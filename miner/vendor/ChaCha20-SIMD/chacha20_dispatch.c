#include "cpu_features.h"
#include "chacha20.h"

static bool initialized = false;
static cpu_features_t f;

void chacha_init(void)
{
    get_cpu_features(&f);

    /* JayXelis Next: raw CPUID alone does not establish OS YMM support.
     * GCC/Clang's built-in check includes the required OS state support. */
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
    __builtin_cpu_init();
    f.HW_AVX2 = f.HW_AVX2 && __builtin_cpu_supports("avx2");
#endif

    initialized = true;
}

void chacha_encrypt(uint8_t *key, uint8_t *nonce, uint8_t *in, uint8_t *out, size_t bytes, uint32_t rounds)
{

    if (!initialized)
    {
        chacha_init();
    }

    if (f.HW_AVX2)
    {
        chacha_encrypt_avx2(key, nonce, in, out, bytes, rounds);
        return;
    }

    if (f.HW_SSE2)
    {
        chacha_encrypt_sse2(key, nonce, in, out, bytes, rounds);
        return;
    }

    chacha_encrypt_portable(key, nonce, in, out, bytes, rounds);
}
