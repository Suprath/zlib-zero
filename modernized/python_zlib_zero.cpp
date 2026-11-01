#ifndef NOMINMAX
#define NOMINMAX
#endif

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <algorithm>
#include "modernized_zlib_deflate.hpp"

static PyObject* py_compress_zlib(PyObject* self, PyObject* args) {
    Py_buffer buf;
    int level = 6;
    if (!PyArg_ParseTuple(args, "y*|i", &buf, &level)) {
        return NULL;
    }
    auto out = ModernizedZlib::compress_zlib(
        static_cast<const uint8_t*>(buf.buf), buf.len, level);
    PyBuffer_Release(&buf);
    return PyBytes_FromStringAndSize(reinterpret_cast<const char*>(out.data()),
                                     static_cast<Py_ssize_t>(out.size()));
}

static PyObject* py_decompress_zlib(PyObject* self, PyObject* args) {
    Py_buffer buf;
    Py_ssize_t max_out = 0;
    if (!PyArg_ParseTuple(args, "y*|n", &buf, &max_out)) {
        return NULL;
    }
    const uint8_t* in_data = static_cast<const uint8_t*>(buf.buf);
    size_t in_len = buf.len;
    if (in_len < 6) {
        PyBuffer_Release(&buf);
        return PyBytes_FromStringAndSize("", 0);
    }

    if (max_out > 0) {
        // Fast path: direct zero-copy into Python Bytes object
        size_t est_cap = static_cast<size_t>(max_out);
        PyObject* res = PyBytes_FromStringAndSize(NULL, static_cast<Py_ssize_t>(est_cap));
        if (!res) {
            PyBuffer_Release(&buf);
            return PyErr_NoMemory();
        }

        uint8_t* dst = reinterpret_cast<uint8_t*>(PyBytes_AS_STRING(res));
        size_t actual_sz = ModernizedZlib::decompress_zlib_into(dst, est_cap, in_data, in_len);
        if (actual_sz > 0) {
            PyBuffer_Release(&buf);
            if (_PyBytes_Resize(&res, static_cast<Py_ssize_t>(actual_sz)) < 0) {
                return NULL;
            }
            return res;
        }
        Py_DECREF(res);
    }

    // Dynamic single-pass path
    auto out = ModernizedZlib::decompress_zlib(in_data, in_len);
    PyBuffer_Release(&buf);
    return PyBytes_FromStringAndSize(reinterpret_cast<const char*>(out.data()),
                                     static_cast<Py_ssize_t>(out.size()));
}

static PyObject* py_compress_gzip(PyObject* self, PyObject* args) {
    Py_buffer buf;
    const char* filename = "";
    if (!PyArg_ParseTuple(args, "y*|s", &buf, &filename)) {
        return NULL;
    }
    auto out = ModernizedZlib::compress_gzip(
        static_cast<const uint8_t*>(buf.buf), buf.len, filename);
    PyBuffer_Release(&buf);
    return PyBytes_FromStringAndSize(reinterpret_cast<const char*>(out.data()),
                                     static_cast<Py_ssize_t>(out.size()));
}

static PyObject* py_decompress_gzip(PyObject* self, PyObject* args) {
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "y*", &buf)) {
        return NULL;
    }
    auto out = ModernizedZlib::decompress_gzip(
        static_cast<const uint8_t*>(buf.buf), buf.len);
    PyBuffer_Release(&buf);
    return PyBytes_FromStringAndSize(reinterpret_cast<const char*>(out.data()),
                                     static_cast<Py_ssize_t>(out.size()));
}

static PyObject* py_adler32(PyObject* self, PyObject* args) {
    Py_buffer buf;
    unsigned int init = 1;
    if (!PyArg_ParseTuple(args, "y*|I", &buf, &init)) {
        return NULL;
    }
    uint32_t val = ModernizedZlib::adler32_modernized(
        init, static_cast<const uint8_t*>(buf.buf), buf.len);
    PyBuffer_Release(&buf);
    return PyLong_FromUnsignedLong(val);
}

