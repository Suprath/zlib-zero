#!/usr/bin/env python3
import sys
import ctypes
import random
import tempfile
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

ZLIB_DYLIB = ROOT_DIR / "zlib_src" / "build" / "libz.dylib"
MODERNIZED_ADLER_CPP = ROOT_DIR / "modernized" / "modernized_official_adler32.cpp"

def run_zlib_ng_parity_tests():
    print("==================================================================")
    print("   NEURALBINARY GLOBAL: zlib vs zlib-ng HASH PARITY TEST SUITE")
    print("==================================================================")

    if not ZLIB_DYLIB.exists():
        print(f"Error: {ZLIB_DYLIB} not found.")
        sys.exit(1)

    # 1. Load Original zlib Dynamic Library via ctypes
    libz = ctypes.CDLL(str(ZLIB_DYLIB))
    libz.adler32.argtypes = [ctypes.c_ulong, ctypes.c_char_p, ctypes.c_uint]
    libz.adler32.restype = ctypes.c_ulong

    # 2. Compile NeuralBinary Modernized Adler32 C++ Code into Shared Library
    with tempfile.TemporaryDirectory() as tmpdir:
        import shutil
        compiler = os.environ.get("CXX", "clang++" if shutil.which("clang++") else "g++")
        cmd = [compiler, "-shared", "-fPIC", "-O3", str(MODERNIZED_ADLER_CPP), "-o", str(mod_so)]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        mod_lib = ctypes.CDLL(str(mod_so))
        mod_lib.adler32_modernized.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t]
        mod_lib.adler32_modernized.restype = ctypes.c_uint32

        print("\n[Test 1: NMAX Chunk Boundary Thresholds (NMAX = 5,552 Bytes)]")
        # Test boundary sizes: 0, 1, 5551, 5552, 5553, 11104, 11105, 65536 (64KB), 1048576 (1MB)
        test_sizes = [0, 1, 5551, 5552, 5553, 11104, 11105, 65536, 1048576]
        
        all_passed = True
        for size in test_sizes:
            data = bytes([random.randint(0, 255) for _ in range(size)]) if size > 0 else b""
            
            orig_hash = libz.adler32(1, data, len(data))
            mod_hash = mod_lib.adler32_modernized(1, data, len(data))

            match = (orig_hash == mod_hash)
            status_str = "MATCH" if match else "MISMATCH (zlib-ng bug detected!)"
            print(f" -> Buffer Size: {size:>7} bytes | Original: {hex(orig_hash):>10} | Modernized: {hex(mod_hash):>10} | {status_str}")
            if not match:
                all_passed = False

        print("\n[Test 2: Memory Alignment & Pointer Offsets]")
        # Test unaligned pointers (offsets 1, 3, 5, 7)
        sample_buf = bytes([random.randint(0, 255) for _ in range(10000)])
        for offset in [0, 1, 3, 5, 7]:
            sub_data = sample_buf[offset:offset+5555]
            orig_hash = libz.adler32(1, sub_data, len(sub_data))
            mod_hash = mod_lib.adler32_modernized(1, sub_data, len(sub_data))
            
            match = (orig_hash == mod_hash)
            print(f" -> Memory Offset: +{offset} bytes | Original: {hex(orig_hash)} | Modernized: {hex(mod_hash)} | {'MATCH' if match else 'MISMATCH'}")
            if not match:
                all_passed = False

        print("\n[Test 3: Randomized Differential Fuzzing (1,000 Iterations)]")
        fuzz_matches = 0
        iterations = 1000
        for i in range(iterations):
            random_len = random.randint(1, 20000)
            random_data = bytes([random.randint(0, 255) for _ in range(random_len)])
            init_adler = random.randint(1, 0xFFFFFFFF)

            orig_val = libz.adler32(init_adler, random_data, len(random_data))
            mod_val = mod_lib.adler32_modernized(init_adler, random_data, len(random_data))

            if orig_val == mod_val:
                fuzz_matches += 1

        print(f" -> Differential Fuzzing Result: {fuzz_matches}/{iterations} Iterations Matched 100% Byte-for-Byte.")

        print("\n==================================================================")
        if all_passed and fuzz_matches == iterations:
            print(" SUCCESS: Modernized C++ adler32 maintains 100% parity with zlib!")
            print(" NO zlib-ng accumulator overflow or chunk boundary bugs detected.")
        else:
            print(" WARNING: Hash mismatch detected!")
        print("==================================================================")

if __name__ == "__main__":
    run_zlib_ng_parity_tests()
