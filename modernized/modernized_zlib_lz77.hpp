#ifndef MODERNIZED_ZLIB_LZ77_HPP
#define MODERNIZED_ZLIB_LZ77_HPP

#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <cstdint>
#include <cstddef>
#include <cstring>

#if defined(_MSC_VER) && !defined(__clang__)
#include <intrin.h>
static inline unsigned int msvc_ctz32(unsigned int mask) {
    unsigned long index = 0;
    _BitScanForward(&index, mask);
    return static_cast<unsigned int>(index);
}
#ifndef __builtin_ctz
#define __builtin_ctz(x) msvc_ctz32(x)
#endif
#endif

#if defined(__ARM_NEON) || defined(__aarch64__) || defined(_M_ARM64)
#include <arm_neon.h>
#elif defined(__AVX2__)
#include <immintrin.h>
#endif

namespace ModernizedZlib {

constexpr size_t WINDOW_SIZE = 32768; // 32KB DEFLATE sliding window
constexpr size_t MAX_MATCH = 258;      // Standard maximum LZ77 match length
constexpr size_t MIN_MATCH = 3;        // Standard minimum LZ77 match length

/**
 * @brief High-Performance 16-Byte SIMD LZ77 Match Scanner with L1 Hardware Prefetching.
 * Scans 16 bytes per clock cycle using ARM NEON / AVX2 vector instructions and L1 cache prefetching.
 */
inline size_t longest_match_fast(const uint8_t* __restrict str1,
                                 const uint8_t* __restrict str2,
                                 size_t max_len) {
    if (max_len > MAX_MATCH) max_len = MAX_MATCH;
    size_t match_len = 0;

    // Hardware L1 CPU Cache Prefetching
#if defined(__GNUC__) || defined(__clang__)
    __builtin_prefetch(str1 + 64, 0, 3);
    __builtin_prefetch(str2 + 64, 0, 3);
#endif

#if defined(__ARM_NEON) || defined(__aarch64__) || defined(_M_ARM64)
    // -------------------------------------------------------------------------
    // 1. ARM NEON 16-Byte SIMD Vector Match Scanner
    // -------------------------------------------------------------------------
    while (match_len + 16 <= max_len) {
        uint8x16_t v1 = vld1q_u8(str1 + match_len);
        uint8x16_t v2 = vld1q_u8(str2 + match_len);
        uint8x16_t cmp = vceqq_u8(v1, v2);

        // Check if all 16 bytes match
        uint64x2_t cmp64 = vreinterpretq_u64_u8(cmp);
        if (vgetq_lane_u64(cmp64, 0) == ~0ULL && vgetq_lane_u64(cmp64, 1) == ~0ULL) {
            match_len += 16;
        } else {
            // Found mismatch in this 16-byte block
            while (match_len < max_len && str1[match_len] == str2[match_len]) {
                match_len++;
            }
            return match_len;
        }
    }
#elif defined(__AVX2__)
    // -------------------------------------------------------------------------
    // 2. x86_64 AVX2 32-Byte Vector Match Scanner
    // -------------------------------------------------------------------------
    while (match_len + 32 <= max_len) {
        __m256i v1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(str1 + match_len));
        __m256i v2 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(str2 + match_len));
        __m256i cmp = _mm256_cmpeq_epi8(v1, v2);
        unsigned int mask = _mm256_movemask_epi8(cmp);
        if (mask == 0xFFFFFFFFU) {
            match_len += 32;
        } else {
            match_len += __builtin_ctz(~mask);
            return match_len;
        }
    }
#endif

    // -------------------------------------------------------------------------
    // 3. 64-Bit Word Scalar Fallback Scanner
    // -------------------------------------------------------------------------
    while (match_len + 8 <= max_len) {
        uint64_t w1, w2;
        std::memcpy(&w1, str1 + match_len, sizeof(uint64_t));
        std::memcpy(&w2, str2 + match_len, sizeof(uint64_t));
        uint64_t diff = w1 ^ w2;
        if (diff != 0) {
#if defined(__GNUC__) || defined(__clang__)
            match_len += (__builtin_ctzll(diff) >> 3);
#elif defined(_MSC_VER)
            unsigned long index = 0;
            _BitScanForward64(&index, diff);
            match_len += (index >> 3);
#else
            while (match_len < max_len && str1[match_len] == str2[match_len]) match_len++;
#endif
            return match_len;
        }
        match_len += 8;
    }

    while (match_len < max_len && str1[match_len] == str2[match_len]) {
        match_len++;
    }

    return match_len;
}

} // namespace ModernizedZlib

#endif // MODERNIZED_ZLIB_LZ77_HPP
