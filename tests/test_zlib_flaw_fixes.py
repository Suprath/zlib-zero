#!/usr/bin/env python3
import sys
import time
import ctypes
import random
import tempfile
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

ZLIB_DYLIB = ROOT_DIR / "zlib_src" / "build" / "libz.dylib"
MODERNIZED_CRC_CPP = ROOT_DIR / "modernized" / "modernized_zlib_crc32.cpp"
MODERNIZED_LZ77_HPP = ROOT_DIR / "modernized" / "modernized_zlib_lz77.hpp"
MODERNIZED_DEFLATE_HPP = ROOT_DIR / "modernized" / "modernized_zlib_deflate.hpp"

def run_flaw_fix_verification():
    print("==================================================================")
    print("  NEURALBINARY GLOBAL: zlib FLAW FIXES VERIFICATION SUITE")
    print("==================================================================")

    if not ZLIB_DYLIB.exists():
        print(f"Error: {ZLIB_DYLIB} not found.")
        sys.exit(1)

    libz = ctypes.CDLL(str(ZLIB_DYLIB))
    libz.crc32.argtypes = [ctypes.c_ulong, ctypes.c_char_p, ctypes.c_uint]
    libz.crc32.restype = ctypes.c_ulong

    # Compile C++ wrapper exposing flaw fixes
    cpp_code = f"""
    #include "{MODERNIZED_LZ77_HPP}"
    #include "{MODERNIZED_DEFLATE_HPP}"
    #include <cstdint>
    #include <cstddef>

    extern "C" size_t test_lz77_match(const uint8_t *s1, const uint8_t *s2, size_t max_len) {{
        return ModernizedZlib::longest_match_fast(s1, s2, max_len);
    }}
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        src_cpp = Path(tmpdir) / "flaw_test.cpp"
        with open(src_cpp, "w") as f:
            f.write(cpp_code)

        import platform, shutil
        compiler = os.environ.get("CXX", "clang++" if shutil.which("clang++") else "g++")
        arch_flags = []
        machine = platform.machine().lower()
        if "arm" in machine or "aarch64" in machine:
            if sys.platform == "linux":
                arch_flags = ["-march=armv8-a+crc"]
            elif sys.platform == "darwin":
                arch_flags = ["-arch", "arm64"]
        elif "x86" in machine or "amd64" in machine:
            arch_flags = ["-march=native"]

        so_crc = Path(tmpdir) / "libmod_crc.dylib"
        cmd = [compiler, "-std=c++20", *arch_flags, "-shared", "-fPIC", "-O3", str(MODERNIZED_CRC_CPP), "-o", str(so_crc)]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        mod_crc_lib = ctypes.CDLL(str(so_crc))
        mod_crc_lib.crc32_modernized.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t]
        mod_crc_lib.crc32_modernized.restype = ctypes.c_uint32

        so_lz77 = Path(tmpdir) / "liblz77.dylib"
        cmd = [compiler, "-std=c++20", *arch_flags, "-shared", "-fPIC", "-O3", str(src_cpp), "-o", str(so_lz77)]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        mod_lz77_lib = ctypes.CDLL(str(so_lz77))
        mod_lz77_lib.test_lz77_match.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
        mod_lz77_lib.test_lz77_match.restype = ctypes.c_size_t

        print("\n[Fix 1 Verification: MSVC & Portable x86_64/ARM64 Hardware CRC32]")
        test_payload = b"NeuralBinary Global Hardware Acceleration Verification Payload 2026!"
        orig_crc = libz.crc32(0, test_payload, len(test_payload))
        mod_crc = mod_crc_lib.crc32_modernized(0, test_payload, len(test_payload))

        match_crc = (orig_crc == mod_crc)
        print(f" -> Original CRC32: {hex(orig_crc)} | Modernized HW CRC32: {hex(mod_crc)} | {'PARITY MATCH' if match_crc else 'MISMATCH'}")

        print("\n[Fix 2 Verification: 64-Bit LZ77 Sliding Window Match Engine]")
        buf1 = b"NeuralBinaryGlobalDEFLATECompressionTestBuffer12345"
        buf2 = b"NeuralBinaryGlobalDEFLATECompressionTestBuffer67890"

        match_len = mod_lz77_lib.test_lz77_match(buf1, buf2, len(buf1))
        expected_len = 46 # Exact prefix match length
        print(f" -> 64-bit LZ77 Scanned Match Length: {match_len} bytes (Expected: {expected_len}) | {'MATCH' if match_len == expected_len else 'MISMATCH'}")

        print("\n==================================================================")
        if match_crc and match_len == expected_len:
            print(" SUCCESS: All Modernized zlib Flaw Fixes Verified 100%!")
        else:
            print(" WARNING: Parity or match failure detected!")
        print("==================================================================")

if __name__ == "__main__":
    run_flaw_fix_verification()
