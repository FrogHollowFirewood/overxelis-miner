/* Original JayXelis Next worker runtime. SPDX-License-Identifier: MIT
 * Consensus kernels are separate, attributed components. This file contains
 * no implementation copied from the earlier miner runtime.
 */
#define _GNU_SOURCE
#include "runtime.h"

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define NX_SCRATCH_BYTES ((size_t)543744)
#define NX_HUGE_BYTES ((size_t)2 * 1024 * 1024)
/* Experimental per-worker hugetlb layout; no page-locality claim. */
#define NX_COLOR_STRIDE ((size_t)4160)
#define NX_COLOR_WINDOW ((size_t)524288)
_Static_assert(NX_COLOR_STRIDE % 64 == 0, "color stride alignment");
_Static_assert(NX_COLOR_WINDOW % 64 == 0, "color window alignment");
_Static_assert(NX_COLOR_WINDOW - 64 + NX_SCRATCH_BYTES <= NX_HUGE_BYTES,
               "colored scratch must stay inside its mapping");
#define NX_RING_CAPACITY 128u
#define NX_MAX_THREADS 1024

extern void xelis_hash_v3(uint8_t *, uint8_t *, uint64_t *);
extern void xelis_hash_v3_opt(uint8_t *, uint8_t *, uint64_t *);
extern void xelis_hash_v3_experimental(uint8_t *, uint8_t *, uint64_t *);
extern void xelis_hash_v3_exp_sqrt(uint8_t *, uint8_t *, uint64_t *);
extern void chacha_init(void);

typedef void (*nx_kernel)(uint8_t *, uint8_t *, uint64_t *);
typedef struct nx_runtime nx_runtime;
static pthread_once_t nx_chacha_once = PTHREAD_ONCE_INIT;

typedef struct {
    uint64_t revision;
    uint64_t epoch;
    uint64_t nonce;
    uint8_t hash[32];
} nx_share;

typedef struct {
    /* Each hot atomic lives on its own cache line. Only this worker writes
     * completed/dropped/tail; the sole consumer writes head. */
    _Alignas(64) _Atomic uint64_t completed;
    _Alignas(64) _Atomic uint64_t dropped;
    _Alignas(64) _Atomic uint64_t head;
    _Alignas(64) _Atomic uint64_t tail;
    _Alignas(64) nx_share shares[NX_RING_CAPACITY];
    nx_runtime *owner;
    pthread_t thread;
    int cpu;
    unsigned ordinal;
    uint64_t next_nonce;
    bool exhausted;
    uint64_t *scratch;
    bool huge;
    void *scratch_mapping;
} nx_worker;

struct nx_runtime {
    pthread_mutex_t mutex;
    pthread_cond_t wake;
    _Atomic uint64_t revision;
    bool stop;
    bool active;
    bool nonce_ready;
    int threads;
    int started;
    int boot_done;
    int boot_error;
    int page_mode;
    int pop_cursor;
    nx_kernel hash;
    nx_worker *workers;
    uint8_t blob[112];
    uint8_t target[32];
    uint64_t epoch;
};


