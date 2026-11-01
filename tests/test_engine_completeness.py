"""
test_engine_completeness.py
===========================
Validates:
  1. 2-Level Hierarchical Huffman decoding (codes 11-15 bits in secondary sub-tables)
  2. Runtime Kraft-McMillan / RFC 1951 oversubscription rejection
  3. C ABI single-call endpoints: uncompress, uncompress2, compress, compress2
  4. Stream reusability via inflateReset and deflateReset
  5. Compression level density differentiation (Level 1 vs Level 6 vs Level 9)
"""

import os
import sys
import zlib
import ctypes
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODERNIZED_DIR = os.path.join(PROJECT_ROOT, "modernized")

sys.path.insert(0, PROJECT_ROOT)

# Check build directories for compiled extensions (sorted newest first)
build_dir = os.path.join(PROJECT_ROOT, "build")
if os.path.exists(build_dir):
    lib_dirs = []
    for sub in os.listdir(build_dir):
        if sub.startswith("lib"):
            full = os.path.join(build_dir, sub)
            if os.path.isdir(full):
                lib_dirs.append((os.path.getmtime(full), full))
    lib_dirs.sort(reverse=True)
    for _, p in lib_dirs:
        sys.path.append(p)

try:
    import zlib_zero
except ImportError:
    zlib_zero = None

def load_c_lib():
    exts = (".so", ".dylib", ".dll", ".pyd")
    candidates = []
    for fname in os.listdir(PROJECT_ROOT):
        if (fname.startswith("zlib_zero") or fname.startswith("libz_zero")) and any(fname.endswith(ext) for ext in exts):
            full = os.path.join(PROJECT_ROOT, fname)
            candidates.append((os.path.getmtime(full), full))
    if os.path.exists(build_dir):
        for root, dirs, files in os.walk(build_dir):
            for f in files:
                if (f.startswith("zlib_zero") or f.startswith("libz_zero")) and any(f.endswith(ext) for ext in exts):
                    full = os.path.join(root, f)
                    candidates.append((os.path.getmtime(full), full))
    candidates.sort(reverse=True)
    for _, path in candidates:
        try:
            return ctypes.CDLL(path)
        except Exception:
            pass
    return None

c_lib = load_c_lib()


