import ZlibZero.Checksum.Adler32
import ZlibZero.Checksum.CRC32
import ZlibZero.LZ77.Model
import ZlibZero.Huffman.Canonical
import ZlibZero.Inflate.Inflate
import ZlibZero.Inflate.FlatBuffer
import ZlibZero.Correctness.Invertibility
import ZlibZero.Extract.VerifiedInflate

/-!
# ZlibZero: Formally Verified High-Performance Compression Kernel in Lean 4

This library exposes mathematically proven kernels for:
- Adler-32 Checksum (RFC 1950) & Associative Block Combination
- CRC-32 Polynomial Field Arithmetic (RFC 1952)
- LZ77 Token Factorization & Memory Safety Invariants (RFC 1951)
- Bulk-Guarded Flat Buffer Bounds Safety Theorems
- Canonical Huffman Prefix-Free Codes & Kraft-McMillan bounds
- Verified Inflate state transitions
- End-to-End Invertibility & Lossless Identity Theorems
- Direct C ABI Code Extraction (@[export])
-/
