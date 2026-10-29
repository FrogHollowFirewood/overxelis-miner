#define _GNU_SOURCE
#include <stdio.h>
#include <malloc.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <sched.h>
#include <unistd.h>
#include <wmmintrin.h>
#include "BLAKE3/c/blake3.h"
#include "ChaCha20-SIMD/chacha20.h"
#include <math.h>

#define INPUT_LEN (112)
#define MEMSIZE (531 * 128)
#define ITERS (2)
#define HASH_SIZE (32)

static inline void blake3(const uint8_t *input, int len, uint8_t *output) {
	blake3_hasher hasher;
	blake3_hasher_init(&hasher);
	blake3_hasher_update(&hasher, input, len);
	blake3_hasher_finalize(&hasher, output, BLAKE3_OUT_LEN);
}

#define CHUNK_SIZE (32)
#define NONCE_SIZE (12)
#define OUTPUT_SIZE (MEMSIZE * 8)
#define CHUNKS (4)
#define INPUT_LEN (112)

void stage1(const uint8_t *input, size_t input_len, uint8_t scratch_pad[OUTPUT_SIZE]) {
	uint8_t key[CHUNK_SIZE * CHUNKS] = {0};
	uint8_t input_hash[HASH_SIZE];
	uint8_t buffer[CHUNK_SIZE * 2];
	memcpy(key, input, INPUT_LEN);
	blake3(input, INPUT_LEN, buffer);

	uint8_t *t = scratch_pad;

	memcpy(buffer + CHUNK_SIZE, key + 0 * CHUNK_SIZE, CHUNK_SIZE);
	blake3(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, buffer, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 1 * CHUNK_SIZE, CHUNK_SIZE);
	blake3(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, t - NONCE_SIZE, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 2 * CHUNK_SIZE, CHUNK_SIZE);
	blake3(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, t - NONCE_SIZE, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 3 * CHUNK_SIZE, CHUNK_SIZE);
	blake3(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, t - NONCE_SIZE, NULL, t, OUTPUT_SIZE / CHUNKS, 8);
}

#define KEY "xelishash-pow-v3"
#define BUFSIZE (MEMSIZE / 2)

// https://danlark.org/2020/06/14/128-bit-division
static inline uint64_t Divide128Div64To64(uint64_t high, uint64_t low, uint64_t divisor, uint64_t *remainder) {
	uint64_t result;
	__asm__("divq %[v]"
			: "=a"(result), "=d"(*remainder) // Output parametrs, =a for rax, =d for rdx, [v] is an
			// alias for divisor, input paramters "a" and "d" for low and high.
			: [v] "r"(divisor), "a"(low), "d"(high) : "cc");
	return result;
}

static inline uint64_t udiv(uint64_t high, uint64_t low, uint64_t divisor) {
	uint64_t remainder;

	if (high < divisor) {
		return Divide128Div64To64(high, low, divisor, &remainder);
	}
	else {
		(void)Divide128Div64To64(0, high, divisor, &high);
		return Divide128Div64To64(high, low, divisor, &remainder);
	}
}

static inline uint64_t ROTR(uint64_t x, uint32_t r) {
	asm("rorq %%cl, %0" : "+r"(x) : "c"(r) : "cc");
	return x;
}

static inline uint64_t ROTL(uint64_t x, uint32_t r) {
	asm("rolq %%cl, %0" : "+r"(x) : "c"(r) : "cc");
	return x;
}

static inline __uint128_t combine_uint64(uint64_t high, uint64_t low) {
	return ((__uint128_t)high << 64) | low;
}

static inline uint64_t murmurhash3(uint64_t seed) {
    seed ^= seed >> 55;
    seed *= 0xff51afd7ed558ccdULL;
    seed ^= seed >> 32;
    seed *= 0xc4ceb9fe1a85ec53ULL;
    seed ^= seed >> 15;
    return seed;
}

static inline uint64_t map_index(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    return (uint64_t)(((__uint128_t)x * BUFSIZE) >> 64);
}

static inline int pick_half(uint64_t seed) {
    return (murmurhash3(seed) & (1ULL << 58)) != 0;
}

uint64_t isqrt(uint64_t n) {
    if (n < 2)
        return n;

    // Compute the floating-point square root
    uint64_t approx = (uint64_t)sqrt((double)n);

    // Verify and adjust if necessary
    if (approx * approx > n) {
        return approx - 1;
    } else if ((approx + 1) * (approx + 1) <= n) {
        return approx + 1;
    } else {
        return approx;
    }
}

uint64_t modular_power(uint64_t base, uint64_t exp, uint64_t mod) {
    uint64_t result = 1;
    base %= mod;  // Ensure base is within the range of mod
    
    while (exp > 0) {
        // If exp is odd, multiply base with result
        if (exp & 1) {
            result = (uint64_t)(((__uint128_t)result * base) % mod);
        }
	        
        // Square the base and reduce by mod
        base = (uint64_t)(((__uint128_t)base * base) % mod);
        exp /= 2;  // Halve the exponent
    }
    
    return result;
}

