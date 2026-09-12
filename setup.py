import os
import sys
import platform
from setuptools import setup, Extension

extra_compile_args = ["-std=c++20", "-O3"]
machine = platform.machine().lower()

if sys.platform == "win32":
    extra_compile_args = ["/std:c++20", "/O2"]
elif sys.platform == "darwin":
    if "arm" in machine or "aarch64" in machine:
        extra_compile_args.extend(["-arch", "arm64"])
elif sys.platform == "linux":
    if "arm" in machine or "aarch64" in machine:
        extra_compile_args.append("-march=armv8-a+crc")
    elif "x86" in machine or "amd64" in machine:
        extra_compile_args.append("-march=native")

zlib_zero_module = Extension(
    "zlib_zero",
    sources=[
        "modernized/python_zlib_zero.cpp",
        "modernized/modernized_official_adler32.cpp",
        "modernized/modernized_zlib_crc32.cpp",
        "modernized/modernized_zlib_c_api.cpp",
        "modernized/modernized_zlib_deflate.cpp",
    ],
    include_dirs=["modernized"],
    language="c++",
    extra_compile_args=extra_compile_args,
)

readme_path = os.path.join(os.path.dirname(__file__), "README.md")
long_description = open(readme_path, encoding="utf-8").read() if os.path.exists(readme_path) else ""

setup(
    name="zlib-zero",
    version="1.0.11",
    description="High-Performance Modernized C++20 zlib Compression Engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Suprath",
    url="https://github.com/Suprath/zlib-zero",
    ext_modules=[zlib_zero_module],
    zip_safe=False,
    classifiers=[
        "Programming Language :: C++",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