static PyObject* py_crc32(PyObject* self, PyObject* args) {
    Py_buffer buf;
    unsigned int init = 0;
    if (!PyArg_ParseTuple(args, "y*|I", &buf, &init)) {
        return NULL;
    }
    uint32_t val = ModernizedZlib::crc32_modernized(
        init, static_cast<const uint8_t*>(buf.buf), buf.len);
    PyBuffer_Release(&buf);
    return PyLong_FromUnsignedLong(val);
}

static PyObject* py_monkey_patch(PyObject* self, PyObject* Py_UNUSED(args)) {
    PyObject* sys_mod = PyImport_ImportModule("sys");
    if (!sys_mod) return NULL;
    PyObject* modules_dict = PyObject_GetAttrString(sys_mod, "modules");
    Py_DECREF(sys_mod);
    if (!modules_dict) return NULL;

    PyObject* zlib_zero_mod = PyImport_ImportModule("zlib_zero");
    if (!zlib_zero_mod) {
        Py_DECREF(modules_dict);
        return NULL;
    }
    PyDict_SetItemString(modules_dict, "zlib", zlib_zero_mod);
    Py_DECREF(zlib_zero_mod);
    Py_DECREF(modules_dict);
    Py_RETURN_NONE;
}

static PyMethodDef ZlibZeroMethods[] = {
    {"compress_zlib", py_compress_zlib, METH_VARARGS, "Compress bytes using modernized C++20 zlib DEFLATE engine."},
    {"decompress_zlib", py_decompress_zlib, METH_VARARGS, "Decompress zlib bytes using modernized C++20 engine."},
    {"compress", py_compress_zlib, METH_VARARGS, "Drop-in alias for zlib.compress."},
    {"decompress", py_decompress_zlib, METH_VARARGS, "Drop-in alias for zlib.decompress."},
    {"compress_gzip", py_compress_gzip, METH_VARARGS, "Compress bytes into GZIP RFC 1952 format."},
    {"decompress_gzip", py_decompress_gzip, METH_VARARGS, "Decompress GZIP RFC 1952 bytes."},
    {"adler32", py_adler32, METH_VARARGS, "Compute Adler-32 checksum (SIMD-accelerated)."},
    {"crc32", py_crc32, METH_VARARGS, "Compute CRC-32 checksum (Hardware-accelerated)."},
    {"monkey_patch", py_monkey_patch, METH_NOARGS, "Globally replace Python's standard zlib with zlib_zero in sys.modules."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef zlibzeromodule = {
    PyModuleDef_HEAD_INIT,
    "zlib_zero",
    "High-Performance Modernized C++20 zlib Engine",
    -1,
    ZlibZeroMethods
};

PyMODINIT_FUNC PyInit_zlib_zero(void) {
    PyObject* m = PyModule_Create(&zlibzeromodule);
    if (!m) return NULL;

    // Standard zlib constants for 100% drop-in compatibility
    PyModule_AddIntConstant(m, "MAX_WBITS", 15);
    PyModule_AddIntConstant(m, "DEFLATED", 8);
    PyModule_AddIntConstant(m, "DEF_MEM_LEVEL", 8);
    PyModule_AddIntConstant(m, "Z_NO_COMPRESSION", 0);
    PyModule_AddIntConstant(m, "Z_BEST_SPEED", 1);
    PyModule_AddIntConstant(m, "Z_BEST_COMPRESSION", 9);
    PyModule_AddIntConstant(m, "Z_DEFAULT_COMPRESSION", -1);
    PyModule_AddIntConstant(m, "Z_SYNC_FLUSH", 2);
    PyModule_AddIntConstant(m, "Z_FULL_FLUSH", 3);
    PyModule_AddIntConstant(m, "Z_FINISH", 4);

    // Standard zlib.error exception
    PyObject* zlib_error = PyErr_NewException("zlib_zero.error", NULL, NULL);
    Py_XINCREF(zlib_error);
    PyModule_AddObject(m, "error", zlib_error);

    return m;
}
