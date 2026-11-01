/**
 * @file modernized_zlib_stream.hpp
 * @brief High-Level C++20 Stream API for NeuralBinary Modernized zlib.
 *
 * Defect 4 fix: ZlibStream::compress_buffer() now calls the real RFC 1950
 * compress_zlib() pipeline instead of performing a raw memcopy.
 * ZlibStream::decompress_buffer() is also wired to decompress_zlib().
 */

#ifndef MODERNIZED_ZLIB_STREAM_HPP
#define MODERNIZED_ZLIB_STREAM_HPP

#include <cstdint>
#include <cstddef>
#include <vector>
#include <string>
#include <memory>

// Forward-declare the DEFLATE namespace functions so we avoid a circular include.
// The full definitions live in modernized_zlib_deflate.hpp which callers include
// before this header in translation units that need compression.
namespace ModernizedZlib {
    class DeflateCompressor;
    class ParallelDeflateCompressor;
    class DynamicHuffmanEncoder;
    class InflateDecompressor;

    std::vector<uint8_t> compress_zlib(const uint8_t* data, size_t len);
    std::vector<uint8_t> compress_zlib(const uint8_t* data, size_t len, int level);
    std::vector<uint8_t> decompress_zlib(const uint8_t* data, size_t len);

    enum class ZlibStatus {
        OK            =  0,
        STREAM_END    =  1,
        NEED_DICT     =  2,
        ERRNO         = -1,
        STREAM_ERROR  = -2,
        DATA_ERROR    = -3,
        MEM_ERROR     = -4,
        BUF_ERROR     = -5,
        VERSION_ERROR = -6
    };

    /**
     * @brief High-level C++20 zlib stream object.
     *
     * Provides single-call compress / decompress operations with automatic
     * RFC 1950 framing and Adler-32 integrity checking.
     */
    class ZlibStream {
    public:
        ZlibStream() : total_in_(0), total_out_(0), checksum_(1) {}

        void set_input(const uint8_t* data, size_t len) {
            input_data_ = data;
            input_len_  = len;
        }

        size_t   total_in()  const { return total_in_;  }
        size_t   total_out() const { return total_out_; }
        uint32_t checksum()  const { return checksum_;  }

        /**
         * @brief Compress @p in_buf into @p out_buf using zlib format (RFC 1950).
         * Wires into ParallelDeflateCompressor → compress_zlib() with full
         * Adler-32 trailer.  Defect 4 fix: no longer a raw memcopy stub.
         */
        ZlibStatus compress_buffer(const std::vector<uint8_t>& in_buf,
                                   std::vector<uint8_t>&        out_buf) {
            if (in_buf.empty()) {
                out_buf.clear();
                return ZlibStatus::OK;
            }

            out_buf    = compress_zlib(in_buf.data(), in_buf.size());
            total_in_  = in_buf.size();
            total_out_ = out_buf.size();

            // Recompute checksum from compressed output's Adler-32 trailer
            if (out_buf.size() >= 6) {
                size_t n = out_buf.size();
                checksum_ = (static_cast<uint32_t>(out_buf[n-4]) << 24) |
                            (static_cast<uint32_t>(out_buf[n-3]) << 16) |
                            (static_cast<uint32_t>(out_buf[n-2]) <<  8) |
                             static_cast<uint32_t>(out_buf[n-1]);
            }

            return out_buf.empty() ? ZlibStatus::MEM_ERROR : ZlibStatus::OK;
        }

        /**
         * @brief Decompress @p in_buf (zlib format) into @p out_buf.
         * Validates CMF/FLG header and Adler-32 trailer.
         */
        ZlibStatus decompress_buffer(const std::vector<uint8_t>& in_buf,
                                     std::vector<uint8_t>&        out_buf) {
            if (in_buf.empty()) {
                out_buf.clear();
                return ZlibStatus::OK;
            }

            out_buf    = decompress_zlib(in_buf.data(), in_buf.size());
            total_in_  = in_buf.size();
            total_out_ = out_buf.size();

            if (out_buf.empty() && !in_buf.empty())
                return ZlibStatus::DATA_ERROR;

            return ZlibStatus::OK;
        }

    private:
        const uint8_t* input_data_ = nullptr;
        size_t         input_len_  = 0;
        size_t         total_in_   = 0;
        size_t         total_out_  = 0;
        uint32_t       checksum_   = 1;
    };

} // namespace ModernizedZlib

#endif // MODERNIZED_ZLIB_STREAM_HPP
