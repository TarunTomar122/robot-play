"""Physical disturbances (PROTOCOL.md section 8). They act through the simulator, never by editing state.

slip : the gripper is commanded open for 0.15 s once the held object has been lifted 3 cm above where it was picked.
nudge: a lateral force acts on an object for 0.3 s the first time the open hand descends next to it (before any grasp).
Each fires at most once per episode, at an event rather than a wall-clock time, so experienced and fresh agents get the same disturbance.
"""
from __future__ import annotations

import numpy as np

SLIP_DURATION = 0.15
NUDGE_DURATION = 0.3
NUDGE_FORCE_G = 1.1            # lateral force as a multiple of the object's weight (floor friction coefficient is 1.0)


class Disturbance:
    def __init__(self, kind: str, seed: int):
        assert kind in ("slip", "nudge")
        self.kind = kind
        self.fired = False
        self.fired_at: float | None = None
        self.rng = np.random.default_rng(10_000 + seed)
        self._until: float | None = None
        self._saved_ctrl: float | None = None
        self._push: tuple[int, np.ndarray] | None = None
        self._rise0: float | None = None

    def attach(self, env):
        env.w.hooks.append(lambda: self.step(env))

    # called by the world every 50 ms of simulated time, whatever the arm is doing
    def step(self, env):
        w, mv = env.w, env.skills.mv
        if self.kind == "slip":
            if self._until is not None:                       # a slip is in progress: restore the previous command when it ends
                if w.time >= self._until:
                    w.data.ctrl[7] = self._saved_ctrl
                    self._until = None
                return
            if self.fired or not mv.held:
                return
            if self._rise0 is None:
                self._rise0 = float(w.obj_pos(mv.held)[2])
            if w.obj_pos(mv.held)[2] - self._rise0 >= 0.03:
                self.fired, self.fired_at = True, w.time
                self._saved_ctrl = float(w.data.ctrl[7])
                w.data.ctrl[7] = w.GRIP_OPEN
                self._until = w.time + SLIP_DURATION
        else:
            if self._push is not None:
                bid, f = self._push
                if w.time >= self._until:
                    w.data.xfrc_applied[bid, :3] = 0
                    self._push = None
                return
            if self.fired or mv.held:
                return
            tcp = w.tcp()
            for o in w.scene.objects:
                p = w.obj_pos(o.name)
                top = p[2] + (o.size[2] if o.shape == "box" else o.size[1])
                if np.linalg.norm(tcp[:2] - p[:2]) < 0.03 and tcp[2] < top + 0.06:
                    # shoved from the front or the back (within 45 degrees of the x axis): sideways pushes would be caught by the open fingers
                    ang = self.rng.choice([0.0, np.pi]) + self.rng.uniform(-np.pi / 4, np.pi / 4)
                    mass = float(w.model.body_mass[w.obj_ids[o.name]])
                    f = NUDGE_FORCE_G * mass * 9.81 * np.array([np.cos(ang), np.sin(ang), 0.0])
                    bid = w.obj_ids[o.name]
                    w.data.xfrc_applied[bid, :3] = f
                    self._push, self._until = (bid, f), w.time + NUDGE_DURATION
                    self.fired, self.fired_at = True, w.time
                    return
