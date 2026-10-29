#ifndef JAYXELIS_NEXT_RUNTIME_H
#define JAYXELIS_NEXT_RUNTIME_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Opaque, Linux/x86-64 worker engine. cpus may be NULL; -1 means unbound.
 * kernel: 0 reference, 1 baseline optimized, 2 experimental FP,
 *         3 experimental integer-square-root candidate.
 * page_mode: 0 ordinary pages, 1 try existing 2 MiB hugetlb pool with fallback.
 * Integer operations return 0 on success, -1 with errno on failure, except
 * nx_pop (1 share, 0 empty) and nx_pages (number of hugetlb workers).
 * The runtime must be destroyed only after other callers have stopped using it.
 */
void *nx_create(int threads, const int *cpus, int kernel, int page_mode);
void nx_destroy(void *runtime);
int nx_set_job(void *runtime, const uint8_t blob112[112],
               const uint8_t target32[32], uint64_t epoch,
               uint64_t nonce_start);
void nx_pause(void *runtime);
int nx_pop(void *runtime, uint64_t *epoch, uint64_t *nonce,
           uint8_t hash32[32]);
uint64_t nx_count(void *runtime);
uint64_t nx_dropped(void *runtime);
int nx_hash(const uint8_t blob112[112], uint8_t hash32[32], int kernel);
int nx_selftest(void);
int nx_pages(void *runtime);

/* The first job starts each worker at nonce_start + its worker index.
 * Workers advance by the fixed thread count throughout this runtime's life.
 * Later nonce_start values do not reset their streams. This deliberately
 * prevents replay when a header returns after intervening jobs, including
 * changes to labels, targets, and nonce bytes in the received header. A new
 * runtime starts a new nonce session and must receive a fresh nonce_start.
 * Nonces are encoded big-endian at bytes 40..47; exhaustion parks the worker.
 * nx_count includes every fully computed hash, including invalidated jobs.
 * nx_dropped counts shares dropped because a worker's bounded queue was full.
 * nx_pop has one consumer; job updates and pause invalidate queued old work.
 */

#ifdef __cplusplus
}
#endif
#endif
