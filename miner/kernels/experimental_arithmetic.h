#ifndef JAYXELIS_EXPERIMENTAL_ARITHMETIC_H
#define JAYXELIS_EXPERIMENTAL_ARITHMETIC_H
#include <stdint.h>
#include <math.h>
#include <immintrin.h>

/* Research candidates. They preserve unsigned wrap semantics and require
 * normal IEEE arithmetic: never compile with -ffast-math. They are not a
 * validated performance improvement, and are isolated from the default kernel.
 */
static inline double jay_u64_double_scalar(uint64_t n) {
#if defined(__AVX512F__)
    return _mm_cvtsd_f64(_mm_cvtu64_sd(_mm_setzero_pd(), n));
#else
    return (double)n;
#endif
}

/* Floating point supplies an estimate ONLY. Integer products/comparisons
 * establish the exact quotient. For d_hi >= 2^32, n_hi/d_hi <= 2^32-1.
 * IEEE binary64 conversion/division perturb that estimate by < 2^-19 under
 * round-to-nearest, so its truncated value differs from floor(n_hi/d_hi)
 * by at most one. The full 128-bit quotient is at most one below that floor.
 * Thus at most two downward corrections and one upward correction suffice.
 * A bounded correction loop and exact fallback avoid relying on this estimate
 * bound for correctness (including unusual floating point rounding modes).
 * The product high word is retained at 128 bits to detect q*d > 2^128-1.
 */
static inline uint64_t jay_quotient128_fp(__uint128_t n, __uint128_t d) {
    uint64_t nh = (uint64_t)(n >> 64), dh = (uint64_t)(d >> 64);
    uint64_t nl = (uint64_t)n, dl = (uint64_t)d;
    if (n < d) return 0;
    if (dh && nh - dh < dh) return 1;
    if (dh < (UINT64_C(1) << 32)) return (uint64_t)(n / d);
    uint64_t q = (uint64_t)(jay_u64_double_scalar(nh) /
                            jay_u64_double_scalar(dh));
    for (unsigned corrections = 0; corrections < 4; ++corrections) {
        __uint128_t lp = (__uint128_t)q * dl;
        __uint128_t hp = (__uint128_t)q * dh + (lp >> 64);
        if (hp > nh || (hp == nh && (uint64_t)lp > nl)) {
            if (!q) return (uint64_t)(n / d);
            --q;
            continue;
        }
        __uint128_t product = (hp << 64) | (uint64_t)lp;
        if (n - product >= d) {
            ++q;
            continue;
        }
        return q;
    }
    return (uint64_t)(n / d);
}

/* The root is <= 2^32, so the signed scalar FP-to-i64 conversion is safe and
 * avoids general FP-to-u64 conversion handling. Keep the official wrapping
 * square corrections, even at n near UINT64_MAX, where this deliberately
 * differs from the mathematical floor square root.
 */
static inline uint64_t jay_isqrt_scalar(uint64_t n) {
#if defined(__AVX512F__)
    __m128d x = _mm_cvtu64_sd(_mm_setzero_pd(), n);
#else
    __m128d x = _mm_set_sd(jay_u64_double_scalar(n));
#endif
    __m128d y = _mm_sqrt_sd(x, x);
    uint64_t a = (uint64_t)_mm_cvttsd_si64(y);
    if (a * a > n) return a - 1;
    uint64_t ap = a + 1;
    if (ap * ap <= n) return ap;
    return a;
}
#endif
