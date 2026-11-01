cmake_minimum_required(VERSION 3.16)
project(zlib_zero VERSION 1.1.2 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Optimization & Architecture Flags
if(MSVC)
    add_compile_options(/O2 /EHsc /utf-8 /DNOMINMAX /D_CRT_SECURE_NO_WARNINGS)
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
    modernized/modernized_verified_extract.cpp
)

# Static Library (libzlib_zero_static.a)
add_library(zlib_zero_static STATIC ${SOURCES})
set_target_properties(zlib_zero_static PROPERTIES OUTPUT_NAME "zlib_zero")

# Dynamic Shared Library (Drop-In replacement libz)
add_library(zlib_zero SHARED ${SOURCES})
set_target_properties(zlib_zero PROPERTIES OUTPUT_NAME "z_zero")

# Lean 4 Mathematical Formal Verification Target
find_program(LAKE_EXECUTABLE lake HINTS "$ENV{HOME}/.elan/bin" "/opt/homebrew/bin")
if(LAKE_EXECUTABLE)
    message(STATUS "Lean 4 Formal Verification: Enabled (${LAKE_EXECUTABLE})")
    add_custom_target(verify
        COMMAND ${LAKE_EXECUTABLE} exe zlib_verify
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/verified
        COMMENT "Running Lean 4 Mathematical Verification proofs"
    )
endif()

message(STATUS "zlib-zero High-Performance C++20 compression library configured successfully.")

