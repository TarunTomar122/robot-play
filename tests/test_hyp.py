"""PROTOCOL.md v1.17: the notebook writer may write marked guesses; everything else about the notebook arm is unchanged."""
from robot_play.agent import HYP_SYSTEM, NOTEBOOK_SYSTEM, Memory, notebook_request, notebook_request_hyp, play_episode, update_memory
from robot_play.llm import FakeProvider
from robot_play.runner import build_specs


class Spy(FakeProvider):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.asked = []

    def complete(self, system, user):
        self.asked.append((system, user))
        return super().complete(system, user)


def test_the_fact_only_writer_is_unchanged_and_the_guess_writer_differs_only_in_allowing_marked_guesses():
    assert "never invent facts" in NOTEBOOK_SYSTEM and "never invent facts" not in HYP_SYSTEM
    assert "GUESS" in HYP_SYSTEM and "GUESS" in notebook_request_hyp("t", "n", "v", 1, 2, "x") and "GUESS" not in notebook_request("t", "n", "v", 1, 2, "x")
    base, hyp = notebook_request("t", "n", "v", 1, 2, "x"), notebook_request_hyp("t", "n", "v", 1, 2, "x")
    assert base.split("Rewrite the notebook now.")[0] == hyp.split("Rewrite the notebook now.")[0]            # same task, notebook, verdict and transcript block, same 300-word cap


def test_a_guess_notebook_is_written_with_the_guess_prompt_and_read_under_the_notebook_label():
    p = Spy([[("done", {})]], notebook_text="GUESS: the grip")
    mem = Memory("notebook_hyp")
    rec = play_episode(p, "mixed_silent", 10_000, True, mem)
    update_memory(p, mem, rec, "mixed_silent", "instr", 20)
    assert p.asked[0][0] == HYP_SYSTEM and mem.notebook == "GUESS: the grip"
    assert mem.prompt_block().startswith("\n\nYOUR NOTEBOOK, written by you after earlier attempts")
    p2 = Spy([[("done", {})]])
    mem2 = Memory("notebook")
    update_memory(p2, mem2, play_episode(p2, "mixed_silent", 10_000, True, mem2), "mixed_silent", "instr", 20)
    assert p2.asked[0][0] == NOTEBOOK_SYSTEM


def test_v1_17_cell_plans_one_twelve_episode_run_per_model_and_seed_on_the_silent_job():
    specs = build_specs("hyp", ["claude-haiku-5-5", "gpt-6-luna"], [40, 41], "runs/x")
    assert len(specs) == 4 and {(s.task, s.condition, s.practice, s.quirk) for s in specs} == {("mixed_silent", "notebook_hyp", 12, True)}
