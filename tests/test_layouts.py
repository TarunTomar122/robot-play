"""Every layout the experiment plays can be built (found in round 5a: flasks layout seed 20801 could not be placed and crashed every run that reached it)."""
import numpy as np
import pytest

from robot_play.agent import eval_seeds, practice_seeds
from robot_play.env import TASKS


@pytest.mark.parametrize("task", ["stack", "bins", "flasks"])
def test_every_planned_layout_can_be_sampled_in_both_scenes(task):
    for rs in range(20):
        for seed in practice_seeds(rs) + eval_seeds(rs):
            for quirk in (True, False):
                TASKS[task].build(np.random.default_rng(seed), quirk)            # raises if the points cannot be placed


def test_the_retry_changes_only_layouts_that_used_to_crash():
    from robot_play.env import _sample_xy
    a = _sample_xy(np.random.default_rng(10_000), 4, x=(0.40, 0.56), y=(-0.28, 0.28), min_sep=0.14)
    b = _sample_xy(np.random.default_rng(10_000), 4, x=(0.40, 0.56), y=(-0.28, 0.28), min_sep=0.14)
    assert all(np.allclose(p, q) for p, q in zip(a, b))                                     # deterministic
