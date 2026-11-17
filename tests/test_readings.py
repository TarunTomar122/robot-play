"""The registered readings and scoring rules of the v1.13 and v1.14 sections of scripts/analyze.py."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("analyze", Path(__file__).resolve().parents[1] / "scripts" / "analyze.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


def test_the_done_rule_counts_a_physically_finished_but_undeclared_episode_as_a_failure():
    assert analyze.registered_solved({"success": True, "claimed_done": True}) == 1
    assert analyze.registered_solved({"success": True, "claimed_done": False}) == 0
    assert analyze.registered_solved({"success": False, "claimed_done": True}) == 0


def test_the_budget_reading_follows_the_registered_branches():
    assert "B1, B2 and B3 met" in analyze.reading_budget(["met", "met", "met"])
    r = analyze.reading_budget(["met", "MISSED (Haiku only)", "MISSED (Haiku only)"])
    assert "B2 (`flasks`) missed (Haiku only)" in r and "B3 (`bins`) missed (Haiku only)" in r and "B1" not in r
    r = analyze.reading_budget(["MISSED", "met", "MISSED (both)"])
    assert "B1 missed" in r and "B3 (`bins`) missed (both)" in r and "B2" not in r
    assert "(Haiku only)" in analyze.reading_budget(["met", "met", "MISSED (Haiku only) (scored with fewer than the planned pairs, above the floor)"])


def test_the_second_model_reading_covers_the_registered_cases_and_admits_the_gap():
    met, missed = "met", "MISSED"
    assert "also holds for a second" in analyze.reading_second([met, met, met, met, met], False)
    assert "Haiku-specific" in analyze.reading_second([met, missed, met, met, met], False)
    assert "does not cover this combination" in analyze.reading_second([met, met, missed, met, missed], False)
    assert "gate failed" in analyze.reading_second(["MISSED (stage 2 must not have run)", "void", "void", "void", "void"], True)
    assert "gate failed" in analyze.reading_second([missed, met, met, met, met], False)


def test_a_failed_validation_voids_every_prediction():
    pr = [("p1", "r1", "met"), ("p2", "r2", "MISSED")]
    assert all(x[2].startswith("void") for x in analyze.void_if([{"bad": 1}], pr))
    assert analyze.void_if([], pr) == pr
