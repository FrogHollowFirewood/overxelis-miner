/* Unselected round-specialization experiment from exact compound source.
 * Two generated constant-i inner loops; original memory order and arithmetic.
 * Only sequential c addressing is written with the equivalent A/B half base.
 * Inter-round AES/address updates, original rotates, helpers, and runtime are
 * unchanged. Local stage3 checks do not qualify desktop full hashes or speed.
 */
/* Unselected compound experiment from exact independently reviewed sources.
 * Register BT/CMOV half selection; bounded B-index xor folding;
 * quotient residual comparison; consensus-wrapping isqrt square reuse.
 * All scratch memory operations retain their order. No runtime change.
 * Preserve the small-input isqrt guard and all original round rotations.
 * Target full-hash qualification and measured selection remain required.
 */
/* GENERATED experiment: threaded. See generate_dispatch_candidates.py.
 * No target-machine speed claim; correctness qualification required. */
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
#include "tnn_chacha8_fourstream_wide.h"

#define INPUT_LEN (112)
#define MEMSIZE (531 * 128)
#define ITERS (2)
#define HASH_SIZE (32)

static inline void blake3_threaded(const uint8_t *input, int len, uint8_t *output) {
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

static void stage1_serial_threaded(const uint8_t *input, size_t input_len, uint8_t scratch_pad[OUTPUT_SIZE]) {
	uint8_t key[CHUNK_SIZE * CHUNKS] = {0};
	uint8_t input_hash[HASH_SIZE];
	uint8_t buffer[CHUNK_SIZE * 2];
	memcpy(key, input, INPUT_LEN);
	blake3_threaded(input, INPUT_LEN, buffer);

	uint8_t *t = scratch_pad;

	memcpy(buffer + CHUNK_SIZE, key + 0 * CHUNK_SIZE, CHUNK_SIZE);
	blake3_threaded(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, buffer, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 1 * CHUNK_SIZE, CHUNK_SIZE);
	blake3_threaded(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, t - NONCE_SIZE, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 2 * CHUNK_SIZE, CHUNK_SIZE);
	blake3_threaded(buffer, CHUNK_SIZE * 2, input_hash);
	chacha_encrypt(input_hash, t - NONCE_SIZE, NULL, t, OUTPUT_SIZE / CHUNKS, 8);

	t += OUTPUT_SIZE / CHUNKS;
	memcpy(buffer, input_hash, CHUNK_SIZE);
	memcpy(buffer + CHUNK_SIZE, key + 3 * CHUNK_SIZE, CHUNK_SIZE);
	blake3_threaded(buffer, CHUNK_SIZE * 2, input_hash);
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

static void stage1_threaded(const uint8_t *input, size_t input_len,
                        uint8_t scratch_pad[OUTPUT_SIZE]) {
    if (!__builtin_cpu_supports("avx512f") ||
        !__builtin_cpu_supports("avx512dq") ||
        !__builtin_cpu_supports("avx512bw")) {
        stage1_serial_threaded(input, input_len, scratch_pad);
        return;
    }
    uint8_t input_key[128] = {0}, buffer[64], keys[4][32], nonces[4][12];
    uint8_t *outputs[4];
    memcpy(input_key, input, INPUT_LEN);
    blake3_threaded(input, INPUT_LEN, buffer);
    memcpy(nonces[0], buffer, NONCE_SIZE);
    for (int i = 0; i < CHUNKS; ++i) {
        if (i) memcpy(buffer, keys[i - 1], CHUNK_SIZE);
        memcpy(buffer + CHUNK_SIZE, input_key + i * CHUNK_SIZE, CHUNK_SIZE);
        blake3_threaded(buffer, sizeof(buffer), keys[i]);
        if (i < CHUNKS - 1)
            chacha8_last_nonce(keys[i], nonces[i], nonces[i + 1]);
        outputs[i] = scratch_pad + i * (OUTPUT_SIZE / CHUNKS);
    }
    jay_chacha8_four_wide(keys, nonces, outputs, OUTPUT_SIZE / CHUNKS);
}


#define KEY "xelishash-pow-v3"
#define BUFSIZE (MEMSIZE / 2)

// https://danlark.org/2020/06/14/128-bit-division
static inline uint64_t Divide128Div64To64_threaded(uint64_t high, uint64_t low, uint64_t divisor, uint64_t *remainder) {
	uint64_t result;
	__asm__("divq %[v]"
			: "=a"(result), "=d"(*remainder) // Output parametrs, =a for rax, =d for rdx, [v] is an
			// alias for divisor, input paramters "a" and "d" for low and high.
			: [v] "r"(divisor), "a"(low), "d"(high)
            : "cc");
	return result;
}

static inline uint64_t udiv_threaded(uint64_t high, uint64_t low, uint64_t divisor) {
	uint64_t remainder;

	if (high < divisor) {
		return Divide128Div64To64_threaded(high, low, divisor, &remainder);
	}
	else {
		(void)Divide128Div64To64_threaded(0, high, divisor, &high);
		return Divide128Div64To64_threaded(high, low, divisor, &remainder);
	}
}


/* Reduced high word prevents the x86-64 DIV quotient overflow trap. */
static inline uint64_t remainder128_threaded(uint64_t high, uint64_t low, uint64_t divisor) {
    uint64_t remainder;
    if (high >= divisor)
        high %= divisor;
    (void)Divide128Div64To64_threaded(high, low, divisor, &remainder);
    return remainder;
}

/* For x,y < modulus, the product high word is already < modulus. */
static inline uint64_t mulmod_threaded(uint64_t x, uint64_t y, uint64_t modulus) {
    __uint128_t product = (__uint128_t)x * y;
    uint64_t remainder;
    (void)Divide128Div64To64_threaded((uint64_t)(product >> 64), (uint64_t)product,
                               modulus, &remainder);
    return remainder;
}


/* Exact floor(n/d). Common high-word divisors need only a 64-bit division.
 * qhat = n_hi / d_hi is an upper estimate. When d_hi >= 2^32,
 * qhat <= 2^32-1 <= d_hi, proving the excess is less than d;
 * consequently one downward correction is sufficient.
 */
static inline uint64_t quotient128_threaded(__uint128_t n, __uint128_t d) {
    uint64_t n_hi = (uint64_t)(n >> 64), d_hi = (uint64_t)(d >> 64);
    uint64_t n_lo = (uint64_t)n, d_lo = (uint64_t)d;
    if (n < d)
        return 0;
    if (d_hi && n_hi - d_hi < d_hi)
        return 1;
    if (d_hi >= (UINT64_C(1) << 32)) {
        uint64_t q = n_hi / d_hi;
        uint64_t r_hi = n_hi % d_hi;
        __uint128_t lo_product = (__uint128_t)q * d_lo;
        /* n_hi = q*d_hi + r_hi exactly. Comparing the residual avoids
         * reconstructing q*d's possibly overflowing 129-bit sum. */
        __uint128_t residual = ((__uint128_t)r_hi << 64) | n_lo;
        return q - (lo_product > residual);
    }
    return (uint64_t)(n / d);
}

static inline uint64_t remainder128by128_threaded(__uint128_t n, __uint128_t d) {
    /* V3 consumes only the low 64 bits of this remainder. */
    return (uint64_t)n - quotient128_threaded(n, d) * (uint64_t)d;
}

static inline uint64_t ROTR_threaded(uint64_t x, uint32_t r) {
    unsigned int n = r & 63;
    return (x >> n) | (x << ((0u - n) & 63));
}

static inline uint64_t ROTL_threaded(uint64_t x, uint32_t r) {
    unsigned int n = r & 63;
    return (x << n) | (x >> ((0u - n) & 63));
}

static inline __uint128_t combine_uint64_threaded(uint64_t high, uint64_t low) {
	return ((__uint128_t)high << 64) | low;
}

static inline uint64_t murmurhash3_threaded(uint64_t seed) {
    seed ^= seed >> 55;
    seed *= 0xff51afd7ed558ccdULL;
    seed ^= seed >> 32;
    seed *= 0xc4ceb9fe1a85ec53ULL;
    seed ^= seed >> 15;
    return seed;
}

static inline uint64_t map_index_threaded(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    return (uint64_t)(((__uint128_t)x * BUFSIZE) >> 64);
}

/* idx_a is the output of map_index_threaded, hence idx_a < BUFSIZE.
 * Its bits above 32 are zero. Fold the independent base before combining
 * idx_a, so the B-address xor-shift need not depend on the A-index result.
 * All unsigned products, scratch reads/stores, and prefetches stay exact. */
_Static_assert(BUFSIZE <= (UINT64_C(1) << 33), "bounded B-index xor-shift");
static inline uint64_t map_index_bounded_xor_threaded(uint64_t idx_a,
                                                     uint64_t base) {
    base ^= base >> 33;
    base ^= idx_a;
    base *= 0xff51afd7ed558ccdULL;
    return (uint64_t)(((__uint128_t)base * BUFSIZE) >> 64);
}

static inline uint64_t *pick_half_threaded(uint64_t seed,
                                            uint64_t *half_a, uint64_t *half_b) {
    seed ^= seed >> 55;
    seed *= 0xff51afd7ed558ccdULL;
    seed ^= seed >> 32;
    seed *= 0xc4ceb9fe1a85ec53ULL;
    /* BT copies exactly bit 58 to CF; CMOVC chooses B when that bit is 1.
     * Register-only, no memory clobber or speculative second scratch load.
     * The final full-width murmur XOR remains irrelevant to bit 58. */
    uint64_t *selected = half_a;
    __asm__("btq $58, %[mixed]\n\tcmovcq %[half_b], %[selected]"
            : [selected] "+r" (selected)
            : [mixed] "r" (seed), [half_b] "r" (half_b)
            : "cc");
    return selected;
}

static inline uint64_t isqrt_threaded(uint64_t n) {
    if (n < 2)
        return n;

    // Compute the floating-point square root
    uint64_t approx = (uint64_t)sqrt((double)n);

    // Preserve the consensus unsigned-square wrap in both comparisons.
    uint64_t square = approx * approx;
    if (square > n) {
        return approx - 1;
    } else if (square + (approx << 1) + 1 <= n) {
        return approx + 1;
    } else {
        return approx;
    }
}

static inline uint64_t modular_power_threaded(uint64_t base, uint64_t exp, uint64_t mod) {
    uint64_t result = 1;
    base %= mod;  // Ensure base is within the range of mod
    
    while (exp > 0) {
        // If exp is odd, multiply base with result
        if (exp & 1) {
            result = mulmod_threaded(result, base, mod);
        }
	        
        // Square the base and reduce by mod
        base = mulmod_threaded(base, base, mod);
        exp /= 2;  // Halve the exponent
    }
    
    return result;
}

void static inline uint64_to_le_bytes_threaded(uint64_t value, uint8_t *bytes) {
	for (int i = 0; i < 8; i++) {
		bytes[i] = value & 0xFF;
		value >>= 8;
	}
}

uint64_t static inline le_bytes_to_uint64_threaded(const uint8_t *bytes) {
	uint64_t value = 0;
	for (int i = 7; i >= 0; i--)
		value = (value << 8) | bytes[i];
	return value;
}

void static inline aes_single_round_threaded(uint8_t *block, const uint8_t *key) {
	__m128i block_vec = _mm_loadu_si128((const __m128i *)block);
	__m128i key_vec = _mm_loadu_si128((const __m128i *)key);

	// Perform single AES encryption round
	block_vec = _mm_aesenc_si128(block_vec, key_vec);

	_mm_storeu_si128((__m128i *)block, block_vec);
}

/* One fixed round; two calls per complete hash, no per-iteration call. */
static __attribute__((noinline, noclone)) uint64_t stage3_round0_threaded(uint64_t *scratch, uint64_t result) {
    uint64_t *mem_buffer_a = scratch;
    uint64_t *mem_buffer_b = &scratch[BUFSIZE];
    const uint32_t i = 0;
    uint32_t r = 0;
    uint64_t next_a_idx = map_index_threaded(result);
{
			uint32_t j = 0;
			uint64_t a, b, c, v;
			__uint128_t t1, t2;
			static const void *const targets[16] = {&&jx_case_0, &&jx_case_1, &&jx_case_2, &&jx_case_3, &&jx_case_4, &&jx_case_5, &&jx_case_6, &&jx_case_7, &&jx_case_8, &&jx_case_9, &&jx_case_10, &&jx_case_11, &&jx_case_12, &&jx_case_13, &&jx_case_14, &&jx_case_15};

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		jx_case_0: {
				t1 = combine_uint64_threaded(a + i, isqrt_threaded(b + j));
				uint64_t denom = murmurhash3_threaded(c ^ result ^ i ^ j) | 1;
				v = remainder128_threaded(a + i, isqrt_threaded(b + j), denom);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_0");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_1: {
				v = ROTL_threaded((c + i) % isqrt_threaded(b | 2), i + j) * isqrt_threaded(a + j);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_1");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_2: {
				v = (isqrt_threaded(a + i) * isqrt_threaded(c + j)) ^ (b + i + j);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_2");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_3: {
				v = ((a + b) * c);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_3");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_4: {
				v = ((b - c) * a);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_4");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_5: {
				v = (c - a + b);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_5");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_6: {
				v = (a - b + c);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_6");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_7: {
				v = (b * c + a);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_7");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_8: {
				v = (c * a + b);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_8");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_9: {
				v = (a * b * c);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_9");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_10: {
				t1 = combine_uint64_threaded(a, b);
				v = remainder128_threaded(a, b, c | 1);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_10");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_11: {
				t1 = combine_uint64_threaded(b, c);
				t2 = combine_uint64_threaded(ROTL_threaded(result, r), a | 2);
				v = (t2 > t1) ? c : remainder128by128_threaded(t1, t2);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_11");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_12: {
				v = udiv_threaded(c, a, b | 4);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_12");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_13: {
				t1 = combine_uint64_threaded(ROTL_threaded(result, r), b);
				t2 = combine_uint64_threaded(a, c | 8);
				v = (t1 > t2) ? quotient128_threaded(t1, t2) : a ^ b;

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_13");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_14: {
				t1 = combine_uint64_threaded(b, a);
				v = (t1 * c) >> 64;

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_14");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_15: {
				t1 = combine_uint64_threaded(a, c);
				t2 = combine_uint64_threaded(ROTR_threaded(result, r), b);
				v = (t1 * t2) >> 64;

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_a[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_15");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_loop_done: ;
		}
    return result;
}

/* One fixed round; two calls per complete hash, no per-iteration call. */
static __attribute__((noinline, noclone)) uint64_t stage3_round1_threaded(uint64_t *scratch, uint64_t result) {
    uint64_t *mem_buffer_a = scratch;
    uint64_t *mem_buffer_b = &scratch[BUFSIZE];
    const uint32_t i = 1;
    uint32_t r = BUFSIZE;
    uint64_t next_a_idx = map_index_threaded(result);
{
			uint32_t j = 0;
			uint64_t a, b, c, v;
			__uint128_t t1, t2;
			static const void *const targets[16] = {&&jx_case_0, &&jx_case_1, &&jx_case_2, &&jx_case_3, &&jx_case_4, &&jx_case_5, &&jx_case_6, &&jx_case_7, &&jx_case_8, &&jx_case_9, &&jx_case_10, &&jx_case_11, &&jx_case_12, &&jx_case_13, &&jx_case_14, &&jx_case_15};

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		jx_case_0: {
				t1 = combine_uint64_threaded(a + i, isqrt_threaded(b + j));
				uint64_t denom = murmurhash3_threaded(c ^ result ^ i ^ j) | 1;
				v = remainder128_threaded(a + i, isqrt_threaded(b + j), denom);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_0");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_1: {
				v = ROTL_threaded((c + i) % isqrt_threaded(b | 2), i + j) * isqrt_threaded(a + j);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_1");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_2: {
				v = (isqrt_threaded(a + i) * isqrt_threaded(c + j)) ^ (b + i + j);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_2");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_3: {
				v = ((a + b) * c);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_3");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_4: {
				v = ((b - c) * a);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_4");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_5: {
				v = (c - a + b);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_5");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_6: {
				v = (a - b + c);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_6");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_7: {
				v = (b * c + a);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_7");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_8: {
				v = (c * a + b);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_8");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_9: {
				v = (a * b * c);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_9");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_10: {
				t1 = combine_uint64_threaded(a, b);
				v = remainder128_threaded(a, b, c | 1);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_10");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_11: {
				t1 = combine_uint64_threaded(b, c);
				t2 = combine_uint64_threaded(ROTL_threaded(result, r), a | 2);
				v = (t2 > t1) ? c : remainder128by128_threaded(t1, t2);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_11");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_12: {
				v = udiv_threaded(c, a, b | 4);

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_12");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_13: {
				t1 = combine_uint64_threaded(ROTL_threaded(result, r), b);
				t2 = combine_uint64_threaded(a, c | 8);
				v = (t1 > t2) ? quotient128_threaded(t1, t2) : a ^ b;

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_13");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_14: {
				t1 = combine_uint64_threaded(b, a);
				v = (t1 * c) >> 64;

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_14");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_case_15: {
				t1 = combine_uint64_threaded(a, c);
				t2 = combine_uint64_threaded(ROTR_threaded(result, r), b);
				v = (t1 * t2) >> 64;

			uint64_t idx_seed = v ^ result;
			result = ROTL_threaded(idx_seed, r);
            next_a_idx = map_index_threaded(result);
            __builtin_prefetch(mem_buffer_a + next_a_idx, 0, 3);

			uint64_t *t_half = pick_half_threaded(v, mem_buffer_a, mem_buffer_b);
			uint64_t idx_t = map_index_threaded(idx_seed);
			uint64_t t = t_half[idx_t] ^ result;

			uint64_t idx_a = map_index_threaded(t ^ result ^ 0x9e3779b97f4a7c15);
			uint64_t idx_b = map_index_bounded_xor_threaded(idx_a, ~result ^ 0xd2b74407b1ce6e93);

			uint64_t mem_a = mem_buffer_a[idx_a];
			mem_buffer_a[idx_a] = t;
			mem_buffer_b[idx_b] ^= mem_a ^ ROTR_threaded(t, i + j);
		
			if (++j == BUFSIZE) goto jx_loop_done;

			a = mem_buffer_a[next_a_idx];
			b = mem_buffer_b[map_index_threaded(a ^ ~ROTR_threaded(result, r))];
			/* The two rounds cover scratch sequentially. Only rotates observe r
             * inside this loop, so the final MEMSIZE value is equivalent to
             * zero because MEMSIZE is a multiple of 64. Normalize before
             * the round's modular-power/address update below. */
            c = mem_buffer_b[j];
            r = i * BUFSIZE + j + 1;

			__asm__ volatile("# jayxelis_dispatch_edge_15");
			goto *targets[ROTL_threaded(result, (uint32_t)c) & 0xf];
		}
		jx_loop_done: ;
		}
    return result;
}

static void stage3_threaded(uint64_t *scratch) {
	uint64_t *mem_buffer_a = scratch;
	uint64_t *mem_buffer_b = &scratch[BUFSIZE];

	uint64_t addr_a = mem_buffer_b[BUFSIZE - 1];
	uint64_t addr_b = mem_buffer_a[BUFSIZE - 1] >> 32;
	uint32_t r = 0;

	for (uint32_t i = 0; i < ITERS; i++) {
		uint64_t mem_a = mem_buffer_a[map_index_threaded(addr_a)];
		uint64_t mem_b = mem_buffer_b[map_index_threaded(mem_a ^ addr_b)];

		uint8_t block[16];
		uint64_to_le_bytes_threaded(mem_b, block);
		uint64_to_le_bytes_threaded(mem_a, block + 8);
		aes_single_round_threaded(block, KEY);

		uint64_t hash1 = le_bytes_to_uint64_threaded(block);
		uint64_t hash2 = le_bytes_to_uint64_threaded(block + 8);
		uint64_t result = ~(hash1 ^ hash2);

		result = (i == 0) ? stage3_round0_threaded(scratch, result)
                          : stage3_round1_threaded(scratch, result);

        r = (i == 0) ? BUFSIZE : 0;
		addr_a = modular_power_threaded(addr_a, addr_b, result);
		addr_b = isqrt_threaded(result) * (r + 1) * isqrt_threaded(addr_a);
	}
}



void xelis_hash_v3_round_specialized(uint8_t in[INPUT_LEN], uint8_t hash[HASH_SIZE], uint64_t scratch[MEMSIZE]) {
	uint8_t *scratch_uint8 = (uint8_t *)scratch;

	stage1_threaded(in, INPUT_LEN, scratch_uint8);
	stage3_threaded(scratch);
	blake3_threaded(scratch_uint8, OUTPUT_SIZE, hash);
}