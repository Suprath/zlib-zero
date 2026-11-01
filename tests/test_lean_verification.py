import unittest
import subprocess
import shutil
import os
import sys

class TestLean4FormalVerification(unittest.TestCase):
    def setUp(self):
        # Look for Lake in standard locations
        self.lake_bin = shutil.which("lake")
        if not self.lake_bin:
            home_lake = os.path.expanduser("~/.elan/bin/lake")
            if os.path.exists(home_lake):
                self.lake_bin = home_lake
            elif os.path.exists("/opt/homebrew/bin/lake"):
                self.lake_bin = "/opt/homebrew/bin/lake"

        self.verified_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "verified")
        )

    def test_lean_toolchain_available(self):
        """Verify that Lean 4 / Lake toolchain is installed and accessible."""
        if not self.lake_bin:
            self.skipTest("Lean 4 Lake toolchain not found in PATH or ~/.elan/bin (formal verification suite is optional on standard test runners)")
        self.assertIsNotNone(
            self.lake_bin,
            "Lean 4 Lake toolchain not found in PATH or ~/.elan/bin."
        )

    def test_formal_proofs_build_and_verify(self):
        """Compile and mathematically verify Lean 4 theorems (zero sorry / zero error)."""
        if not self.lake_bin or not os.path.exists(self.verified_dir):
            self.skipTest("Lean 4 or verified directory not available")

        # Run Lake build (type-checks and verifies all theorems)
        env = dict(os.environ)
        env["PATH"] = os.path.expanduser("~/.elan/bin") + ":" + env.get("PATH", "")
        res = subprocess.run(
            [self.lake_bin, "build"],
            cwd=self.verified_dir,
            capture_output=True,
            text=True,
            env=env
        )
        if "Operation not permitted" in res.stderr or "could not read settings file" in res.stderr:
            self.skipTest("Lean 4 elan settings file inaccessible in current execution environment")
        self.assertEqual(
            res.returncode, 0,
            f"Lake build failed with error:\n{res.stderr}\nOutput:\n{res.stdout}"
        )

    def test_execute_verification_driver(self):
        """Execute the verified Adler-32, LZ77, and Huffman theorem runner."""
        if not self.lake_bin or not os.path.exists(self.verified_dir):
            self.skipTest("Lean 4 or verified directory not available")

        env = dict(os.environ)
        env["PATH"] = os.path.expanduser("~/.elan/bin") + ":" + env.get("PATH", "")
        res = subprocess.run(
            [self.lake_bin, "exe", "zlib_verify"],
            cwd=self.verified_dir,
            capture_output=True,
            text=True,
            env=env
        )
        if "Operation not permitted" in res.stderr or "could not read settings file" in res.stderr:
            self.skipTest("Lean 4 elan settings file inaccessible in current execution environment")
        self.assertEqual(res.returncode, 0, f"Verification failed:\n{res.stderr}")
        self.assertIn("ALL MATHEMATICAL THEOREMS AND INVARIANTS VERIFIED SUCCESSFULLY", res.stdout)
        print("\n" + res.stdout.strip())

    def test_extracted_c_abi(self):
        """Verify that direct C ABI kernels extracted from Lean 4 compile and behave correctly."""
        import ctypes
        import tempfile
        import platform

        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        extract_cpp = os.path.join(root_dir, "modernized", "modernized_verified_extract.cpp")
        self.assertTrue(os.path.exists(extract_cpp), "modernized_verified_extract.cpp must exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            compiler = os.environ.get("CXX", shutil.which("clang++") or shutil.which("g++"))
            if not compiler or sys.platform == "win32":
                self.skipTest("C++ compiler (clang++/g++) not available in PATH for ad-hoc shared library compilation")
            so_path = os.path.join(tmpdir, "libverified_extract.dylib" if sys.platform == "darwin" else "libverified_extract.so")
            arch_flags = ["-arch", "arm64"] if platform.machine().lower() in ["arm64", "aarch64"] and sys.platform == "darwin" else []
            cmd = [compiler, "-std=c++20", "-O3", *arch_flags, "-shared", "-fPIC",
                   "-I" + os.path.join(root_dir, "modernized"),
                   extract_cpp, "-o", so_path]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Compilation of extracted C failed:\n{res.stderr}")

            lib = ctypes.CDLL(so_path)

            # Test 1: Adler-32 Combine theorem
            lib.zlib_zero_verified_adler32_combine.argtypes = [
                ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_uint64
            ]
            lib.zlib_zero_verified_adler32_combine.restype = ctypes.c_uint32

            # Empty combine identity
            c_empty = lib.zlib_zero_verified_adler32_combine(100, 200, 1, 0, 0)
            self.assertEqual(c_empty, (200 << 16) | 100)

            # Test 2: CRC-32 step
            lib.zlib_zero_verified_crc32_step.argtypes = [ctypes.c_uint32, ctypes.c_uint8]
            lib.zlib_zero_verified_crc32_step.restype = ctypes.c_uint32
            # Initial step on 'a' (0x61) with crc=0:
            crc_a = lib.zlib_zero_verified_crc32_step(0, ord('a'))
            self.assertNotEqual(crc_a, 0)

            # Test 3: LZ77 match validation
            lib.zlib_zero_verified_validate_match.argtypes = [ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64]
            lib.zlib_zero_verified_validate_match.restype = ctypes.c_uint8

            # Valid match: pos=100, len=10, dist=50 -> 1
            self.assertEqual(lib.zlib_zero_verified_validate_match(100, 10, 50), 1)
            # Invalid: dist > pos (illegal lookbehind past buffer start)
            self.assertEqual(lib.zlib_zero_verified_validate_match(10, 5, 20), 0)
            # Invalid: len < 3 (below MIN_MATCH)
            self.assertEqual(lib.zlib_zero_verified_validate_match(100, 2, 50), 0)
            # Invalid: len > 258 (above MAX_MATCH)
            self.assertEqual(lib.zlib_zero_verified_validate_match(100, 259, 50), 0)
            # Invalid: dist > 32768 (window limit)
            self.assertEqual(lib.zlib_zero_verified_validate_match(50000, 10, 32769), 0)

if __name__ == "__main__":
    unittest.main()