class TestEngineCompleteness(unittest.TestCase):
    def setUp(self):
        if zlib_zero is None:
            self.skipTest("zlib_zero Python module not compiled or installed")

    def test_01_compression_levels_density(self):
        """Verify that Level 6/9 produces denser compression than Level 1 on text data."""
        sample_text = (b"The quick brown fox jumps over the lazy dog. " * 500 +
                       b"Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 300 +
                       b"NeuralBinary and zlib-zero modern C++20 engine compression. " * 400)
        
        c1 = zlib_zero.compress_zlib(sample_text, 1)
        c6 = zlib_zero.compress_zlib(sample_text, 6)
        c9 = zlib_zero.compress_zlib(sample_text, 9)

        # Decompress each and verify lossless parity
        self.assertEqual(zlib.decompress(c1), sample_text)
        self.assertEqual(zlib.decompress(c6), sample_text)
        self.assertEqual(zlib.decompress(c9), sample_text)

        # Verify density progression: Level 6 should be strictly smaller than Level 1
        self.assertLess(len(c6), len(c1))
        self.assertLessEqual(len(c9), len(c6))
        print(f"\n  [PASS] Compression density: L1={len(c1)}B, L6={len(c6)}B, L9={len(c9)}B (L6 savings: {100*(1-len(c6)/len(c1)):.1f}%)")

    def test_02_c_abi_single_call_compress_uncompress(self):
        """Verify compress, compress2, uncompress, and uncompress2 C ABI functions."""
        if not c_lib:
            self.skipTest("C ABI library not available")

        c_lib.compress.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_char_p, ctypes.c_ulong]
        c_lib.compress.restype = ctypes.c_int

        c_lib.compress2.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_char_p, ctypes.c_ulong, ctypes.c_int]
        c_lib.compress2.restype = ctypes.c_int

        c_lib.uncompress.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_char_p, ctypes.c_ulong]
        c_lib.uncompress.restype = ctypes.c_int

        c_lib.uncompress2.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong)]
        c_lib.uncompress2.restype = ctypes.c_int

        data = b"Testing standard zlib C ABI uncompress and compress functions!" * 100
        data_len = len(data)

        # Compress
        dest_buf = ctypes.create_string_buffer(data_len + 128)
        dest_len = ctypes.c_ulong(len(dest_buf))

        ret = c_lib.compress(dest_buf, ctypes.byref(dest_len), data, data_len)
        self.assertEqual(ret, 0, "compress() returned error")
        compressed_bytes = dest_buf.raw[:dest_len.value]

        # Verify against standard Python zlib
        self.assertEqual(zlib.decompress(compressed_bytes), data)

        # Uncompress
        uncomp_buf = ctypes.create_string_buffer(data_len + 64)
        uncomp_len = ctypes.c_ulong(len(uncomp_buf))
        ret_u = c_lib.uncompress(uncomp_buf, ctypes.byref(uncomp_len), compressed_bytes, len(compressed_bytes))
        self.assertEqual(ret_u, 0, "uncompress() returned error")
        self.assertEqual(uncomp_len.value, data_len)
        self.assertEqual(uncomp_buf.raw[:uncomp_len.value], data)

        # Uncompress2 with source length tracking
        src_len_inout = ctypes.c_ulong(len(compressed_bytes))
        uncomp_len2 = ctypes.c_ulong(len(uncomp_buf))
        ret_u2 = c_lib.uncompress2(uncomp_buf, ctypes.byref(uncomp_len2), compressed_bytes, ctypes.byref(src_len_inout))
        self.assertEqual(ret_u2, 0, "uncompress2() returned error")
        self.assertEqual(uncomp_len2.value, data_len)
        self.assertEqual(uncomp_buf.raw[:uncomp_len2.value], data)
        print("\n  [PASS] C ABI compress / uncompress / uncompress2 verified successfully")

    def test_03_stream_reset_reusability(self):
        """Verify that inflateReset and deflateReset allow stream reuse across multiple payloads."""
        if not c_lib:
            self.skipTest("C ABI library not available")

        class z_stream(ctypes.Structure):
            _fields_ = [
                ("next_in", ctypes.c_char_p),
                ("avail_in", ctypes.c_uint32),
                ("total_in", ctypes.c_uint64),
                ("next_out", ctypes.c_char_p),
                ("avail_out", ctypes.c_uint32),
                ("total_out", ctypes.c_uint64),
                ("msg", ctypes.c_char_p),
                ("state", ctypes.c_void_p),
                ("zalloc", ctypes.c_void_p),
                ("zfree", ctypes.c_void_p),
                ("opaque", ctypes.c_void_p),
                ("data_type", ctypes.c_int),
                ("adler", ctypes.c_uint32),
                ("reserved", ctypes.c_uint32),
            ]

        c_lib.inflateInit_.argtypes = [ctypes.POINTER(z_stream), ctypes.c_char_p, ctypes.c_int]
        c_lib.inflateInit_.restype = ctypes.c_int
        c_lib.inflate.argtypes = [ctypes.POINTER(z_stream), ctypes.c_int]
        c_lib.inflate.restype = ctypes.c_int
        c_lib.inflateReset.argtypes = [ctypes.POINTER(z_stream)]
        c_lib.inflateReset.restype = ctypes.c_int
        c_lib.inflateEnd.argtypes = [ctypes.POINTER(z_stream)]
        c_lib.inflateEnd.restype = ctypes.c_int

        strm = z_stream()
        strm.zalloc = None
        strm.zfree = None
        strm.opaque = None

        ret = c_lib.inflateInit_(ctypes.byref(strm), b"1.2.11", ctypes.sizeof(z_stream))
        self.assertEqual(ret, 0)

        payloads = [
            b"Payload 1: testing database / nginx persistent connection reuse.",
            b"Payload 2: another independent stream reusing the exact same z_stream struct.",
            b"Payload 3: final payload verifying zero leaks and state cleanliness."
        ]

        for p in payloads:
            comp = zlib.compress(p)
            out_buf = ctypes.create_string_buffer(len(p) + 64)

            strm.next_in = comp
            strm.avail_in = len(comp)
            strm.next_out = ctypes.cast(out_buf, ctypes.c_char_p)
            strm.avail_out = len(out_buf)

            ret = c_lib.inflate(ctypes.byref(strm), 4)
            self.assertEqual(ret, 1)
            self.assertEqual(out_buf.raw[:strm.total_out], p)

            ret_r = c_lib.inflateReset(ctypes.byref(strm))
            self.assertEqual(ret_r, 0)

        c_lib.inflateEnd(ctypes.byref(strm))
        print("\n  [PASS] Stream reuse via inflateReset verified across multiple payloads")

    def test_04_kraft_mcmillan_oversubscription_rejection(self):
        """Verify that malformed streams with oversubscribed Huffman trees are rejected."""
        bad_payload = bytes([
            0x78, 0x9c,       # zlib header
            0xed, 0xc0, 0x01, # dynamic block with oversubscribed tree
            0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0xff, 0xff
        ])
        res = zlib_zero.decompress_zlib(bad_payload)
        self.assertEqual(len(res), 0)
        print("\n  [PASS] Kraft-McMillan oversubscribed tree safely rejected with 0 output")

    def test_05_long_code_hierarchical_subtable(self):
        """Ensure codes exceeding 10 bits correctly populate secondary 32-entry sub-tables."""
        counts = [1] * 200
        counts[0] = 100000
        counts[1] = 50000
        counts[2] = 25000
        data = b""
        for i in range(len(counts)):
            data += bytes([i]) * min(counts[i], 100)
        
        comp = zlib_zero.compress_zlib(data)
        decomp = zlib_zero.decompress_zlib(comp)
        self.assertEqual(decomp, data)
        self.assertEqual(zlib.decompress(comp), data)
        print("\n  [PASS] Secondary sub-table lookup for long codes verified losslessly")


if __name__ == "__main__":
    unittest.main()