/* Cold topology helpers. Unsupported input always retains ordinal fallback. */
static bool nx_topology_space(char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static bool nx_topology_number(const char *text, size_t length,
                                size_t *position, int *value) {
    size_t p = *position;
    if (p >= length || text[p] < '0' || text[p] > '9') return false;
    unsigned n = 0;
    do {
        const unsigned digit = (unsigned)(text[p] - '0');
        if (n > ((unsigned)CPU_SETSIZE - 1u - digit) / 10u) return false;
        n = n * 10u + digit;
        ++p;
    } while (p < length && text[p] >= '0' && text[p] <= '9');
    *position = p;
    *value = (int)n;
    return true;
}

static bool nx_parse_sibling_key(const char *text, size_t length,
                                  int selected_cpu, int *key) {
    if (text == NULL || key == NULL || selected_cpu < 0 ||
        selected_cpu >= CPU_SETSIZE) return false;
    size_t p = 0;
    while (p < length && nx_topology_space(text[p])) ++p;
    int first = -1, previous_end = -1;
    bool contains_selected = false;
    for (;;) {
        int start, end;
        if (!nx_topology_number(text, length, &p, &start)) return false;
        end = start;
        if (p < length && text[p] == '-') {
            ++p;
            if (!nx_topology_number(text, length, &p, &end)) return false;
        }
        if (end < start || start <= previous_end) return false;
        if (first < 0) first = start;
        if (selected_cpu >= start && selected_cpu <= end) contains_selected = true;
        previous_end = end;
        if (p < length && text[p] == ',') {
            ++p;
            continue;
        }
        while (p < length && nx_topology_space(text[p])) ++p;
        if (p != length || !contains_selected) return false;
        *key = first;
        return true;
    }
}

static bool nx_topology_cpus_supported(int threads, const int *cpus) {
    if (threads < 1 || threads > NX_MAX_THREADS || cpus == NULL) return false;
    for (int i = 0; i < threads; ++i) {
        if (cpus[i] < 0 || cpus[i] >= CPU_SETSIZE) return false;
        for (int j = 0; j < i; ++j)
            if (cpus[i] == cpus[j]) return false;
    }
    return true;
}

static bool nx_build_topology_ordinals(int threads, const int *cpus,
                                        const int *keys, unsigned *colors) {
    if (!nx_topology_cpus_supported(threads, cpus) ||
        keys == NULL || colors == NULL) return false;
    int group_keys[NX_MAX_THREADS];
    unsigned group_counts[NX_MAX_THREADS];
    int groups = 0;
    for (int i = 0; i < threads; ++i) {
        if (keys[i] < 0 || keys[i] > cpus[i]) return false;
        int group = 0;
        while (group < groups && group_keys[group] != keys[i]) ++group;
        if (group == groups) {
            group_keys[groups] = keys[i];
            group_counts[groups] = 0;
            ++groups;
        }
        const unsigned rank = group_counts[group]++;
        colors[i] = (unsigned)(group % 16) + 16u * rank;
    }
    return true;
}

static ssize_t nx_topology_read(int fd, void *buffer, size_t count) {
    /* Bound EINTR retries as well as the amount read. */
    for (unsigned attempt = 0; attempt < 4; ++attempt) {
        ssize_t n = read(fd, buffer, count);
        if (n >= 0 || errno != EINTR) return n;
    }
    return -1;
}

static bool nx_read_sibling_key(int cpu, int *key) {
    if (cpu < 0 || cpu >= CPU_SETSIZE) return false;
    const char prefix[] = "/sys/devices/system/cpu/cpu";
    const char suffix[] = "/topology/thread_siblings_list";
    char path[96], digits[16];
    size_t used = sizeof(prefix) - 1, count = 0;
    unsigned number = (unsigned)cpu;
    do {
        digits[count++] = (char)('0' + number % 10u);
        number /= 10u;
    } while (number != 0);
    if (used + count + sizeof(suffix) > sizeof(path)) return false;
    memcpy(path, prefix, used);
    while (count != 0) path[used++] = digits[--count];
    memcpy(path + used, suffix, sizeof(suffix));

    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return false;
    char text[512], extra;
    ssize_t length = nx_topology_read(fd, text, sizeof(text));
    ssize_t trailing = length > 0 ? nx_topology_read(fd, &extra, 1) : -1;
    close(fd);
    if (length <= 0 || trailing != 0) return false;
    return nx_parse_sibling_key(text, (size_t)length, cpu, key);
}

static bool nx_assign_topology_ordinals(nx_worker *workers, int threads,
                                        const int *cpus) {
    if (!nx_topology_cpus_supported(threads, cpus)) return false;
    int keys[NX_MAX_THREADS];
    unsigned colors[NX_MAX_THREADS];
    for (int i = 0; i < threads; ++i)
        if (!nx_read_sibling_key(cpus[i], &keys[i])) return false;
    if (!nx_build_topology_ordinals(threads, cpus, keys, colors)) return false;
    /* Commit only after every read and parse succeeds: no partial remapping. */
    for (int i = 0; i < threads; ++i) workers[i].ordinal = colors[i];
    return true;
}

static bool nx_cpu_supported(void) {
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
    __builtin_cpu_init();
    return __builtin_cpu_supports("aes") != 0;
#else
    return false;
#endif
}

static nx_kernel nx_select_kernel(int kernel) {
    switch (kernel) {
    case 0: return xelis_hash_v3;
    case 1: return xelis_hash_v3_opt;
    case 2: return xelis_hash_v3_experimental;
    case 3: return xelis_hash_v3_exp_sqrt;
    default: return NULL;
    }
}

static uint64_t *nx_scratch_allocate(int page_mode, unsigned ordinal,
                                     bool *huge, void **mapping_base) {
    *huge = false;
    *mapping_base = NULL;
#if defined(MAP_HUGETLB)
    if (page_mode == 1) {
        int flags = MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB;
#if defined(MAP_HUGE_2MB)
        flags |= MAP_HUGE_2MB;
#elif defined(MAP_HUGE_SHIFT)
        flags |= (21 << MAP_HUGE_SHIFT);
#endif
        void *p = mmap(NULL, NX_HUGE_BYTES, PROT_READ | PROT_WRITE,
                       flags, -1, 0);
        if (p != MAP_FAILED) {
            const size_t offset = ((size_t)ordinal * NX_COLOR_STRIDE)
                                  % NX_COLOR_WINDOW;
            uint64_t *scratch = (uint64_t *)((uint8_t *)p + offset);
            *huge = true;
            *mapping_base = p;
            /* First touch remains in the already affinitized worker. */
            memset(scratch, 0, NX_SCRATCH_BYTES);
            return scratch;
        }
    }
#else
    (void)page_mode;
    (void)ordinal;
#endif
    void *p = NULL;
    int result = posix_memalign(&p, 64, NX_SCRATCH_BYTES);
    if (result != 0) {
        errno = result;
        return NULL;
    }
    memset(p, 0, NX_SCRATCH_BYTES);
    return p;
}

static void nx_scratch_free(nx_worker *worker) {
    if (worker->scratch == NULL) return;
    if (worker->huge) munmap(worker->scratch_mapping, NX_HUGE_BYTES);
    else free(worker->scratch);
    worker->scratch = NULL;
    worker->scratch_mapping = NULL;
}

static void nx_nonce_encode(uint8_t blob[112], uint64_t nonce) {
    for (unsigned i = 0; i < 8; ++i)
        blob[40 + i] = (uint8_t)(nonce >> (56 - 8 * i));
}

static bool nx_meets_target(const uint8_t hash[32],
                            const uint8_t target[32]) {
    /* Both are unsigned 256-bit integers, most-significant byte first. */
    return memcmp(hash, target, 32) <= 0;
}

static void nx_push_share(nx_worker *worker, uint64_t revision,
                          uint64_t epoch, uint64_t nonce,
                          const uint8_t hash[32], uint64_t *dropped) {
    uint64_t tail = atomic_load_explicit(&worker->tail, memory_order_relaxed);
    uint64_t head = atomic_load_explicit(&worker->head, memory_order_acquire);
    if (tail - head >= NX_RING_CAPACITY) {
        ++*dropped;
        atomic_store_explicit(&worker->dropped, *dropped, memory_order_relaxed);
        return;
    }
    nx_share *share = &worker->shares[tail % NX_RING_CAPACITY];
    share->revision = revision;
    share->epoch = epoch;
    share->nonce = nonce;
    memcpy(share->hash, hash, 32);
    atomic_store_explicit(&worker->tail, tail + 1, memory_order_release);
}

static void *nx_worker_main(void *opaque) {
    nx_worker *worker = opaque;
    nx_runtime *runtime = worker->owner;
    int startup_error = 0;
    if (worker->cpu >= 0) {
        cpu_set_t affinity;
        CPU_ZERO(&affinity);
        CPU_SET(worker->cpu, &affinity);
        startup_error = pthread_setaffinity_np(pthread_self(),
                                             sizeof(affinity), &affinity);
    }
    if (startup_error == 0) {
        worker->scratch = nx_scratch_allocate(runtime->page_mode, worker->ordinal,
                                              &worker->huge,
                                              &worker->scratch_mapping);
        if (worker->scratch == NULL) startup_error = errno ? errno : ENOMEM;
    }
    pthread_mutex_lock(&runtime->mutex);
    if (startup_error != 0 && runtime->boot_error == 0)
        runtime->boot_error = startup_error;
    ++runtime->boot_done;
    pthread_cond_broadcast(&runtime->wake);
    pthread_mutex_unlock(&runtime->mutex);
    if (startup_error != 0) return NULL;

    uint64_t completed = 0, dropped = 0;
    for (;;) {
        uint8_t blob[112], target[32];
        uint64_t epoch, revision;
        pthread_mutex_lock(&runtime->mutex);
        while (!runtime->stop && (!runtime->active || worker->exhausted))
            pthread_cond_wait(&runtime->wake, &runtime->mutex);
        if (runtime->stop) {
            pthread_mutex_unlock(&runtime->mutex);
            break;
        }
        memcpy(blob, runtime->blob, 112);
        memcpy(target, runtime->target, 32);
        epoch = runtime->epoch;
        revision = atomic_load_explicit(&runtime->revision,
                                       memory_order_relaxed);
        pthread_mutex_unlock(&runtime->mutex);

        while (atomic_load_explicit(&runtime->revision, memory_order_acquire)
               == revision) {
            const uint64_t nonce = worker->next_nonce;
            /* Reserve this value before hashing. Job changes consume but never
             * replay an in-flight nonce. Detect addition overflow, never wrap. */
            if (nonce > UINT64_MAX - (uint64_t)runtime->threads)
                worker->exhausted = true;
            else worker->next_nonce = nonce + (uint64_t)runtime->threads;
            nx_nonce_encode(blob, nonce);
            uint8_t result[32];
            runtime->hash(blob, result, worker->scratch);
            ++completed;
            atomic_store_explicit(&worker->completed, completed,
                                  memory_order_relaxed);
            if (atomic_load_explicit(&runtime->revision, memory_order_acquire)
                    == revision && nx_meets_target(result, target))
                nx_push_share(worker, revision, epoch, nonce, result, &dropped);
            if (worker->exhausted) break;
        }
    }
    return NULL;
}

void *nx_create(int threads, const int *cpus, int kernel, int page_mode) {
    nx_kernel hash = nx_select_kernel(kernel);
    if (threads < 1 || threads > NX_MAX_THREADS || hash == NULL ||
        page_mode < 0 || page_mode > 1) {
        errno = EINVAL;
        return NULL;
    }
    if (!nx_cpu_supported()) {
        errno = ENOTSUP;
        return NULL;
    }
    /* Vendor dispatch's lazy bool is not synchronized; initialize exactly once
     * before any workers or concurrent nx_hash calls can enter the kernels. */
    int init_result = pthread_once(&nx_chacha_once, chacha_init);
    if (init_result != 0) {
        errno = init_result;
        return NULL;
    }
    if (cpus != NULL) {
        cpu_set_t allowed;
        if (sched_getaffinity(0, sizeof(allowed), &allowed) != 0) return NULL;
        for (int i = 0; i < threads; ++i) {
            if (cpus[i] < -1 || cpus[i] >= CPU_SETSIZE ||
                (cpus[i] >= 0 && !CPU_ISSET(cpus[i], &allowed))) {
                errno = EINVAL;
                return NULL;
            }
        }
    }
    nx_runtime *runtime = calloc(1, sizeof(*runtime));
    if (runtime == NULL) return NULL;
    int result = pthread_mutex_init(&runtime->mutex, NULL);
    if (result != 0) {
        free(runtime);
        errno = result;
        return NULL;
    }
    result = pthread_cond_init(&runtime->wake, NULL);
    if (result != 0) {
        pthread_mutex_destroy(&runtime->mutex);
        free(runtime);
        errno = result;
        return NULL;
    }
    result = posix_memalign((void **)&runtime->workers, 64,
                           (size_t)threads * sizeof(nx_worker));
    if (result != 0) {
        pthread_cond_destroy(&runtime->wake);
        pthread_mutex_destroy(&runtime->mutex);
        free(runtime);
        errno = result;
        return NULL;
    }
    memset(runtime->workers, 0, (size_t)threads * sizeof(nx_worker));
    runtime->threads = threads;
    runtime->page_mode = page_mode;
    runtime->hash = hash;
    atomic_init(&runtime->revision, 1);
    for (int i = 0; i < threads; ++i) {
        nx_worker *worker = &runtime->workers[i];
        worker->owner = runtime;
        worker->cpu = cpus == NULL ? -1 : cpus[i];
        worker->ordinal = (unsigned)i;
        atomic_init(&worker->completed, 0);
        atomic_init(&worker->dropped, 0);
        atomic_init(&worker->head, 0);
        atomic_init(&worker->tail, 0);
    }
    /* Ordinary mode performs no topology reads. Any unavailable, unpinned,
     * duplicate, or malformed topology retains the original i ordinals. */
    if (page_mode == 1)
        (void)nx_assign_topology_ordinals(runtime->workers, threads, cpus);
    for (int i = 0; i < threads; ++i) {
        result = pthread_create(&runtime->workers[i].thread, NULL,
                                nx_worker_main, &runtime->workers[i]);
        if (result != 0) break;
        ++runtime->started;
    }
    pthread_mutex_lock(&runtime->mutex);
    while (runtime->boot_done < runtime->started)
        pthread_cond_wait(&runtime->wake, &runtime->mutex);
    if (result == 0) result = runtime->boot_error;
    pthread_mutex_unlock(&runtime->mutex);
    if (result != 0) {
        nx_destroy(runtime);
        errno = result;
        return NULL;
    }
    return runtime;
}

void nx_destroy(void *opaque) {
    nx_runtime *runtime = opaque;
    if (runtime == NULL) return;
    pthread_mutex_lock(&runtime->mutex);
    runtime->stop = true;
    runtime->active = false;
    atomic_fetch_add_explicit(&runtime->revision, 1, memory_order_release);
    pthread_cond_broadcast(&runtime->wake);
    pthread_mutex_unlock(&runtime->mutex);
    for (int i = 0; i < runtime->started; ++i)
        pthread_join(runtime->workers[i].thread, NULL);
    for (int i = 0; i < runtime->threads; ++i)
        nx_scratch_free(&runtime->workers[i]);
    free(runtime->workers);
    pthread_cond_destroy(&runtime->wake);
    pthread_mutex_destroy(&runtime->mutex);
    free(runtime);
}

int nx_set_job(void *opaque, const uint8_t blob112[112],
               const uint8_t target32[32], uint64_t epoch,
               uint64_t nonce_start) {
    nx_runtime *runtime = opaque;
    if (runtime == NULL || blob112 == NULL || target32 == NULL) {
        errno = EINVAL;
        return -1;
    }
    pthread_mutex_lock(&runtime->mutex);
    uint64_t revision = atomic_load_explicit(&runtime->revision,
                                             memory_order_relaxed);
    if (revision == UINT64_MAX || runtime->stop) {
        pthread_mutex_unlock(&runtime->mutex);
        errno = revision == UINT64_MAX ? EOVERFLOW : EINVAL;
        return -1;
    }
    if (!runtime->nonce_ready) {
        for (int i = 0; i < runtime->threads; ++i) {
            nx_worker *worker = &runtime->workers[i];
            if (nonce_start > UINT64_MAX - (uint64_t)i)
                worker->exhausted = true;
            else worker->next_nonce = nonce_start + (uint64_t)i;
        }
        runtime->nonce_ready = true;
    }
    memcpy(runtime->blob, blob112, 112);
    memcpy(runtime->target, target32, 32);
    runtime->epoch = epoch;
    runtime->active = true;
    atomic_store_explicit(&runtime->revision, revision + 1,
                          memory_order_release);
    pthread_cond_broadcast(&runtime->wake);
    pthread_mutex_unlock(&runtime->mutex);
    return 0;
}

void nx_pause(void *opaque) {
    nx_runtime *runtime = opaque;
    if (runtime == NULL) return;
    pthread_mutex_lock(&runtime->mutex);
    runtime->active = false;
    atomic_fetch_add_explicit(&runtime->revision, 1, memory_order_release);
    pthread_cond_broadcast(&runtime->wake);
    pthread_mutex_unlock(&runtime->mutex);
}

int nx_pop(void *opaque, uint64_t *epoch, uint64_t *nonce, uint8_t hash32[32]) {
    nx_runtime *runtime = opaque;
    if (runtime == NULL || epoch == NULL || nonce == NULL || hash32 == NULL) {
        errno = EINVAL;
        return -1;
    }
    pthread_mutex_lock(&runtime->mutex);
    const uint64_t revision = atomic_load_explicit(&runtime->revision,
                                                  memory_order_acquire);
    for (int step = 0; step < runtime->threads; ++step) {
        int index = (runtime->pop_cursor + step) % runtime->threads;
        nx_worker *worker = &runtime->workers[index];
        uint64_t head = atomic_load_explicit(&worker->head,
                                             memory_order_relaxed);
        uint64_t tail = atomic_load_explicit(&worker->tail, memory_order_acquire);
        while (head != tail) {
            const nx_share share = worker->shares[head % NX_RING_CAPACITY];
            ++head;
            atomic_store_explicit(&worker->head, head, memory_order_release);
            if (runtime->active && share.revision == revision) {
                *epoch = share.epoch;
                *nonce = share.nonce;
                memcpy(hash32, share.hash, 32);
                runtime->pop_cursor = (index + 1) % runtime->threads;
                pthread_mutex_unlock(&runtime->mutex);
                return 1;
            }
        }
    }
    pthread_mutex_unlock(&runtime->mutex);
    return 0;
}

uint64_t nx_count(void *opaque) {
    nx_runtime *runtime = opaque;
    if (runtime == NULL) return 0;
    uint64_t total = 0;
    for (int i = 0; i < runtime->threads; ++i)
        total += atomic_load_explicit(&runtime->workers[i].completed,
                                      memory_order_relaxed);
    return total;
}

uint64_t nx_dropped(void *opaque) {
    nx_runtime *runtime = opaque;
    if (runtime == NULL) return 0;
    uint64_t total = 0;
    for (int i = 0; i < runtime->threads; ++i)
        total += atomic_load_explicit(&runtime->workers[i].dropped,
                                      memory_order_relaxed);
    return total;
}

int nx_pages(void *opaque) {
    nx_runtime *runtime = opaque;
    if (runtime == NULL) return 0;
    int total = 0;
    /* Page decisions finish before nx_create returns and never change. */
    for (int i = 0; i < runtime->threads; ++i)
        if (runtime->workers[i].huge) ++total;
    return total;
}

int nx_hash(const uint8_t blob112[112], uint8_t hash32[32], int kernel) {
    nx_kernel hash = nx_select_kernel(kernel);
    if (blob112 == NULL || hash32 == NULL || hash == NULL) {
        errno = EINVAL;
        return -1;
    }
    if (!nx_cpu_supported()) {
        errno = ENOTSUP;
        return -1;
    }
    int init_result = pthread_once(&nx_chacha_once, chacha_init);
    if (init_result != 0) {
        errno = init_result;
        return -1;
    }
    bool huge;
    void *scratch_mapping;
    uint64_t *scratch = nx_scratch_allocate(0, 0, &huge, &scratch_mapping);
    if (scratch == NULL) return -1;
    uint8_t blob[112];
    memcpy(blob, blob112, 112);
    hash(blob, hash32, scratch);
    free(scratch);
    return 0;
}

static uint8_t nx_hex_digit(char c) {
    return (uint8_t)(c <= '9' ? c - '0' : c - 'a' + 10);
}

static void nx_hex_decode(const char *hex, uint8_t *bytes, size_t count) {
    for (size_t i = 0; i < count; ++i)
        bytes[i] = (uint8_t)((nx_hex_digit(hex[2 * i]) << 4) |
                             nx_hex_digit(hex[2 * i + 1]));
}

int nx_selftest(void) {
    /* Fixed outputs from official Rust source, independent of the C reference.
     * Provenance: reference/provenance.json, xelis-hash commit f48262b931438fd.
     * Larger randomized differential tests remain in the external suite. */
    static const char *expected_vectors[2] = {
        "69ac67285efd5ca22afc05c4ecee5bda169de4e9ef08fa39d4a6798494cd67a3",
        "f208b0decb1b68bb162844494f4f41538a650a74c22999155ca30ccee79c4653"
    };
    static const char nonzero_input[] =
        "acec6cd4b51f6d2d2cf236e18f85592cb36c27bf2074e5213f822178b959928d"
        "0a4fb76bee7a5cde19865a6b746eec35ff05d67e18d861c794effd66c7b8e8fd"
        "9e9156bb70514e46506e21259fe9c601b26cd2646d9b6a7c7c535932c573e720"
        "4a025c2f19dc87f97aacdc898fea44bc";
    uint8_t blob[112], expected[32], result[32];
    for (unsigned vector = 0; vector < 2; ++vector) {
        if (vector == 0) memset(blob, 0, sizeof(blob));
        else nx_hex_decode(nonzero_input, blob, sizeof(blob));
        nx_hex_decode(expected_vectors[vector], expected, sizeof(expected));
        for (int kernel = 0; kernel <= 3; ++kernel) {
            if (nx_hash(blob, result, kernel) != 0) return -1;
            if (memcmp(expected, result, 32) != 0) {
                errno = EILSEQ;
                return -1;
            }
        }
    }
    for (unsigned pattern = 1; pattern < 3; ++pattern) {
        for (unsigned i = 0; i < sizeof(blob); ++i)
            blob[i] = pattern == 0 ? 0 :
                (pattern == 1 ? (uint8_t)i : (uint8_t)(i * 173 + 91));
        if (nx_hash(blob, expected, 0) != 0) return -1;
        for (int kernel = 1; kernel <= 3; ++kernel) {
            if (nx_hash(blob, result, kernel) != 0) return -1;
            if (memcmp(expected, result, 32) != 0) {
                errno = EILSEQ;
                return -1;
            }
        }
    }
    return 0;
}
