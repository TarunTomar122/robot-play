"""Registered thresholds are compared with a tolerance, so float noise cannot flip a prediction that sits exactly on its threshold."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("analyze", Path(__file__).resolve().parents[1] / "scripts" / "analyze.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


def test_thresholds_on_the_line_pass_and_just_over_fails():
    assert 0.1 + 0.2 > 0.3 and analyze.at_most(0.1 + 0.2, 0.3)                      # the float trap itself
    assert analyze.at_least(0.9 - 0.3, 0.6) and analyze.at_least(0.65, 0.65) and analyze.at_most(0.65, 0.65)
    assert not analyze.at_most(0.66, 0.65) and not analyze.at_least(0.64, 0.65)