void static inline uint64_to_le_bytes(uint64_t value, uint8_t *bytes) {
	for (int i = 0; i < 8; i++) {
		bytes[i] = value & 0xFF;
		value >>= 8;
	}
}

uint64_t static inline le_bytes_to_uint64(const uint8_t *bytes) {
	uint64_t value = 0;
	for (int i = 7; i >= 0; i--)
		value = (value << 8) | bytes[i];
	return value;
}

void static inline aes_single_round(uint8_t *block, const uint8_t *key) {
	__m128i block_vec = _mm_loadu_si128((const __m128i *)block);
	__m128i key_vec = _mm_loadu_si128((const __m128i *)key);

	// Perform single AES encryption round
	block_vec = _mm_aesenc_si128(block_vec, key_vec);

	_mm_storeu_si128((__m128i *)block, block_vec);
}

void stage3(uint64_t *scratch) {
	uint64_t *mem_buffer_a = scratch;
	uint64_t *mem_buffer_b = &scratch[BUFSIZE];

	uint64_t addr_a = mem_buffer_b[BUFSIZE - 1];
	uint64_t addr_b = mem_buffer_a[BUFSIZE - 1] >> 32;
	uint32_t r = 0;

	for (uint32_t i = 0; i < ITERS; i++) {
		uint64_t mem_a = mem_buffer_a[map_index(addr_a)];
		uint64_t mem_b = mem_buffer_b[map_index(mem_a ^ addr_b)];

		uint8_t block[16];
		uint64_to_le_bytes(mem_b, block);
		uint64_to_le_bytes(mem_a, block + 8);
		aes_single_round(block, KEY);

		uint64_t hash1 = le_bytes_to_uint64(block);
		uint64_t hash2 = le_bytes_to_uint64(block + 8);
		uint64_t result = ~(hash1 ^ hash2);

		for (uint32_t j = 0; j < BUFSIZE; j++) {
			uint64_t a = mem_buffer_a[map_index(result)];
			uint64_t b = mem_buffer_b[map_index(a ^ ~ROTR(result, r))];
			uint64_t c = (r < BUFSIZE) ? mem_buffer_a[r] : mem_buffer_b[r - BUFSIZE];
			r = (r < MEMSIZE - 1) ? r + 1 : 0;

			uint64_t v;
			__uint128_t t1, t2;
			switch (ROTL(result, (uint32_t)c) & 0xf) {
			case 0:
				t1 = combine_uint64(a + i, isqrt(b + j));
				uint64_t denom = murmurhash3(c ^ result ^ i ^ j) | 1;
				v = (uint64_t)(t1 % denom);
				break;
			case 1:
				v = ROTL((c + i) % isqrt(b | 2), i + j) * isqrt(a + j);
				break;
			case 2:
				v = (isqrt(a + i) * isqrt(c + j)) ^ (b + i + j);
				break;
			case 3:
				v = ((a + b) * c);
				break;
			case 4:
				v = ((b - c) * a);
				break;
			case 5:
				v = (c - a + b);
				break;
			case 6:
				v = (a - b + c);
				break;
			case 7:
				v = (b * c + a);
				break;
			case 8:
				v = (c * a + b);
				break;
			case 9:
				v = (a * b * c);
				break;
			case 10:
				t1 = combine_uint64(a, b);
				v = t1 % (c | 1);
				break;
			case 11:
				t1 = combine_uint64(b, c);
				t2 = combine_uint64(ROTL(result, r), a | 2);
				v = (t2 > t1) ? c : t1 % t2;
				break;
			case 12:
				v = udiv(c, a, b | 4);
				break;
			case 13:
				t1 = combine_uint64(ROTL(result, r), b);
				t2 = combine_uint64(a, c | 8);
				v = (t1 > t2) ? t1 / t2 : a ^ b;
				break;
			case 14:
				t1 = combine_uint64(b, a);
				v = (t1 * c) >> 64;
				break;
			case 15:
				t1 = combine_uint64(a, c);
				t2 = combine_uint64(ROTR(result, r), b);
				v = (t1 * t2) >> 64;
				break;
			}
			uint64_t idx_seed = v ^ result;
			result = ROTL(idx_seed, r);

			uint64_t use_buffer_b = pick_half(v);
			uint64_t idx_t = map_index(idx_seed);
			uint64_t t = (use_buffer_b ? mem_buffer_b[idx_t] : mem_buffer_a[idx_t]) ^ result;

			uint64_t idx_a = map_index(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index(idx_a ^ ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR(t, i + j);
		}

		addr_a = modular_power(addr_a, addr_b, result);
		addr_b = isqrt(result) * (r + 1) * isqrt(addr_a);
	}
}

int xelis_hash_v3_init() { return 0; }

void xelis_hash_v3(uint8_t in[INPUT_LEN], uint8_t hash[HASH_SIZE], uint64_t scratch[MEMSIZE]) {
	uint8_t *scratch_uint8 = (uint8_t *)scratch;

	stage1(in, INPUT_LEN, scratch_uint8);
	stage3(scratch);
	blake3(scratch_uint8, OUTPUT_SIZE, hash);
}

