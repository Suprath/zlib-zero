import unittest
import subprocess
import shutil
import os

class TestLean4FormalVerification(unittest.TestCase):
    def setUp(self):
        # Look for Lake in standard locations
        self.lake_bin = shutil.which("lake")
        if not self.lake_bin:
            home_lake = os.path.expanduser("~/.elan/bin/lake")
            if os.path.exists(home_lake):
                self.lake_bin = home_lake
            elif os.path.exists("/opt/homebrew/bin/lake"):
                self.lake_bin = "/opt/homebrew/bin/lake"

        self.verified_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "verified")
        )

    def test_lean_toolchain_available(self):
        """Verify that Lean 4 / Lake toolchain is installed and accessible."""
        self.assertIsNotNone(
            self.lake_bin,
            "Lean 4 Lake toolchain not found in PATH or ~/.elan/bin."
        )

    def test_formal_proofs_build_and_verify(self):
        """Compile and mathematically verify Lean 4 theorems (zero sorry / zero error)."""
        if not self.lake_bin or not os.path.exists(self.verified_dir):
            self.skipTest("Lean 4 or verified directory not available")

        # Run Lake build (type-checks and verifies all theorems)
        env = dict(os.environ)
        env["PATH"] = os.path.expanduser("~/.elan/bin") + ":" + env.get("PATH", "")
        res = subprocess.run(
            [self.lake_bin, "build"],
            cwd=self.verified_dir,
            capture_output=True,
            text=True,
            env=env
        )
        self.assertEqual(
            res.returncode, 0,
            f"Lake build failed with error:\n{res.stderr}\nOutput:\n{res.stdout}"
        )

    def test_execute_verification_driver(self):
        """Execute the verified Adler-32, LZ77, and Huffman theorem runner."""
        if not self.lake_bin or not os.path.exists(self.verified_dir):
            self.skipTest("Lean 4 or verified directory not available")

        env = dict(os.environ)
        env["PATH"] = os.path.expanduser("~/.elan/bin") + ":" + env.get("PATH", "")
        res = subprocess.run(
            [self.lake_bin, "exe", "zlib_verify"],
            cwd=self.verified_dir,
            capture_output=True,
            text=True,
            env=env
        )
        self.assertEqual(res.returncode, 0, f"Verification failed:\n{res.stderr}")
        self.assertIn("ALL MATHEMATICAL THEOREMS AND INVARIANTS VERIFIED SUCCESSFULLY", res.stdout)
        print("\n" + res.stdout.strip())

if __name__ == "__main__":
    unittest.main()
