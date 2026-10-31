import Lake
open Lake DSL

package «verified» where
  version := v!"0.1.0"
  keywords := #["compression", "zlib", "formal-verification"]

lean_lib «ZlibZero» where
  roots := #[`ZlibZero]

@[default_target]
lean_exe «zlib_verify» where
  root := `Main
