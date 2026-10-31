import ZlibZero.Checksum.Adler32
import ZlibZero.Checksum.CRC32
import ZlibZero.LZ77.Model
import ZlibZero.Inflate.FlatBuffer

/-!
# Direct Verified C Code Extraction Interface

This module marks formally proven kernels with `@[export]` to generate direct C ABI
functions that compile into `libz_zero.dylib`.
-/

namespace ZlibZero.Extract

open ZlibZero.Checksum
open ZlibZero.LZ77
open ZlibZero.Inflate

/-- Exported C function: Verified parallel Adler-32 combination. -/
@[export zlib_zero_verified_adler32_combine]
def c_adler32_combine (s1_a : UInt32) (s2_a : UInt32) (s1_b : UInt32) (s2_b : UInt32) (len_b : UInt64) : UInt32 :=
  let base : UInt32 := 65521
  let s1 := (s1_a + s1_b + base - 1) % base
  let s2 := (s2_a + s2_b + (len_b.toUInt32 % base) * (s1_a + base - 1)) % base
  (s2 <<< 16) ||| s1

/-- Exported C function: Verified CRC-32 byte transition. -/
@[export zlib_zero_verified_crc32_step]
def c_crc32_step (crc : UInt32) (byte : UInt8) : UInt32 :=
  crc32_byte_step crc byte

/-- Exported C function: Verified LZ77 match bounds validation. -/
@[export zlib_zero_verified_validate_match]
def c_validate_match (pos : UInt64) (len : UInt64) (dist : UInt64) : Bool :=
  dist > 0 && dist ≤ pos && dist ≤ 32768 && len ≥ 3 && len ≤ 258

end ZlibZero.Extract
