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


def test_who_missed_names_the_model_and_the_reading_skips_a_model_with_no_room():
    assert analyze.who_missed([("Haiku", True), ("Luna", True)]) == "met"
    assert analyze.who_missed([("Haiku", True), ("Luna", False)]) == "MISSED (Luna)"
    assert analyze.who_missed([("Haiku", False), ("Luna", False)]) == "MISSED (Haiku and Luna)"
    st = ["MISSED (Haiku and Luna)", "MISSED (Luna)", "MISSED (Luna)", "met", "met", "met"]           # the v1.15 outcome: Luna had no room, so its M3 miss is not read
    r = analyze.reading_mixed(st)
    assert "M1 missed for Haiku and Luna" in r and "M2 missed for Luna" in r and "M3 missed" not in r and "all met" not in r
    assert "M3 missed for Haiku" in analyze.reading_mixed(["met", "met", "MISSED (Haiku)", "met", "met", "met"])
    assert "M6 missed for Luna" in analyze.reading_mixed(["met", "met", "met", "met", "met", "MISSED (Luna)"])
    assert "M4 missed (notebook above the answer key: Luna)" in analyze.reading_mixed(["met", "met", "met", "MISSED (notebook above the answer key: Luna)", "met", "met"])
    assert "M1 to M6 all met" in analyze.reading_mixed(["met"] * 6)


def test_pick_flags_count_squeeze_refusals_and_silent_failed_picks_separately():
    from robot_play.analysis import pick_flags
    log = [{"tool": "pick", "result": {"ok": False, "error": "squeeze limit exceeded on cube_blue: the fingers pressed with 5.2 N, it takes at most 3.5 N; the hand let go"}},
           {"tool": "pick", "result": {"ok": False, "holding": None}}, {"tool": "pick", "result": {"ok": True}},
           {"tool": "pick", "result": {"ok": False, "error": "unreachable"}}, {"tool": "place", "result": {"ok": False}}]
    assert pick_flags(log) == {"squeezed": 1, "silent_pick": 1} and pick_flags(None) == {"squeezed": 0, "silent_pick": 0}


def test_v1_16_reading_skips_a_model_with_no_room_and_names_each_miss():
    assert "S1 to S6 all met" in analyze.reading_silent(["met"] * 6)
    r = analyze.reading_silent(["met", "MISSED (Luna)", "met", "MISSED (Haiku)", "met", "met"])
    assert "S2 missed for Luna" in r and "S4 missed for Haiku" in r and "S1 missed" not in r and "all met" not in r
    r2 = analyze.reading_silent(["met", "met", "MISSED (Luna)", "MISSED (Luna)", "met", "MISSED (Luna)"])
    assert "S3 missed for Luna" in r2 and "S4 missed" not in r2 and "S6 missed" not in r2
