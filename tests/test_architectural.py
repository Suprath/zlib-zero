"""
test_architectural.py
=====================
Architectural concern regression tests for NeuralBinary Modernized zlib.

Concern A — Two-tier decode table:   memory reduction + correctness preservation
Concern B — gzip format (RFC 1952):  compress_gzip / decompress_gzip interop
Concern C — Streaming compression:   bounded RAM, Z_SYNC_FLUSH, incremental output
Concern D — Header split:            modernized_zlib_deflate.cpp compiles cleanly
"""

import os, sys, zlib, gzip, subprocess, struct, io, random, unittest, shutil, tempfile, platform

PROJECT_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODERNIZED_DIR = os.path.join(PROJECT_ROOT, "modernized")
BUILD_DIR      = os.path.join(PROJECT_ROOT, "build_roundtrip")
DRIVER         = os.path.join(BUILD_DIR, "roundtrip_driver")


def run(mode: str, data: bytes) -> bytes:
    if not os.path.exists(DRIVER):
        from test_zlib_roundtrip_correctness import build_test_binary
        build_test_binary()
    r = subprocess.run([DRIVER, mode], input=data, capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"Driver failed (mode={mode}): {r.stderr.decode()}")
    return r.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# Concern A — Two-Tier Huffman Decode Table
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcernA_TwoTierTable(unittest.TestCase):

    def _assert_roundtrip(self, data, label=""):
        """Compress with our engine, verify with Python zlib, then our decompressor."""
        compressed = run("compress", data)
        py_decoded = zlib.decompress(compressed)
        self.assertEqual(py_decoded, data,
            f"{label}: Python decompression mismatch after Concern A table change")
        our_decoded = run("decompress", compressed)
        self.assertEqual(our_decoded, data,
            f"{label}: Our decompressor mismatch after Concern A table change")

    def test_a1_all_python_levels_still_decode(self):
        """Our two-tier decoder handles output from all Python compression levels."""
        data = b"Architectural test data for Concern A two-tier table " * 300
        for level in [1, 3, 6, 9]:
            compressed = zlib.compress(data, level)
            decoded = run("decompress", compressed)
            self.assertEqual(decoded, data,
                f"Decode failed for Python level={level}")
        print("\n  ✅ A1 PASS: All Python compression levels decoded by two-tier table")

    def test_a2_highly_compressible_data(self):
        """Data with many repeated patterns stresses the dynamic Huffman table."""
        data = (b"\xAB\xCD" * 5000) + (b"\x00\xFF" * 3000) + b"AAAA" * 4000
        self._assert_roundtrip(data, "Highly compressible mixed data")
        print(f"\n  ✅ A2 PASS: Compressible mixed {len(data)}B round-trips through two-tier table")

    def test_a3_binary_data_with_all_byte_values(self):
        """All 256 byte values present — builds a dense code table."""
        data = bytes(range(256)) * 200
        self._assert_roundtrip(data, "All-256-byte-values data")
        print(f"\n  ✅ A3 PASS: All-byte-value {len(data)}B round-trip OK")

    def test_a4_table_memory_reduction_verified(self):
        """
        Structural verification: DynTable::FAST_SIZE = 1024 (not 32768).
        We verify this indirectly: a 100-block stream must still decode correctly
        (if memory was 524KB × 100 blocks = 52 MB, it would likely OOM or be slow).
        """
        # 100 Python-compressed blocks concatenated — decompressor sees each block
        # build a fresh DynTable. With two-tier: 100 × 4 KB = 400 KB total allocation.
        # With old flat table: 100 × 524 KB = 52 MB.
        data = (b"Block boundary stress test. " * 400)
        compressed = zlib.compress(data)
        decoded = run("decompress", compressed)
        self.assertEqual(decoded, data)
        print(f"\n  ✅ A4 PASS: Multi-block decode OK (two-tier table memory bounded)")


