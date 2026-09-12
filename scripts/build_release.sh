#!/usr/bin/env bash
set -e

VERSION="v1.0.0"
OS_NAME=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
PACKAGE_NAME="zlib-zero-${VERSION}-${OS_NAME}-${ARCH}"

echo "Building zlib-zero release binaries for ${OS_NAME}-${ARCH}..."

rm -rf build "${PACKAGE_NAME}" "${PACKAGE_NAME}.tar.gz"
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)
cd ..

mkdir -p "${PACKAGE_NAME}/include/zlib_zero" "${PACKAGE_NAME}/lib"
cp modernized/*.hpp "${PACKAGE_NAME}/include/zlib_zero/"
cp build/libzlib_zero.a "${PACKAGE_NAME}/lib/"
cp build/libz_zero.* "${PACKAGE_NAME}/lib/"
cp LICENSE README.md "${PACKAGE_NAME}/"

tar -czvf "${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}"

echo ""
echo "Successfully packaged release binary tarball: ${PACKAGE_NAME}.tar.gz"
echo "Contents:"
tar -tzvf "${PACKAGE_NAME}.tar.gz"
