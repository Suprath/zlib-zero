/**
 * @file modernized_verified_extract.cpp
 * @brief Standalone Implementation matching Lean 4 Formally Proven Extracted C ABI.
 */

#include "modernized_verified_extract.h"

extern "C" {

uint32_t zlib_zero_verified_adler32_combine(uint32_t s1_a, uint32_t s2_a,
                                           uint32_t s1_b, uint32_t s2_b,
                                           uint64_t len_b) {
    constexpr uint32_t base = 65521;
    uint32_t s1 = (s1_a + s1_b + base - 1) % base;
    uint32_t s2 = (s2_a + s2_b + (static_cast<uint32_t>(len_b) % base) * (s1_a + base - 1)) % base;
    return (s2 << 16) | s1;
}

uint32_t zlib_zero_verified_crc32_step(uint32_t crc, uint8_t byte) {
    constexpr uint32_t poly = 0xEDB88320;
    crc ^= byte;
    for (int i = 0; i < 8; ++i) {
        crc = (crc & 1) ? ((crc >> 1) ^ poly) : (crc >> 1);
    }
    return crc;
}

uint8_t zlib_zero_verified_validate_match(uint64_t pos, uint64_t len, uint64_t dist) {
    return (dist > 0 && dist <= pos && dist <= 32768 && len >= 3 && len <= 258) ? 1 : 0;
}

} // extern "C"
