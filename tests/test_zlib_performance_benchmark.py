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
MODERNIZED_ADLER_CPP = ROOT_DIR / "modernized" / "modernized_official_adler32.cpp"
MODERNIZED_CRC_CPP = ROOT_DIR / "modernized" / "modernized_zlib_crc32.cpp"

def run_performance_benchmarks():
    print("==================================================================")
    print("   NEURALBINARY GLOBAL: zlib THROUGHPUT & PERFORMANCE BENCHMARK")
    print("==================================================================")

    if not ZLIB_DYLIB.exists():
        print(f"Error: {ZLIB_DYLIB} not found.")
        sys.exit(1)

    libz = ctypes.CDLL(str(ZLIB_DYLIB))
    libz.adler32.argtypes = [ctypes.c_ulong, ctypes.c_char_p, ctypes.c_uint]
    libz.adler32.restype = ctypes.c_ulong

    libz.crc32.argtypes = [ctypes.c_ulong, ctypes.c_char_p, ctypes.c_uint]
    libz.crc32.restype = ctypes.c_ulong

    with tempfile.TemporaryDirectory() as tmpdir:
        # Compile Adler32 with -O3 -std=c++20
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

        adler_so = Path(tmpdir) / "libmod_adler.dylib"
        cmd = [compiler, "-std=c++20", *arch_flags, "-shared", "-fPIC", "-O3", str(MODERNIZED_ADLER_CPP), "-o", str(adler_so)]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        mod_adler_lib = ctypes.CDLL(str(adler_so))
        mod_adler_lib.adler32_modernized.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t]
        mod_adler_lib.adler32_modernized.restype = ctypes.c_uint32

        # Compile CRC32 with Hardware Acceleration
        crc_so = Path(tmpdir) / "libmod_crc.dylib"
        cmd = [compiler, "-std=c++20", *arch_flags, "-shared", "-fPIC", "-O3", str(MODERNIZED_CRC_CPP), "-o", str(crc_so)]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        mod_crc_lib = ctypes.CDLL(str(crc_so))
        mod_crc_lib.crc32_modernized.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t]
        mod_crc_lib.crc32_modernized.restype = ctypes.c_uint32

        # Generate 10MB test payload
        payload_size = 10 * 1024 * 1024 # 10 MB
        test_payload = bytes([random.randint(0, 255) for _ in range(payload_size)])

        iterations = 50
        total_bytes = payload_size * iterations
        total_mb = total_bytes / (1024 * 1024)

        print(f"\n[Benchmark Configuration: {iterations} Iterations of 10MB Payload (Total Data: {total_mb:.1f} MB)]\n")

        # 1. Original libz adler32
        t0 = time.perf_counter()
        for _ in range(iterations):
            r1 = libz.adler32(1, test_payload, payload_size)
        t1 = time.perf_counter()
        orig_adler_time = t1 - t0
        orig_adler_tp = total_mb / orig_adler_time

        # 2. Modernized C++ adler32 (NMAX Unrolled + Fast Modulo)
        t0 = time.perf_counter()
        for _ in range(iterations):
            r2 = mod_adler_lib.adler32_modernized(1, test_payload, payload_size)
        t1 = time.perf_counter()
        mod_adler_time = t1 - t0
        mod_adler_tp = total_mb / mod_adler_time

        parity_adler = (r1 == r2)

        print(f" -> Original zlib adler32:    {orig_adler_time:.4f} sec | {orig_adler_tp:>7.1f} MB/sec | Result: {hex(r1)}")
        print(f" -> Modernized C++ adler32:  {mod_adler_time:.4f} sec | {mod_adler_tp:>7.1f} MB/sec | Result: {hex(r2)} | {'PARITY MATCH' if parity_adler else 'MISMATCH'}")
        speedup_adler = (mod_adler_tp / orig_adler_tp) * 100
        print(f"    --> Speed Performance Ratio: {speedup_adler:.1f}% of native C speed\n")

        # 3. Original libz crc32
        t0 = time.perf_counter()
        for _ in range(iterations):
            c1 = libz.crc32(0, test_payload, payload_size)
        t1 = time.perf_counter()
        orig_crc_time = t1 - t0
        orig_crc_tp = total_mb / orig_crc_time

        # 4. Modernized C++ Hardware-Accelerated crc32
        t0 = time.perf_counter()
        for _ in range(iterations):
            c2 = mod_crc_lib.crc32_modernized(0, test_payload, payload_size)
        t1 = time.perf_counter()
        mod_crc_time = t1 - t0
        mod_crc_tp = total_mb / mod_crc_time

        parity_crc = (c1 == c2)

        print(f" -> Original zlib crc32:      {orig_crc_time:.4f} sec | {orig_crc_tp:>7.1f} MB/sec | Result: {hex(c1)}")
        print(f" -> Modernized C++ HW crc32: {mod_crc_time:.4f} sec | {mod_crc_tp:>7.1f} MB/sec | Result: {hex(c2)} | {'PARITY MATCH' if parity_crc else 'MISMATCH'}")
        speedup_crc = (mod_crc_tp / orig_crc_tp) * 100
        print(f"    --> Speed Performance Ratio: {speedup_crc:.1f}% of native C speed")

        print("\n==================================================================")
        if parity_adler and parity_crc:
            print(" SUCCESS: Hardware-Accelerated Modernized zlib Benchmarked & Verified!")
        else:
            print(" WARNING: Parity error detected!")
        print("==================================================================")

if __name__ == "__main__":
    run_performance_benchmarks()
