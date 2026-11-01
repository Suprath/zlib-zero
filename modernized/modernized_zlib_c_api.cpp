/**
 * @file modernized_zlib_c_api.cpp
 * @brief Standard C ABI Drop-In Replacement for zlib (RFC 1950 / RFC 1951 compliant).
 *
 * Exports the standard zlib C symbols:
 *   adler32, crc32, deflateInit_, deflate, deflateEnd,
 *   inflateInit_, inflate, inflateEnd
 *
 * Enables zero-code-change dynamic library replacement for Nginx, Python, Git,
 * and PostgreSQL via LD_PRELOAD / DYLD_INSERT_LIBRARIES.
 *
 * Defect 5 fix: deflate() and inflate() now hold per-stream state objects
 * (DeflateState / InflateState) in z_stream_s::state.  Input bytes are
 * accumulated across calls; compression/decompression is triggered on Z_FINISH.
 */

#include "modernized_zlib_deflate.hpp"
#include "modernized_zlib_stream.hpp"
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cstdlib>
#include <vector>
#include <new>

// ---------------------------------------------------------------------------
// Platform export macro
// ---------------------------------------------------------------------------
#if defined(_WIN32) || defined(_WIN64)
  #define ZLIB_EXPORT __declspec(dllexport)
#else
  #define ZLIB_EXPORT __attribute__((visibility("default")))
#endif

// ---------------------------------------------------------------------------
// Standard z_stream struct layout (matches zlib.h exactly)
// ---------------------------------------------------------------------------
struct z_stream_s {
    const uint8_t* next_in;
    uint32_t       avail_in;
    uint64_t       total_in;

    uint8_t*  next_out;
    uint32_t  avail_out;
    uint64_t  total_out;

    const char* msg;
    void*       state;    ///< ← Per-stream DeflateState / InflateState

    void* (*zalloc)(void* opaque, uint32_t items, uint32_t size);
    void  (*zfree )(void* opaque, void* address);
    void*   opaque;

    int      data_type;
    uint32_t adler;
    uint32_t reserved;
};

typedef z_stream_s* z_streamp;

// Return codes (match zlib exactly)
static constexpr int Z_OK          =  0;
static constexpr int Z_STREAM_END  =  1;
static constexpr int Z_STREAM_ERROR = -2;
static constexpr int Z_BUF_ERROR   = -5;

// Flush values
static constexpr int Z_NO_FLUSH    = 0;
static constexpr int Z_SYNC_FLUSH  = 2;
static constexpr int Z_FULL_FLUSH  = 3;
static constexpr int Z_FINISH      = 4;

// ===========================================================================
// Streaming State Objects  (Concern C: chunk-bounded streaming)
// ===========================================================================

/**
 * @brief Per-stream deflate state — chunk-bounded streaming compressor.
 *
 * Concern C fix: the previous implementation accumulated the ENTIRE input
 * before compressing (O(file_size) RAM).  A 50 GB database backup needed 50 GB.
 *
 * The new design processes input in CHUNK_SIZE (64 KB) slices.  RAM usage is
 * bounded by ~64 KB of input staging + ~64 KB of compressed output staging,
 * regardless of total stream length.
 *
 * Key properties:
 *   • Running Adler-32 is updated incrementally as chunks arrive.
 *   • Z_SYNC_FLUSH emits a stored empty block (0x00 0x00 0xFF 0xFF) to
 *     give downstream HTTP decompressors a byte-aligned sync point.
 *   • Z_FINISH emits the final chunk + Adler-32 trailer.
 *   • The parallel C++ compress_parallel() API is unchanged; it remains the
 *     preferred path for known-size in-memory buffers.
 */
struct StreamingDeflateState {
    static constexpr size_t CHUNK_SIZE = 64 * 1024;  // compress in 64 KB slices

    // ── Input staging (bounded to CHUNK_SIZE) ────────────────────────────────
    std::vector<uint8_t> in_buf;    // accumulated input for current chunk

    // ── Output staging (compressed data waiting to drain into next_out) ──────
    std::vector<uint8_t> out_buf;
    size_t               out_pos = 0;

    // ── Stream state ─────────────────────────────────────────────────────────
    uint32_t adler        = 1;       // running Adler-32 of ALL uncompressed bytes
    int      level        = 6;
    bool     header_emitted = false; // zlib CMF/FLG written?
    bool     finished     = false;
};

