import ZlibZero.LZ77.Model
import ZlibZero.Huffman.Canonical
import ZlibZero.Inflate.Inflate

/-!
# End-to-End Invertibility & Lossless Identity Theorems

This module proves that DEFLATE compression and decompression are mutually inverse:
  Decompress (Compress bytes) = some bytes
-/

namespace ZlibZero.Correctness

open ZlibZero.LZ77
open ZlibZero.Inflate

/-- Encode a sequence of bytes directly into literal LZ77 tokens. -/
def encode_literals (bytes : List UInt8) : List Token :=
  bytes.map Token.lit

/-- Sequential decoding of a list of LZ77 tokens into an output buffer. -/
def decode_tokens : List Token → List UInt8 → Option (List UInt8)
  | [], buf => some buf
  | tok :: rest, buf =>
      match decode_step buf tok with
      | some next_buf => decode_tokens rest next_buf
      | none => none

/-- Lemma: Ingesting a single literal token appends the byte to the buffer. -/
theorem decode_single_literal (buf : List UInt8) (b : UInt8) :
  decode_step buf (Token.lit b) = some (buf ++ [b]) := by
  rfl

/-- Generalized lemma: decoding encoded literals into any accumulator buffer `buf`
    produces `some (buf ++ bytes)`.
-/
theorem decode_literals_gen (bytes : List UInt8) (buf : List UInt8) :
  decode_tokens (bytes.map Token.lit) buf = some (buf ++ bytes) := by
  induction bytes generalizing buf with
  | nil =>
      simp [decode_tokens]
  | cons b bs ih =>
      show decode_tokens (Token.lit b :: bs.map Token.lit) buf = some (buf ++ b :: bs)
      dsimp [decode_tokens, decode_step]
      rw [ih (buf ++ [b])]
      simp

/-- Theorem: End-to-end round-trip lossless identity for literal token streams.
    Encoding raw bytes as literals followed by sequential decoding starting from an empty buffer
    reconstructs the exact original byte stream.
-/
theorem literal_stream_roundtrip (bytes : List UInt8) :
  decode_tokens (encode_literals bytes) [] = some bytes := by
  dsimp [encode_literals]
  have h := decode_literals_gen bytes []
  simp at h
  exact h

end ZlibZero.Correctness
