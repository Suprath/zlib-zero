cmake_minimum_required(VERSION 3.16)
project(zlib_zero VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Optimization & Architecture Flags
if(MSVC)
    add_compile_options(/O2)
else()
    add_compile_options(-O3)
    if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm" AND NOT APPLE)
        add_compile_options(-march=armv8-a+crc)
    elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|amd64|i386")
        add_compile_options(-march=native)
    endif()
endif()

include_directories(modernized)

set(SOURCES
    modernized/modernized_official_adler32.cpp
    modernized/modernized_zlib_crc32.cpp
    modernized/modernized_zlib_c_api.cpp
    modernized/modernized_zlib_deflate.cpp
)

# Static Library (libzlib_zero_static.a)
add_library(zlib_zero_static STATIC ${SOURCES})
set_target_properties(zlib_zero_static PROPERTIES OUTPUT_NAME "zlib_zero")

# Dynamic Shared Library (Drop-In replacement libz)
add_library(zlib_zero SHARED ${SOURCES})
set_target_properties(zlib_zero PROPERTIES OUTPUT_NAME "z_zero")

message(STATUS "zlib-zero High-Performance C++20 compression library configured successfully.")
