#!/usr/bin/env python3
"""Check the ADPF profile's bounds and session lifetime policy."""
import json
from pathlib import Path
import unittest

CONFIG = Path(__file__).resolve().parents[1] / "powerhint.json"


class AdpfProfileTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG.read_text())

    def test_cpu_session_profile(self):
        profiles = self.config.get("AdpfConfig", [])
        self.assertEqual(len(profiles), 1)
        p = profiles[0]
        self.assertTrue(p["Name"])
        self.assertIs(p["PID_On"], True)
        self.assertIs(p["UclampMin_On"], True)
        self.assertLessEqual(0, p["UclampMin_Low"])
        self.assertLessEqual(p["UclampMin_Low"], p["UclampMin_Init"])
        self.assertLessEqual(p["UclampMin_Init"], p["UclampMin_High"])
        self.assertLessEqual(p["UclampMin_High"], 1024)
        self.assertLessEqual(p["UclampMin_LoadReset"], p["UclampMin_High"])
        self.assertLessEqual(p["UclampMin_LoadUp"], p["UclampMin_High"])
        self.assertGreater(p["PID_Po"], 0)
        self.assertGreater(p["PID_Pu"], 0)
        self.assertGreater(p["PID_I"], 0)
        self.assertLessEqual(p["PID_I_Low"], p["PID_I_Init"])
        self.assertLessEqual(p["PID_I_Init"], p["PID_I_High"])

    def test_votes_expire_and_only_supported_controls_are_enabled(self):
        p = self.config["AdpfConfig"][0]
        self.assertGreater(p["ReportingRateLimitNs"], 0)
        self.assertLessEqual(p["ReportingRateLimitNs"], 1_000_000_000 / 90)
        self.assertGreaterEqual(p["StaleTimeFactor"], 1.0)
        self.assertLessEqual(p["StaleTimeFactor"], 3.0)
        self.assertEqual(p["TargetTimeFactor"], 0.90)
        self.assertLessEqual(p["TargetTimeFactor"], 1.0)
        self.assertIs(p["GpuBoost"], False)
        self.assertNotIn("HeuristicBoost_On", p)


if __name__ == "__main__":
    unittest.main()