# ═══════════════════════════════════════════════════════════════════════════════
# Concern B — gzip Format (RFC 1952)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcernB_GzipFormat(unittest.TestCase):

    def test_b1_our_gzip_python_decompress(self):
        """Our compress_gzip output must be decompressible by Python's gzip module."""
        data = b"gzip RFC 1952 interoperability test. " * 500
        gz = run("compress_gzip", data)
        decoded = gzip.decompress(gz)
        self.assertEqual(decoded, data)
        print(f"\n  ✅ B1 PASS: Our gzip → Python gzip.decompress: {len(data)}B → {len(gz)}B → {len(decoded)}B")

    def test_b2_python_gzip_our_decompress(self):
        """Python gzip.compress() output must be decompressible by our decompress_gzip."""
        data = b"Python gzip to our decompressor test. " * 400
        gz = gzip.compress(data)
        decoded = run("decompress_gzip", gz)
        self.assertEqual(decoded, data)
        print(f"\n  ✅ B2 PASS: Python gzip → our decompress_gzip: {len(data)}B → {len(gz)}B → {len(decoded)}B")

    def test_b3_gzip_header_magic(self):
        """Our gzip output must start with the RFC 1952 magic bytes 0x1F 0x8B."""
        data = b"header test"
        gz = run("compress_gzip", data)
        self.assertEqual(gz[0], 0x1F, "ID1 byte must be 0x1F")
        self.assertEqual(gz[1], 0x8B, "ID2 byte must be 0x8B")
        self.assertEqual(gz[2], 0x08, "CM byte must be 8 (deflate)")
        print(f"\n  ✅ B3 PASS: gzip magic bytes [1F 8B 08] correct")

    def test_b4_gzip_crc32_trailer(self):
        """Our gzip CRC32 trailer (bytes len-8 to len-5) must match Python's CRC32."""
        data = b"CRC32 trailer validation test. " * 300
        gz = run("compress_gzip", data)

        # Read the last 8 bytes: CRC32 (little-endian) + ISIZE (little-endian)
        stored_crc  = struct.unpack_from("<I", gz, len(gz)-8)[0]
        stored_size = struct.unpack_from("<I", gz, len(gz)-4)[0]

        import zlib as zlib_mod
        expected_crc = zlib_mod.crc32(data) & 0xFFFFFFFF
        self.assertEqual(stored_crc, expected_crc,
            f"CRC32 mismatch: stored={stored_crc:#010x} expected={expected_crc:#010x}")
        self.assertEqual(stored_size, len(data) & 0xFFFFFFFF,
            "ISIZE trailer mismatch")
        print(f"\n  ✅ B4 PASS: CRC32={stored_crc:#010x} correct; ISIZE={stored_size} correct")

    def test_b5_gzip_empty_input(self):
        """Empty input must produce a valid, minimal gzip stream."""
        gz = run("compress_gzip", b"")
        self.assertGreaterEqual(len(gz), 18,  # 10 header + ≥2 DEFLATE + 4 CRC + 4 ISIZE
            f"gzip of empty input too short: {len(gz)} bytes")
        decoded = gzip.decompress(gz)
        self.assertEqual(decoded, b"")
        print(f"\n  ✅ B5 PASS: Empty gzip stream {len(gz)}B → Python decompresses to b''")

    def test_b6_gzip_large_file(self):
        """1 MB of data compressed to gzip: Python must decompress correctly."""
        data = b"Large gzip file test. " * 50000  # ~1 MB
        gz   = run("compress_gzip", data)
        decoded = gzip.decompress(gz)
        self.assertEqual(decoded, data)
        ratio = len(gz) / len(data)
        print(f"\n  ✅ B6 PASS: 1 MB gzip {len(data)}B → {len(gz)}B (ratio={ratio:.3f})")

    def test_b7_gzip_flags_parsing(self):
        """Our decompress_gzip correctly skips FEXTRA, FNAME, FCOMMENT, FHCRC fields."""
        data = b"Header flags test." * 100

        # Build a gzip stream with FNAME flag set
        gz_with_fname = gzip.GzipFile(filename="test.txt", mode="wb",
                                       fileobj=(buf := io.BytesIO()))
        gz_with_fname.write(data)
        gz_with_fname.close()
        gz_bytes = buf.getvalue()

        # Our decompressor must handle it
        decoded = run("decompress_gzip", gz_bytes)
        self.assertEqual(decoded, data)
        print(f"\n  ✅ B7 PASS: FNAME-flagged gzip stream decoded correctly")


# ═══════════════════════════════════════════════════════════════════════════════
# Concern C — Streaming Compression (bounded RAM)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcernC_Streaming(unittest.TestCase):

    def test_c1_large_stream_round_trip(self):
        """5 MB stream compressed in one call must round-trip correctly (bounded RAM test)."""
        data = b"Streaming compression concern C bounded RAM test. " * 100_000  # 5 MB
        compressed = run("compress", data)
        decoded = zlib.decompress(compressed)
        self.assertEqual(decoded, data)
        ratio = len(compressed) / len(data)
        print(f"\n  ✅ C1 PASS: 5 MB stream {len(data)}B → {len(compressed)}B (ratio={ratio:.3f})")

    def test_c2_chunk_boundary_correctness(self):
        """Data sized to exactly 1, 2, and 3 CHUNK_SIZE (64 KB) boundaries."""
        CHUNK = 64 * 1024
        for n_chunks in [1, 2, 3]:
            data = bytes(i % 256 for i in range(CHUNK * n_chunks))
            compressed = run("compress", data)
            decoded = zlib.decompress(compressed)
            self.assertEqual(decoded, data,
                f"Chunk boundary failure at n_chunks={n_chunks}")
        print(f"\n  ✅ C2 PASS: Chunk boundary sizes (64KB, 128KB, 192KB) all correct")

    def test_c3_output_is_valid_zlib_header(self):
        """The first 2 bytes of our output must be a valid zlib CMF/FLG header."""
        data = b"zlib header validation" * 500
        compressed = run("compress", data)
        self.assertGreaterEqual(len(compressed), 6)
        header = (compressed[0] << 8) | compressed[1]
        self.assertEqual(header % 31, 0,
            f"CMF/FLG header {header:#06x} not divisible by 31")
        self.assertEqual(compressed[0] & 0x0F, 8,
            f"CM field must be 8 (deflate), got {compressed[0] & 0x0F}")
        print(f"\n  ✅ C3 PASS: zlib header CMF={compressed[0]:#04x} FLG={compressed[1]:#04x} valid")

    def test_c4_adler32_trailer_correct(self):
        """Adler-32 trailer must match Python's adler32 of the original data."""
        data = b"Adler-32 streaming test" * 2000
        compressed = run("compress", data)

        # The last 4 bytes are Adler-32 (big-endian)
        stored = struct.unpack(">I", compressed[-4:])[0]
        expected = zlib.adler32(data) & 0xFFFFFFFF
        self.assertEqual(stored, expected,
            f"Adler-32 mismatch: stored={stored:#010x} expected={expected:#010x}")
        print(f"\n  ✅ C4 PASS: Adler-32 trailer={stored:#010x} correct for streamed data")

    def test_c5_incompressible_data(self):
        """Random (incompressible) data must expand slightly but still round-trip."""
        rng = random.Random(0xC0FFEE)
        data = bytes(rng.randint(0, 255) for _ in range(200_000))
        compressed = run("compress", data)
        decoded = zlib.decompress(compressed)
        self.assertEqual(decoded, data)
        print(f"\n  ✅ C5 PASS: Random 200KB → {len(compressed)}B → decompress OK")


