/* Exact C adaptation of TNN's temporal-store AVX512 four-stream ChaCha path.
 * Source: Tritonn204/tnn-miner include/chacha20_xelis_inline.h
 * Commit b567a87b9fef84e20ebc4b7747ad871361b31974.
 * Copyright (c) 2023 Tritonn204. Distributed under the MIT license;
 * see vendor/TNN-LICENSE. Only ChaCha code is reused; no TNN Stage3 math.
 */
#ifndef JAY_CHACHA8_FOURSTREAM_WIDE_H
#define JAY_CHACHA8_FOURSTREAM_WIDE_H
#include <immintrin.h>
__attribute__((target("avx512f,avx512dq,avx512bw")))
static inline void jay_chacha8_four_wide(
    const uint8_t keys[4][32],
    const uint8_t nonces[4][12],
    uint8_t* outputs[4],
    const size_t bytes_per_stream)
{
    const __m512i const0 = _mm512_set1_epi32(0x61707865);
    const __m512i const1 = _mm512_set1_epi32(0x3320646e);
    const __m512i const2 = _mm512_set1_epi32(0x79622d32);
    const __m512i const3 = _mm512_set1_epi32(0x6b206574);

    // Load and transpose keys: k# = same key word for 4 streams, broadcast to 4 lanes
    __m512i k0, k1, k2, k3, k4, k5, k6, k7;
    {
        __m128i key0 = _mm_loadu_si128((const __m128i*)keys[0]);
        __m128i key1 = _mm_loadu_si128((const __m128i*)keys[1]);
        __m128i key2 = _mm_loadu_si128((const __m128i*)keys[2]);
        __m128i key3 = _mm_loadu_si128((const __m128i*)keys[3]);

        __m128i key0_hi = _mm_loadu_si128((const __m128i*)(keys[0] + 16));
        __m128i key1_hi = _mm_loadu_si128((const __m128i*)(keys[1] + 16));
        __m128i key2_hi = _mm_loadu_si128((const __m128i*)(keys[2] + 16));
        __m128i key3_hi = _mm_loadu_si128((const __m128i*)(keys[3] + 16));

        __m128i t0 = _mm_unpacklo_epi32(key0, key1);
        __m128i t1 = _mm_unpacklo_epi32(key2, key3);
        __m128i t2 = _mm_unpackhi_epi32(key0, key1);
        __m128i t3 = _mm_unpackhi_epi32(key2, key3);

        k0 = _mm512_broadcast_i32x4(_mm_unpacklo_epi64(t0, t1));
        k1 = _mm512_broadcast_i32x4(_mm_unpackhi_epi64(t0, t1));
        k2 = _mm512_broadcast_i32x4(_mm_unpacklo_epi64(t2, t3));
        k3 = _mm512_broadcast_i32x4(_mm_unpackhi_epi64(t2, t3));

        t0 = _mm_unpacklo_epi32(key0_hi, key1_hi);
        t1 = _mm_unpacklo_epi32(key2_hi, key3_hi);
        t2 = _mm_unpackhi_epi32(key0_hi, key1_hi);
        t3 = _mm_unpackhi_epi32(key2_hi, key3_hi);

        k4 = _mm512_broadcast_i32x4(_mm_unpacklo_epi64(t0, t1));
        k5 = _mm512_broadcast_i32x4(_mm_unpackhi_epi64(t0, t1));
        k6 = _mm512_broadcast_i32x4(_mm_unpacklo_epi64(t2, t3));
        k7 = _mm512_broadcast_i32x4(_mm_unpackhi_epi64(t2, t3));
    }

    // Load and transpose nonces
    __m512i n0, n1, n2;
    {
        uint32_t nonce_words[4][3];
        for (int i = 0; i < 4; i++)
            memcpy(nonce_words[i], nonces[i], 12);

        n0 = _mm512_broadcast_i32x4(_mm_setr_epi32(
            nonce_words[0][0], nonce_words[1][0], nonce_words[2][0], nonce_words[3][0]));
        n1 = _mm512_broadcast_i32x4(_mm_setr_epi32(
            nonce_words[0][1], nonce_words[1][1], nonce_words[2][1], nonce_words[3][1]));
        n2 = _mm512_broadcast_i32x4(_mm_setr_epi32(
            nonce_words[0][2], nonce_words[1][2], nonce_words[2][2], nonce_words[3][2]));
    }

    // Counter offsets: 4 blocks, same counter within each 128-bit lane
    // Lane 0 = block +0, lane 1 = block +1, lane 2 = block +2, lane 3 = block +3
    const __m512i ctr_inc = _mm512_setr_epi32(
        0, 0, 0, 0,   // lane 0: block 0
        1, 1, 1, 1,   // lane 1: block 1
        2, 2, 2, 2,   // lane 2: block 2
        3, 3, 3, 3    // lane 3: block 3
    );

    size_t iterations = bytes_per_stream / 256;  // 4 blocks x 64 bytes per stream
    uint32_t counter_base = 0;

    for (size_t iter = 0; iter < iterations; iter++)
    {
        __m512i counter = _mm512_add_epi32(_mm512_set1_epi32(counter_base), ctr_inc);

        __m512i x0 = const0, x1 = const1, x2 = const2, x3 = const3;
        __m512i x4 = k0, x5 = k1, x6 = k2, x7 = k3;
        __m512i x8 = k4, x9 = k5, x10 = k6, x11 = k7;
        __m512i x12 = counter, x13 = n0, x14 = n1, x15 = n2;

        const __m512i s0  = x0,  s1  = x1,  s2  = x2,  s3  = x3;
        const __m512i s4  = x4,  s5  = x5,  s6  = x6,  s7  = x7;
        const __m512i s8  = x8,  s9  = x9,  s10 = x10, s11 = x11;
        const __m512i s12 = x12, s13 = x13, s14 = x14, s15 = x15;

        for (int i = 8; i > 0; i -= 2)
        {
            #define QR_AVX512_INL(a, b, c, d) \
                a = _mm512_add_epi32(a, b); d = _mm512_xor_si512(d, a); d = _mm512_rol_epi32(d, 16); \
                c = _mm512_add_epi32(c, d); b = _mm512_xor_si512(b, c); b = _mm512_rol_epi32(b, 12); \
                a = _mm512_add_epi32(a, b); d = _mm512_xor_si512(d, a); d = _mm512_rol_epi32(d, 8);  \
                c = _mm512_add_epi32(c, d); b = _mm512_xor_si512(b, c); b = _mm512_rol_epi32(b, 7);

            // Column round
            QR_AVX512_INL(x0, x4, x8,  x12); QR_AVX512_INL(x1, x5, x9,  x13);
            QR_AVX512_INL(x2, x6, x10, x14); QR_AVX512_INL(x3, x7, x11, x15);
            // Diagonal round
            QR_AVX512_INL(x0, x5, x10, x15); QR_AVX512_INL(x1, x6, x11, x12);
            QR_AVX512_INL(x2, x7, x8,  x13); QR_AVX512_INL(x3, x4, x9,  x14);

            #undef QR_AVX512_INL
        }

        x0  = _mm512_add_epi32(x0,  s0);  x1  = _mm512_add_epi32(x1,  s1);
        x2  = _mm512_add_epi32(x2,  s2);  x3  = _mm512_add_epi32(x3,  s3);
        x4  = _mm512_add_epi32(x4,  s4);  x5  = _mm512_add_epi32(x5,  s5);
        x6  = _mm512_add_epi32(x6,  s6);  x7  = _mm512_add_epi32(x7,  s7);
        x8  = _mm512_add_epi32(x8,  s8);  x9  = _mm512_add_epi32(x9,  s9);
        x10 = _mm512_add_epi32(x10, s10); x11 = _mm512_add_epi32(x11, s11);
        x12 = _mm512_add_epi32(x12, s12); x13 = _mm512_add_epi32(x13, s13);
        x14 = _mm512_add_epi32(x14, s14); x15 = _mm512_add_epi32(x15, s15);

        /* Gather all four groups of state words per stream, then transpose
         * 128-bit lanes to contiguous 64-byte blocks before temporal stores. */
        __m512i group[4][4];
        #define PACK_FOUR_WORDS(xa, xb, xc, xd, g) \
        { \
            __m512i t0=_mm512_unpacklo_epi32(xa,xb); \
            __m512i t1=_mm512_unpackhi_epi32(xa,xb); \
            __m512i t2=_mm512_unpacklo_epi32(xc,xd); \
            __m512i t3=_mm512_unpackhi_epi32(xc,xd); \
            group[g][0]=_mm512_unpacklo_epi64(t0,t2); \
            group[g][1]=_mm512_unpackhi_epi64(t0,t2); \
            group[g][2]=_mm512_unpacklo_epi64(t1,t3); \
            group[g][3]=_mm512_unpackhi_epi64(t1,t3); \
        }
        PACK_FOUR_WORDS(x0,x1,x2,x3,0);
        PACK_FOUR_WORDS(x4,x5,x6,x7,1);
        PACK_FOUR_WORDS(x8,x9,x10,x11,2);
        PACK_FOUR_WORDS(x12,x13,x14,x15,3);
        #undef PACK_FOUR_WORDS
        #define STORE_STREAM(s) \
        { \
            __m512i a=_mm512_shuffle_i32x4(group[0][s],group[1][s],0x44); \
            __m512i b=_mm512_shuffle_i32x4(group[2][s],group[3][s],0x44); \
            __m512i c=_mm512_shuffle_i32x4(group[0][s],group[1][s],0xee); \
            __m512i d=_mm512_shuffle_i32x4(group[2][s],group[3][s],0xee); \
            _mm512_storeu_si512((void*)(outputs[s]+0),_mm512_shuffle_i32x4(a,b,0x88)); \
            _mm512_storeu_si512((void*)(outputs[s]+64),_mm512_shuffle_i32x4(a,b,0xdd)); \
            _mm512_storeu_si512((void*)(outputs[s]+128),_mm512_shuffle_i32x4(c,d,0x88)); \
            _mm512_storeu_si512((void*)(outputs[s]+192),_mm512_shuffle_i32x4(c,d,0xdd)); \
        }
        STORE_STREAM(0);
        STORE_STREAM(1);
        STORE_STREAM(2);
        STORE_STREAM(3);
        #undef STORE_STREAM

        outputs[0] += 256;
        outputs[1] += 256;
        outputs[2] += 256;
        outputs[3] += 256;
        counter_base += 4;
    }


}

#endif
