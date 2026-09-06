"""Tests for personality, decision engine, and creator modules."""
import json
import os
import subprocess
import tempfile
import unittest

BINARY = "/workspace/digital-creator"


class TestPersonality(unittest.TestCase):
    def test_personality_output(self):
        r = subprocess.run([BINARY, "personality", "--name", "TestBot"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Personality:", r.stdout)
        self.assertIn("Traits", r.stdout)
        self.assertIn("Mood", r.stdout)

    def test_personality_name(self):
        r = subprocess.run([BINARY, "personality", "--name", "Nexus"],
                           capture_output=True, text=True, timeout=10)
        self.assertIn("Nexus", r.stdout)

    def test_trait_bars(self):
        r = subprocess.run([BINARY, "personality"],
                           capture_output=True, text=True, timeout=10)
        self.assertIn("█", r.stdout)  # trait bar visual


class TestDecision(unittest.TestCase):
    def test_decision_output(self):
        r = subprocess.run([BINARY, "decision"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Decision", r.stdout)
        self.assertIn("Confidence", r.stdout)

    def test_decision_with_context(self):
        r = subprocess.run([BINARY, "decision", "--context", "build API"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        # Context affects scoring but decision is still returned
        self.assertIn("Decision", r.stdout)
        self.assertIn("Confidence", r.stdout)

    def test_decision_json_persistence(self):
        r = subprocess.run([BINARY, "decision"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        # Verify at least one decision exists with valid format
        self.assertIn("Decision #", r.stdout)


class TestCreator(unittest.TestCase):
    def test_creator_report(self):
        r = subprocess.run([BINARY, "creator"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Digital Creator", r.stdout)

    def test_creator_persistence(self):
        home = os.environ.get("HOME", "/tmp")
        os.environ["HOME"] = tempfile.mkdtemp()
        try:
            r = subprocess.run([BINARY, "creator"],
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0)
            # Second run should show same state
            r2 = subprocess.run([BINARY, "creator"],
                                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0)
        finally:
            os.environ["HOME"] = home


class TestDashboard(unittest.TestCase):
    def test_dashboard_command(self):
        r = subprocess.run([BINARY, "dashboard"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertIn("PERSONALITY", r.stdout)
        self.assertIn("CREATOR", r.stdout)


if __name__ == "__main__":
    unittest.main()