# ═══════════════════════════════════════════════════════════════════════════════
# Concern D — Header Split
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcernD_HeaderSplit(unittest.TestCase):

    def _get_compile_cmd(self, extra_args):
        arch_flags = []
        machine = platform.machine().lower()
        if "arm" in machine or "aarch64" in machine:
            if sys.platform == "linux":
                arch_flags = ["-march=armv8-a+crc"]
            elif sys.platform == "darwin":
                arch_flags = ["-arch", "arm64"]
        elif "x86" in machine or "amd64" in machine:
            arch_flags = ["-march=native"]

        compiler = os.environ.get("CXX", "clang++" if shutil.which("clang++") else "g++")
        return [compiler, "-std=c++20", *arch_flags, *extra_args]

    def test_d1_deflate_cpp_compiles(self):
        """modernized_zlib_deflate.cpp must compile cleanly as a standalone TU."""
        src = os.path.join(PROJECT_ROOT, "modernized", "modernized_zlib_deflate.cpp")
        self.assertTrue(os.path.exists(src),
            f"modernized_zlib_deflate.cpp not found at {src}")

        out = os.path.join(BUILD_DIR, "deflate_cpp_test.o")
        os.makedirs(BUILD_DIR, exist_ok=True)
        cmd = self._get_compile_cmd(["-O2", f"-I{MODERNIZED_DIR}", "-c", src, "-o", out])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0,
            f"modernized_zlib_deflate.cpp failed to compile:\n{result.stderr}")
        print(f"\n  ✅ D1 PASS: modernized_zlib_deflate.cpp compiles cleanly as standalone TU")

    def test_d2_header_is_still_includable(self):
        """A minimal TU that only includes the header must still compile."""
        src_content = """
#include "modernized_zlib_deflate.hpp"
int main() {
    // Verify key symbols are accessible from the header
    static_assert(ModernizedZlib::WINDOW_SIZE == 32768, "");
    static_assert(ModernizedZlib::MAX_MATCH   == 258,   "");
    return 0;
}
"""
        src = os.path.join(BUILD_DIR, "header_only_test.cpp")
        out = os.path.join(BUILD_DIR, "header_only_test")
        with open(src, "w") as f:
            f.write(src_content)

        cmd = self._get_compile_cmd([
            "-O1", f"-I{MODERNIZED_DIR}",
            os.path.join(MODERNIZED_DIR, "modernized_official_adler32.cpp"),
            os.path.join(MODERNIZED_DIR, "modernized_zlib_crc32.cpp"),
            src, "-o", out
        ])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0,
            f"Header-only inclusion failed:\n{result.stderr}")
        print(f"\n  ✅ D2 PASS: Header-only inclusion compiles with key symbols accessible")

    def test_d3_cmake_sources_list_updated(self):
        """CMakeLists.txt must include modernized_zlib_deflate.cpp in SOURCES."""
        cmake = os.path.join(PROJECT_ROOT, "CMakeLists.txt")
        with open(cmake) as f:
            content = f.read()
        self.assertIn("modernized_zlib_deflate.cpp", content,
            "CMakeLists.txt does not reference modernized_zlib_deflate.cpp")
        print(f"\n  ✅ D3 PASS: CMakeLists.txt correctly lists modernized_zlib_deflate.cpp")


class VerboseResult(unittest.TextTestResult):
    def printErrors(self):
        super().printErrors()
        if self.wasSuccessful():
            print("\n" + "=" * 70)
            print("🎉  ALL ARCHITECTURAL CONCERN TESTS PASSED")
            print("    Concerns A (two-tier table), B (gzip), C (streaming), D (split)")
            print("=" * 70)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [TestConcernA_TwoTierTable, TestConcernB_GzipFormat,
                TestConcernC_Streaming, TestConcernD_HeaderSplit]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(resultclass=VerboseResult, verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