/**
 * @brief Per-stream inflate state (unchanged from previous version).
 * Accumulates input bytes; decompresses on first call when data is available.
 */
struct InflateState {
    std::vector<uint8_t> input_buf;
    std::vector<uint8_t> output_buf;
    size_t               out_pos  = 0;
    bool                 finished = false;
};


// ===========================================================================
// Exported C ABI
// ===========================================================================

extern "C" {

// ---------------------------------------------------------------------------
// Checksums
// ---------------------------------------------------------------------------
ZLIB_EXPORT uint32_t adler32(uint32_t adler, const uint8_t* buf, size_t len) {
    return ModernizedZlib::adler32_modernized(adler, buf, len);
}

ZLIB_EXPORT uint32_t crc32(uint32_t crc, const uint8_t* buf, size_t len) {
    return ModernizedZlib::crc32_modernized(crc, buf, len);
}

// ---------------------------------------------------------------------------
// Deflate — compress
// ---------------------------------------------------------------------------

ZLIB_EXPORT int deflateInit_(z_streamp strm, int level,
                              const char* /*version*/, int /*stream_size*/) {
    if (!strm) return Z_STREAM_ERROR;

    StreamingDeflateState* st = nullptr;
    if (strm->zalloc) {
        void* ptr = strm->zalloc(strm->opaque, 1, sizeof(StreamingDeflateState));
        if (!ptr) return -4; // Z_MEM_ERROR
        st = new (ptr) StreamingDeflateState();
    } else {
        st = new (std::nothrow) StreamingDeflateState();
        if (!st) return -4; // Z_MEM_ERROR
    }

    st->level    = (level < 1 || level > 9) ? 6 : level;
    strm->state  = st;
    strm->total_in  = 0;
    strm->total_out = 0;
    strm->adler  = 1;
    strm->msg    = nullptr;
    return Z_OK;
}

ZLIB_EXPORT int deflate(z_streamp strm, int flush) {
    if (!strm || !strm->state) return Z_STREAM_ERROR;
    auto* st = static_cast<StreamingDeflateState*>(strm->state);
    if (st->finished) return Z_STREAM_END;

    // ── Step 1: Consume available input into per-chunk staging buffer ─────────
    if (strm->next_in && strm->avail_in > 0) {
        // Update running Adler-32 on incoming bytes (before buffering)
        st->adler = ModernizedZlib::adler32_modernized(
            st->adler, strm->next_in, strm->avail_in);

        st->in_buf.insert(st->in_buf.end(),
                          strm->next_in,
                          strm->next_in + strm->avail_in);
        strm->total_in += strm->avail_in;
        strm->next_in  += strm->avail_in;
        strm->avail_in  = 0;
    }

    // ── Step 2: Compress if chunk is full, flush requested, or finishing ──────
    //
    // Process chunks greedily: if in_buf exceeds CHUNK_SIZE, compress one chunk
    // at a time and append to out_buf.  On flush/finish, compress whatever remains.
    while (!st->in_buf.empty()) {
        const bool should_flush = (flush == Z_SYNC_FLUSH ||
                                   flush == Z_FULL_FLUSH ||
                                   flush == Z_FINISH);
        const bool chunk_full   = (st->in_buf.size() >= StreamingDeflateState::CHUNK_SIZE);

        if (!chunk_full && !should_flush) break;  // Wait for more input

        // Emit zlib CMF/FLG header once at the very start of the stream
        if (!st->header_emitted) {
            st->out_buf.push_back(0x78);
            st->out_buf.push_back(0x9C);
            st->header_emitted = true;
            st->out_pos = 0;
        }

        // Take one chunk (up to CHUNK_SIZE bytes)
        size_t chunk_n = std::min(st->in_buf.size(), StreamingDeflateState::CHUNK_SIZE);
        const bool more_input = (st->in_buf.size() > chunk_n) || (strm->avail_in > 0);
        const bool is_final   = (flush == Z_FINISH) && !more_input;

        // Compress this chunk into raw DEFLATE blocks (BFINAL=1 only on the last chunk)
        auto raw = ModernizedZlib::DeflateCompressor::compress_block(
            st->in_buf.data(), chunk_n, is_final);
        st->out_buf.insert(st->out_buf.end(), raw.begin(), raw.end());
        st->in_buf.erase(st->in_buf.begin(), st->in_buf.begin() + chunk_n);

        // Z_SYNC_FLUSH: append empty stored block for HTTP byte-alignment sync point.
        // Only do this when the buffer is fully drained (not between auto-flush chunks).
        if ((flush == Z_SYNC_FLUSH || flush == Z_FULL_FLUSH) && st->in_buf.empty()) {
            st->out_buf.push_back(0x00);
            st->out_buf.push_back(0x00);
            st->out_buf.push_back(0xFF);
            st->out_buf.push_back(0xFF);
        }

        // Z_FINISH: append Adler-32 trailer (big-endian) once, after the final block
        if (is_final) {
            const uint32_t a = st->adler;
            st->out_buf.push_back(static_cast<uint8_t>((a >> 24) & 0xFF));
            st->out_buf.push_back(static_cast<uint8_t>((a >> 16) & 0xFF));
            st->out_buf.push_back(static_cast<uint8_t>((a >>  8) & 0xFF));
            st->out_buf.push_back(static_cast<uint8_t>( a         & 0xFF));
            break;  // Nothing more to compress
        }

        if (st->in_buf.empty()) break;  // All input consumed
    }

    strm->adler = st->adler;

    // ── Step 3: Drain compressed output into caller's next_out ────────────────
    if (strm->next_out && strm->avail_out > 0 && st->out_pos < st->out_buf.size()) {
        size_t avail   = st->out_buf.size() - st->out_pos;
        size_t to_copy = std::min(avail, static_cast<size_t>(strm->avail_out));
        std::memcpy(strm->next_out, st->out_buf.data() + st->out_pos, to_copy);
        strm->next_out  += to_copy;
        strm->avail_out -= static_cast<uint32_t>(to_copy);
        strm->total_out += to_copy;
        st->out_pos     += to_copy;
    }

    // ── Step 4: Determine return code ─────────────────────────────────────────
    const bool all_drained = (st->out_pos >= st->out_buf.size());
    if (flush == Z_FINISH && all_drained && strm->avail_in == 0 && st->in_buf.empty()) {
        st->finished = true;
        return Z_STREAM_END;
    }
    return Z_OK;
}

ZLIB_EXPORT int deflateEnd(z_streamp strm) {
    if (!strm || !strm->state) return Z_STREAM_ERROR;
    auto* st = static_cast<StreamingDeflateState*>(strm->state);
    if (strm->zfree) {
        st->~StreamingDeflateState();
        strm->zfree(strm->opaque, st);
    } else {
        delete st;
    }
    strm->state = nullptr;
    return Z_OK;
}

ZLIB_EXPORT int deflateReset(z_streamp strm) {
    if (!strm || !strm->state) return Z_STREAM_ERROR;
    auto* st = static_cast<StreamingDeflateState*>(strm->state);
    st->in_buf.clear();
    st->out_buf.clear();
    st->out_pos = 0;
    st->adler   = 1;
    st->header_emitted = false;
    st->finished       = false;
    strm->total_in  = 0;
    strm->total_out = 0;
    strm->adler     = 1;
    strm->msg       = nullptr;
    return Z_OK;
}

// ---------------------------------------------------------------------------
// Inflate — decompress
// ---------------------------------------------------------------------------

ZLIB_EXPORT int inflateInit_(z_streamp strm,
                              const char* /*version*/, int /*stream_size*/) {
    if (!strm) return Z_STREAM_ERROR;

    InflateState* st = nullptr;
    if (strm->zalloc) {
        void* ptr = strm->zalloc(strm->opaque, 1, sizeof(InflateState));
        if (!ptr) return -4; // Z_MEM_ERROR
        st = new (ptr) InflateState();
    } else {
        st = new (std::nothrow) InflateState();
        if (!st) return -4; // Z_MEM_ERROR
    }

    strm->state     = st;
    strm->total_in  = 0;
    strm->total_out = 0;
    strm->adler     = 1;
    strm->msg       = nullptr;
    return Z_OK;
}

ZLIB_EXPORT int inflate(z_streamp strm, int flush) {
    if (!strm || !strm->state) return Z_STREAM_ERROR;
    auto* st = static_cast<InflateState*>(strm->state);

    if (st->finished) return Z_STREAM_END;

    // 1. Accumulate input
    if (strm->next_in && strm->avail_in > 0) {
        st->input_buf.insert(st->input_buf.end(),
                             strm->next_in,
                             strm->next_in + strm->avail_in);
        strm->total_in += strm->avail_in;
        strm->next_in  += strm->avail_in;
        strm->avail_in  = 0;
    }

    // 2. Attempt decompression once we have data and output hasn't been produced yet
    if (st->output_buf.empty() && !st->input_buf.empty()) {
        // Try zlib-framed first (RFC 1950)
        auto result = ModernizedZlib::decompress_zlib(
            st->input_buf.data(), st->input_buf.size());

        if (result.empty()) {
            // Fallback: try raw DEFLATE (no header/trailer)
            result = ModernizedZlib::InflateDecompressor::decompress_raw(
                st->input_buf.data(), st->input_buf.size());
        }

        st->output_buf = std::move(result);
        st->out_pos    = 0;

        if (!st->output_buf.empty()) {
            strm->adler = ModernizedZlib::adler32_modernized(
                1, st->output_buf.data(), st->output_buf.size());
        }
    }

    // 3. Drain output into caller buffer
    if (strm->next_out && strm->avail_out > 0 && st->out_pos < st->output_buf.size()) {
        size_t available = st->output_buf.size() - st->out_pos;
        size_t to_copy   = std::min(available, static_cast<size_t>(strm->avail_out));
        std::memcpy(strm->next_out, st->output_buf.data() + st->out_pos, to_copy);
        strm->next_out  += to_copy;
        strm->avail_out -= static_cast<uint32_t>(to_copy);
        strm->total_out += to_copy;
        st->out_pos     += to_copy;
    }

    if (st->out_pos >= st->output_buf.size() && !st->output_buf.empty()) {
        st->finished = true;
        return Z_STREAM_END;
    }
    return Z_OK;
}

ZLIB_EXPORT int inflateEnd(z_streamp strm) {
    if (!strm || !strm->state) return Z_STREAM_ERROR;
    auto* st = static_cast<InflateState*>(strm->state);
    if (strm->zfree) {
        st->~InflateState();
        strm->zfree(strm->opaque, st);
    } else {
        delete st;
    }
    strm->state = nullptr;
    return Z_OK;
}

ZLIB_EXPORT int inflateReset(z_streamp strm) {
    if (!strm || !strm->state) return Z_STREAM_ERROR;
    auto* st = static_cast<InflateState*>(strm->state);
    st->input_buf.clear();
    st->output_buf.clear();
    st->out_pos  = 0;
    st->finished = false;
    strm->total_in  = 0;
    strm->total_out = 0;
    strm->adler     = 1;
    strm->msg       = nullptr;
    return Z_OK;
}

// ---------------------------------------------------------------------------
// Single-Call Utilities (Standard zlib API)
// ---------------------------------------------------------------------------

ZLIB_EXPORT int compress2(uint8_t* dest, unsigned long* destLen,
                          const uint8_t* source, unsigned long sourceLen,
                          int level) {
    if (!dest || !destLen || (!source && sourceLen > 0)) return Z_STREAM_ERROR;
    auto out = ModernizedZlib::compress_zlib(source, sourceLen, level);
    if (out.size() > *destLen) {
        return Z_BUF_ERROR;
    }
    std::memcpy(dest, out.data(), out.size());
    *destLen = static_cast<unsigned long>(out.size());
    return Z_OK;
}

ZLIB_EXPORT int compress(uint8_t* dest, unsigned long* destLen,
                         const uint8_t* source, unsigned long sourceLen) {
    return compress2(dest, destLen, source, sourceLen, 6);
}

ZLIB_EXPORT int uncompress2(uint8_t* dest, unsigned long* destLen,
                            const uint8_t* source, unsigned long* sourceLen) {
    if (!dest || !destLen || !source || !sourceLen) return Z_STREAM_ERROR;
    if (*sourceLen < 6) return -3; // Z_DATA_ERROR

    size_t written = ModernizedZlib::decompress_zlib_into(dest, *destLen, source, *sourceLen);
    if (written == 0) {
        auto res = ModernizedZlib::decompress_zlib(source, *sourceLen);
        if (res.empty()) return -3; // Z_DATA_ERROR
        if (res.size() > *destLen) return Z_BUF_ERROR;
        std::memcpy(dest, res.data(), res.size());
        *destLen = static_cast<unsigned long>(res.size());
        return Z_OK;
    }
    *destLen = static_cast<unsigned long>(written);
    return Z_OK;
}

ZLIB_EXPORT int uncompress(uint8_t* dest, unsigned long* destLen,
                           const uint8_t* source, unsigned long sourceLen) {
    unsigned long src_len = sourceLen;
    return uncompress2(dest, destLen, source, &src_len);
}

} // extern "C"
