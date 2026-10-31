import ZlibZero.LZ77.Model

/-!
# Formal Verification of Bulk-Guarded Flat Buffer Decompression

This module formalizes:
1. Flat pre-allocated memory buffer state machine
2. Maximum token match length bound (MAX_MATCH = 258)
3. Bulk-guard theorem:
   Checking capacity once for MAX_MATCH guarantees that all subsequent literal
   writes and back-reference copies within that step are unconditionally bounds-safe,
   eliminating the need for per-byte capacity checks and zero-fill overhead.
-/

namespace ZlibZero.Inflate

open ZlibZero.LZ77

/-- A FlatBuffer represents a contiguous memory region with fixed capacity and current write offset. -/
structure FlatBuffer where
  capacity : Nat
  pos      : Nat
  h_pos    : pos ≤ capacity
  deriving Repr, DecidableEq

/-- Initial empty flat buffer with given total pre-allocated capacity. -/
def init_flat_buffer (cap : Nat) : FlatBuffer where
  capacity := cap
  pos      := 0
  h_pos    := Nat.zero_le cap

/-- Bulk capacity guard predicate: ensures buffer can accommodate at least MAX_MATCH (258) bytes. -/
def HasBulkCapacity (fb : FlatBuffer) : Prop :=
  fb.pos + MAX_MATCH ≤ fb.capacity

instance (fb : FlatBuffer) : Decidable (HasBulkCapacity fb) := by
  dsimp [HasBulkCapacity]
  infer_instance

/-- Theorem: If the bulk capacity guard holds, writing a single literal byte is strictly bounds-safe. -/
theorem bulk_guard_safe_literal (fb : FlatBuffer) (h : HasBulkCapacity fb) :
  fb.pos + 1 ≤ fb.capacity := by
  dsimp [HasBulkCapacity, MAX_MATCH] at h
  omega

/-- Theorem: If the bulk capacity guard holds, any valid LZ77 back-reference copy
    (length <= MAX_MATCH) is strictly bounds-safe without requiring per-byte reallocation checks. -/
theorem bulk_guard_safe_match (fb : FlatBuffer) (len : Nat)
    (h_bulk : HasBulkCapacity fb) (h_len : len ≤ MAX_MATCH) :
  fb.pos + len ≤ fb.capacity := by
  dsimp [HasBulkCapacity] at h_bulk
  omega

/-- State transition: advance write position by `len` bytes under proven safety. -/
def advance_flat_buffer (fb : FlatBuffer) (len : Nat) (h_safe : fb.pos + len ≤ fb.capacity) : FlatBuffer where
  capacity := fb.capacity
  pos      := fb.pos + len
  h_pos    := h_safe

/-- Theorem: Bulk buffer advancement is strictly monotonic. -/
theorem advance_monotonic (fb : FlatBuffer) (len : Nat) (h_safe : fb.pos + len ≤ fb.capacity) :
  (advance_flat_buffer fb len h_safe).pos ≥ fb.pos := by
  dsimp [advance_flat_buffer]
  omega

end ZlibZero.Inflate
