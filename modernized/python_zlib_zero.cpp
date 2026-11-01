#define PY_SSIZE_T_CLEAN
#include <Python.h>
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
    return PyBytes_FromStringAndSize(reinterpret_cast<const char*>(out.data()), out.size());
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
        PyObject* res = PyBytes_FromStringAndSize(NULL, est_cap);
        if (!res) {
            PyBuffer_Release(&buf);
            return PyErr_NoMemory();
        }

        uint8_t* dst = reinterpret_cast<uint8_t*>(PyBytes_AS_STRING(res));
        size_t actual_sz = ModernizedZlib::decompress_zlib_into(dst, est_cap, in_data, in_len);
        if (actual_sz > 0) {
            PyBuffer_Release(&buf);
            if (_PyBytes_Resize(&res, actual_sz) < 0) {
                return NULL;
            }
            return res;
        }
        Py_DECREF(res);
    }

    // Dynamic single-pass path
    auto out = ModernizedZlib::decompress_zlib(in_data, in_len);
    PyBuffer_Release(&buf);
    return PyBytes_FromStringAndSize(reinterpret_cast<const char*>(out.data()), out.size());
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
    return PyBytes_FromStringAndSize(reinterpret_cast<const char*>(out.data()), out.size());
}

static PyObject* py_decompress_gzip(PyObject* self, PyObject* args) {
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "y*", &buf)) {
        return NULL;
    }
    auto out = ModernizedZlib::decompress_gzip(
        static_cast<const uint8_t*>(buf.buf), buf.len);
    PyBuffer_Release(&buf);
    return PyBytes_FromStringAndSize(reinterpret_cast<const char*>(out.data()), out.size());
}

static PyMethodDef ZlibZeroMethods[] = {
    {"compress_zlib", py_compress_zlib, METH_VARARGS, "Compress bytes using modernized C++20 zlib DEFLATE engine."},
    {"decompress_zlib", py_decompress_zlib, METH_VARARGS, "Decompress zlib bytes using modernized C++20 engine."},
    {"compress_gzip", py_compress_gzip, METH_VARARGS, "Compress bytes into GZIP RFC 1952 format."},
    {"decompress_gzip", py_decompress_gzip, METH_VARARGS, "Decompress GZIP RFC 1952 bytes."},
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
    return PyModule_Create(&zlibzeromodule);
}
