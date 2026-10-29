/* ISOLATED EXPERIMENT: sqrt. Not selected by default. */
/* Experimental, consensus-compatible optimization candidate. Derived from the
 * Xelis project's MIT-licensed C XelisHash V3 reference implementation.
 * No standalone benchmark/main and no shared mutable state.
 * Requires x86-64 AES support; do not compile with -ffast-math.
 */
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
#include "blake3.h"
#include "chacha20.h"
#include <math.h>
#include "experimental_arithmetic.h"
#include "tnn_chacha8_fourstream_wide.h"

#define INPUT_LEN (112)
#define MEMSIZE (531 * 128)
#define ITERS (2)
#define HASH_SIZE (32)

static inline void blake3_exp_sqrt(const uint8_t *input, int len, uint8_t *output) {
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

static void stage1_serial_exp_sqrt(const uint8_t *input, size_t input_len, uint8_t scratch_pad[OUTPUT_SIZE]) {
	uint8_t key[CHUNK_SIZE * CHUNKS] = {0};
	uint8_t input_hash[HASH_SIZE];
	uint8_t buffer[CHUNK_SIZE * 2];
	memcpy(key, input, INPUT_LEN);
	blake3_exp_sqrt(input, INPUT_LEN, buffer);

	uint8_t *t = scratch_pad;

	memcpy(buffer + CHUNK_SIZE, key + 0 * CHUNK_SIZE, CHUNK_SIZE);
	blake3_exp_sqrt(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, buffer, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 1 * CHUNK_SIZE, CHUNK_SIZE);
	blake3_exp_sqrt(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, t - NONCE_SIZE, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 2 * CHUNK_SIZE, CHUNK_SIZE);
	blake3_exp_sqrt(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, t - NONCE_SIZE, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 3 * CHUNK_SIZE, CHUNK_SIZE);
	blake3_exp_sqrt(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, t - NONCE_SIZE, NULL, t, OUTPUT_SIZE / CHUNKS, 8);
}


/* Existing portable implementation: one block permits exact nonce lookahead. */
extern void ChaCha20EncryptBytes(uint8_t *state, uint8_t *in, uint8_t *out,
                                 size_t bytes, uint32_t rounds);
static void chacha8_last_nonce(const uint8_t key[32], const uint8_t nonce[12],
                               uint8_t next_nonce[12]) {
    uint8_t state[48] = {0}, last_block[64];
    uint32_t counter = (OUTPUT_SIZE / CHUNKS / 64) - 1;
    ChaCha20SetKey(state, key);
    ChaCha20SetNonce(state, nonce);
    memcpy(state + 32, &counter, sizeof(counter));
    ChaCha20EncryptBytes(state, NULL, last_block, sizeof(last_block), 8);
    memcpy(next_nonce, last_block + 52, 12);
}

static void stage1_exp_sqrt(const uint8_t *input, size_t input_len,
                        uint8_t scratch_pad[OUTPUT_SIZE]) {
    if (!__builtin_cpu_supports("avx512f") ||
        !__builtin_cpu_supports("avx512dq") ||
        !__builtin_cpu_supports("avx512bw")) {
        stage1_serial_exp_sqrt(input, input_len, scratch_pad);
        return;
    }
    uint8_t input_key[128] = {0}, buffer[64], keys[4][32], nonces[4][12];
    uint8_t *outputs[4];
    memcpy(input_key, input, INPUT_LEN);
    blake3_exp_sqrt(input, INPUT_LEN, buffer);
    memcpy(nonces[0], buffer, NONCE_SIZE);
    for (int i = 0; i < CHUNKS; ++i) {
        if (i) memcpy(buffer, keys[i - 1], CHUNK_SIZE);
        memcpy(buffer + CHUNK_SIZE, input_key + i * CHUNK_SIZE, CHUNK_SIZE);
        blake3_exp_sqrt(buffer, sizeof(buffer), keys[i]);
        if (i < CHUNKS - 1)
            chacha8_last_nonce(keys[i], nonces[i], nonces[i + 1]);
        outputs[i] = scratch_pad + i * (OUTPUT_SIZE / CHUNKS);
    }
    jay_chacha8_four_wide(keys, nonces, outputs, OUTPUT_SIZE / CHUNKS);
}


#define KEY "xelishash-pow-v3"
#define BUFSIZE (MEMSIZE / 2)

// https://danlark.org/2020/06/14/128-bit-division
static inline uint64_t Divide128Div64To64_exp_sqrt(uint64_t high, uint64_t low, uint64_t divisor, uint64_t *remainder) {
	uint64_t result;
	__asm__("divq %[v]"
			: "=a"(result), "=d"(*remainder) // Output parametrs, =a for rax, =d for rdx, [v] is an
			// alias for divisor, input paramters "a" and "d" for low and high.
			: [v] "r"(divisor), "a"(low), "d"(high)
            : "cc");
	return result;
}

static inline uint64_t udiv_exp_sqrt(uint64_t high, uint64_t low, uint64_t divisor) {
	uint64_t remainder;

	if (high < divisor) {
		return Divide128Div64To64_exp_sqrt(high, low, divisor, &remainder);
	}
	else {
		(void)Divide128Div64To64_exp_sqrt(0, high, divisor, &high);
		return Divide128Div64To64_exp_sqrt(high, low, divisor, &remainder);
	}
}


/* Reduced high word prevents the x86-64 DIV quotient overflow trap. */
static inline uint64_t remainder128_exp_sqrt(uint64_t high, uint64_t low, uint64_t divisor) {
    uint64_t remainder;
    if (high >= divisor)
        high %= divisor;
    (void)Divide128Div64To64_exp_sqrt(high, low, divisor, &remainder);
    return remainder;
}

/* For x,y < modulus, the product high word is already < modulus. */
static inline uint64_t mulmod_exp_sqrt(uint64_t x, uint64_t y, uint64_t modulus) {
    __uint128_t product = (__uint128_t)x * y;
    uint64_t remainder;
    (void)Divide128Div64To64_exp_sqrt((uint64_t)(product >> 64), (uint64_t)product,
                               modulus, &remainder);
    return remainder;
}


/* Exact floor(n/d). Common high-word divisors need only a 64-bit division.
 * qhat = n_hi / d_hi is an upper estimate. When d_hi >= 2^32,
 * qhat <= 2^32-1 <= d_hi, proving the excess is less than d;
 * consequently one downward correction is sufficient.
 */
static inline uint64_t quotient128_exp_sqrt(__uint128_t n, __uint128_t d) {
    uint64_t n_hi = (uint64_t)(n >> 64), d_hi = (uint64_t)(d >> 64);
    uint64_t n_lo = (uint64_t)n, d_lo = (uint64_t)d;
    if (n < d)
        return 0;
    if (d_hi && n_hi - d_hi < d_hi)
        return 1;
    if (d_hi >= (UINT64_C(1) << 32)) {
        uint64_t q = n_hi / d_hi;
        __uint128_t lo_product = (__uint128_t)q * d_lo;
        uint64_t high_base = q * d_hi;
        uint64_t high_product = high_base + (uint64_t)(lo_product >> 64);
        /* Include overflow of q*d beyond 128 bits in the correction test. */
        if (high_product < high_base || high_product > n_hi ||
            (high_product == n_hi && (uint64_t)lo_product > n_lo))
            --q;
        return q;
    }
    return (uint64_t)(n / d);
}

static inline uint64_t remainder128by128_exp_sqrt(__uint128_t n, __uint128_t d) {
    /* V3 consumes only the low 64 bits of this remainder. */
    return (uint64_t)n - quotient128_exp_sqrt(n, d) * (uint64_t)d;
}

static inline uint64_t ROTR_exp_sqrt(uint64_t x, uint32_t r) {
    unsigned int n = r & 63;
    return (x >> n) | (x << ((0u - n) & 63));
}

static inline uint64_t ROTL_exp_sqrt(uint64_t x, uint32_t r) {
    unsigned int n = r & 63;
    return (x << n) | (x >> ((0u - n) & 63));
}

static inline __uint128_t combine_uint64_exp_sqrt(uint64_t high, uint64_t low) {
	return ((__uint128_t)high << 64) | low;
}

static inline uint64_t murmurhash3_exp_sqrt(uint64_t seed) {
    seed ^= seed >> 55;
    seed *= 0xff51afd7ed558ccdULL;
    seed ^= seed >> 32;
    seed *= 0xc4ceb9fe1a85ec53ULL;
    seed ^= seed >> 15;
    return seed;
}

static inline uint64_t map_index_exp_sqrt(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    return (uint64_t)(((__uint128_t)x * BUFSIZE) >> 64);
}

static inline int pick_half_exp_sqrt(uint64_t seed) {
    return (murmurhash3_exp_sqrt(seed) & (1ULL << 58)) != 0;
}

static inline uint64_t isqrt_exp_sqrt(uint64_t n) {
    return jay_isqrt_scalar(n);
}

static inline uint64_t modular_power_exp_sqrt(uint64_t base, uint64_t exp, uint64_t mod) {
    uint64_t result = 1;
    base %= mod;  // Ensure base is within the range of mod
    
    while (exp > 0) {
        // If exp is odd, multiply base with result
        if (exp & 1) {
            result = mulmod_exp_sqrt(result, base, mod);
        }
	        
        // Square the base and reduce by mod
        base = mulmod_exp_sqrt(base, base, mod);
        exp /= 2;  // Halve the exponent
    }
    
    return result;
}

void static inline uint64_to_le_bytes_exp_sqrt(uint64_t value, uint8_t *bytes) {
	for (int i = 0; i < 8; i++) {
		bytes[i] = value & 0xFF;
		value >>= 8;
	}
}

uint64_t static inline le_bytes_to_uint64_exp_sqrt(const uint8_t *bytes) {
	uint64_t value = 0;
	for (int i = 7; i >= 0; i--)
		value = (value << 8) | bytes[i];
	return value;
}

void static inline aes_single_round_exp_sqrt(uint8_t *block, const uint8_t *key) {
	__m128i block_vec = _mm_loadu_si128((const __m128i *)block);
	__m128i key_vec = _mm_loadu_si128((const __m128i *)key);

	// Perform single AES encryption round
	block_vec = _mm_aesenc_si128(block_vec, key_vec);

	_mm_storeu_si128((__m128i *)block, block_vec);
}

static void stage3_exp_sqrt(uint64_t *scratch) {
	uint64_t *mem_buffer_a = scratch;
	uint64_t *mem_buffer_b = &scratch[BUFSIZE];

	uint64_t addr_a = mem_buffer_b[BUFSIZE - 1];
	uint64_t addr_b = mem_buffer_a[BUFSIZE - 1] >> 32;
	uint32_t r = 0;

	for (uint32_t i = 0; i < ITERS; i++) {
		uint64_t mem_a = mem_buffer_a[map_index_exp_sqrt(addr_a)];
		uint64_t mem_b = mem_buffer_b[map_index_exp_sqrt(mem_a ^ addr_b)];

		uint8_t block[16];
		uint64_to_le_bytes_exp_sqrt(mem_b, block);
		uint64_to_le_bytes_exp_sqrt(mem_a, block + 8);
		aes_single_round_exp_sqrt(block, KEY);

		uint64_t hash1 = le_bytes_to_uint64_exp_sqrt(block);
		uint64_t hash2 = le_bytes_to_uint64_exp_sqrt(block + 8);
		uint64_t result = ~(hash1 ^ hash2);
        uint64_t next_a_idx = map_index_exp_sqrt(result);

		for (uint32_t j = 0; j < BUFSIZE; j++) {
			uint64_t a = mem_buffer_a[next_a_idx];
			uint64_t b = mem_buffer_b[map_index_exp_sqrt(a ^ ~ROTR_exp_sqrt(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            uint64_t c = scratch[i * BUFSIZE + j];
            r = i * BUFSIZE + j + 1;

			uint64_t v;
			__uint128_t t1, t2;
			switch (ROTL_exp_sqrt(result, (uint32_t)c) & 0xf) {
			case 0:
				t1 = combine_uint64_exp_sqrt(a + i, isqrt_exp_sqrt(b + j));
				uint64_t denom = murmurhash3_exp_sqrt(c ^ result ^ i ^ j) | 1;
				v = remainder128_exp_sqrt(a + i, isqrt_exp_sqrt(b + j), denom);
				break;
			case 1:
				v = ROTL_exp_sqrt((c + i) % isqrt_exp_sqrt(b | 2), i + j) * isqrt_exp_sqrt(a + j);
				break;
			case 2:
				v = (isqrt_exp_sqrt(a + i) * isqrt_exp_sqrt(c + j)) ^ (b + i + j);
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
				t1 = combine_uint64_exp_sqrt(a, b);
				v = remainder128_exp_sqrt(a, b, c | 1);
				break;
			case 11:
				t1 = combine_uint64_exp_sqrt(b, c);
				t2 = combine_uint64_exp_sqrt(ROTL_exp_sqrt(result, r), a | 2);
				v = (t2 > t1) ? c : remainder128by128_exp_sqrt(t1, t2);
				break;
			case 12:
				v = udiv_exp_sqrt(c, a, b | 4);
				break;
			case 13:
				t1 = combine_uint64_exp_sqrt(ROTL_exp_sqrt(result, r), b);
				t2 = combine_uint64_exp_sqrt(a, c | 8);
				v = (t1 > t2) ? quotient128_exp_sqrt(t1, t2) : a ^ b;
				break;
			case 14:
				t1 = combine_uint64_exp_sqrt(b, a);
				v = (t1 * c) >> 64;
				break;
			case 15:
				t1 = combine_uint64_exp_sqrt(a, c);
				t2 = combine_uint64_exp_sqrt(ROTR_exp_sqrt(result, r), b);
				v = (t1 * t2) >> 64;
				break;
			}
			uint64_t idx_seed = v ^ result;
			result = ROTL_exp_sqrt(idx_seed, r);
            next_a_idx = map_index_exp_sqrt(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t use_buffer_b = pick_half_exp_sqrt(v);
			uint64_t idx_t = map_index_exp_sqrt(idx_seed);
			uint64_t t = scratch[idx_t + use_buffer_b * BUFSIZE] ^ result;

			uint64_t idx_a = map_index_exp_sqrt(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_exp_sqrt(idx_a ^ ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_exp_sqrt(t, i + j);
		}

        r = (i == 0) ? BUFSIZE : 0;
		addr_a = modular_power_exp_sqrt(addr_a, addr_b, result);
		addr_b = isqrt_exp_sqrt(result) * (r + 1) * isqrt_exp_sqrt(addr_a);
	}
}



void xelis_hash_v3_exp_sqrt(uint8_t in[INPUT_LEN], uint8_t hash[HASH_SIZE], uint64_t scratch[MEMSIZE]) {
	uint8_t *scratch_uint8 = (uint8_t *)scratch;

	stage1_exp_sqrt(in, INPUT_LEN, scratch_uint8);
	stage3_exp_sqrt(scratch);
	blake3_exp_sqrt(scratch_uint8, OUTPUT_SIZE, hash);
}
