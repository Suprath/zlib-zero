import ZlibZero.Checksum.Adler32
import ZlibZero.LZ77.Model
import ZlibZero.Huffman.Canonical
import ZlibZero.Inflate.Inflate

/-!
# ZlibZero: Formally Verified High-Performance Compression Kernel in Lean 4

This library exposes mathematically proven kernels for:
- Adler-32 Checksum (RFC 1950) & Associative Block Combination
- LZ77 Token Factorization & Memory Safety Invariants (RFC 1951)
- Canonical Huffman Prefix-Free Codes & Kraft-McMillan bounds
- Verified Inflate state transitions
-/
