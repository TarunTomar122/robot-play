"""Agent-facing skill tools. Everything returned is a measured fact from the simulator."""
from __future__ import annotations

import numpy as np

from .motion import Collision, IKFailure, Mover, ik_best_yaw
from .world import PandaWorld

GRIP = {"light": 100.0, "normal": 60.0, "firm": 0.0}
CLEARANCE = 0.12          # hover height above the highest thing in the way


def _r(x, n=3):
    return [round(float(v), n) for v in x]


class Skills:
    def __init__(self, w: PandaWorld, targets: dict | None = None):
        self.w = w
        self.mv = Mover(w)
        self.targets = targets or {}      # zones the agent can place on: name -> (x, y, support_top_z)
        self.sim_time0 = w.time
        self.calls = 0
        self.yaw = 0.0

    # ------------------------------------------------------------------ helpers
    def _top(self, name: str) -> float:
        return float(self.w.obj_pos(name)[2] + self._half_h(name))

    def _half_h(self, name: str) -> float:
        for o in self.w.scene.objects:
            if o.name == name:
                return o.size[2] if o.shape == "box" else o.size[1]
        raise KeyError(name)

    def _obj(self, name: str):
        for o in self.w.scene.objects:
            if o.name == name:
                return o
        return None

    def _tcp_to(self, pos, yaw, speed, ignore=frozenset(), straight=False):
        w, mv = self.w, self.mv
        q = ik_best_yaw(w, np.asarray(pos, float), yaw, w.q)
        path = mv.plan(w.q, q, set(ignore))
        mv.follow(path, speed)

    def _descend(self, pos, yaw, speed, ignore):
        """Straight-line Cartesian move in small steps, collision checked."""
        w, mv = self.w, self.mv
        p0 = w.tcp()
        n = max(2, int(np.linalg.norm(np.asarray(pos) - p0) / 0.02))
        qs, q = [w.q], w.q
        for t in np.linspace(0, 1, n + 1)[1:]:
            q = ik_best_yaw(w, p0 + (np.asarray(pos) - p0) * t, yaw, q)
            hits = mv.colliding(q, set(ignore))
            if hits:
                raise Collision(hits, "straight move")
            qs.append(q)
        mv.follow(qs, speed)

    def _retreat(self, p, yaw, z_hover, ignore):
        """After a failed grasp, lift straight back up so the next call starts from a clear hover pose."""
        try:
            self._descend([p[0], p[1], z_hover], yaw, "normal", {ignore})
        except (IKFailure, Collision):
            pass

    def _fail(self, reason: str, **extra):
        return {"ok": False, "error": reason, **extra}

    def _refresh_held(self):
        """The hand only holds what both fingers still touch. If the object has slipped out (or was knocked away), forget it: `observe` and `close_gripper` then
        say what is true, and the planner treats the object as an obstacle again instead of as part of the hand."""
        if self.mv.held and self.w.fingers_touching(self.mv.held) < 2:
            self.mv.detach()

    # ------------------------------------------------------------------ tools
    def observe(self) -> dict:
        self._refresh_held()
        w = self.w
        objs = []
        for o in w.scene.objects:
            p = w.obj_pos(o.name)
            sz = [2 * o.size[0], 2 * o.size[1], 2 * o.size[2]] if o.shape == "box" else [2 * max(o.size[0], o.base[0] if o.base else 0), 2 * max(o.size[0], o.base[0] if o.base else 0), 2 * o.size[1]]
            objs.append({"name": o.name, "shape": o.shape, "size_xyz_m": _r(sz), "position_m": _r(p),
                         "tilt_deg": round(w.obj_tilt_deg(o.name), 1), "held": o.name == self.mv.held})
        zones = [{"name": k, "center_xy_m": _r(v["xy"]), "outer_size_xyz_m": _r(v["size"])} for k, v in self.targets.items()]
        return {"objects": objs, "zones": zones,
                "gripper": {"width_m": round(w.gripper_width(), 3), "holding": self.mv.held},
                "tcp_m": _r(w.tcp()), "sim_time_s": round(w.time - self.sim_time0, 1)}

    def open_gripper(self) -> dict:
        self.w.set_gripper(False)
        self.w.settle(0.4)
        self.mv.detach()
        return {"ok": True, "gripper_width_m": round(self.w.gripper_width(), 3)}

    def close_gripper(self, grip_level: str = "normal") -> dict:
        if grip_level not in GRIP:
            return self._fail("grip_level must be light|normal|firm")
        self._refresh_held()
        self.w.data.ctrl[7] = GRIP[grip_level]
        self.w.settle(0.5)
        self._refresh_held()
        if not self.mv.held:                       # an object squeezed between both fingers is part of the hand from now on: the planner carries it and does not treat it as an obstacle
            width = self.w.gripper_width()
            for o in self.w.scene.objects:
                narrow = 2 * min(o.size[0], o.size[1]) if o.shape == "box" else 2 * o.size[0]       # its narrowest horizontal extent: a cube's side, a flask's diameter
                if self.w.fingers_touching(o.name) == 2 and width >= narrow - 0.008:               # fingertips resting on top of the object touch it with both fingers but have nothing between them
                    self.mv.attach(o.name)
                    break
        return {"ok": True, "gripper_width_m": round(self.w.gripper_width(), 3), "holding": self.mv.held}

    def home(self, speed: str = "normal") -> dict:
        try:
            path = self.mv.plan(self.w.q, PandaWorld.HOME_Q)
        except Collision as e:
            return self._fail(str(e))
        self.mv.follow(path, speed)
        return {"ok": True, "tcp_m": _r(self.w.tcp())}

    def move_to(self, x: float, y: float, z: float, speed: str = "normal") -> dict:
        try:
            self._tcp_to([x, y, z], self.yaw, speed)
        except (IKFailure, Collision) as e:
            return self._fail(str(e))
        self.w.settle(0.3)                          # let anything hanging in the fingers stop swinging before the next command
        self._refresh_held()
        return {"ok": True, "tcp_m": _r(self.w.tcp()), "touched": sorted(self.mv.touched)}

    def pick(self, object: str, grasp_height: float = 0.6, speed: str = "normal", grip_level: str = "normal",
             yaw_offset_deg: float = 0.0, lift_height: float = 0.15) -> dict:
        w, mv = self.w, self.mv
        o = self._obj(object)
        if o is None:
            return self._fail(f"unknown object '{object}'")
        if mv.held:
            return self._fail(f"already holding {mv.held}")
        if speed not in ("slow", "normal", "fast") or grip_level not in GRIP:
            return self._fail("speed must be slow|normal|fast and grip_level light|normal|firm")
        grasp_height = float(np.clip(grasp_height, 0.0, 1.0))
        lift_height = float(np.clip(lift_height, 0.05, 0.4))
        w.set_gripper(False)
        w.settle(0.3)
        p = w.obj_pos(object)
        h = 2 * self._half_h(object)
        base = p[2] - self._half_h(object)
        # grip across the narrower horizontal extent of a box; any direction for a cylinder
        yaw = 0.0
        if o.shape == "box":
            R = w.data.xmat[w.obj_ids[object]].reshape(3, 3)
            yaw = float(np.arctan2(R[1, 0], R[0, 0]))
            if o.size[0] > o.size[1] + 1e-6:
                yaw += np.pi / 2
        yaw += np.radians(yaw_offset_deg)
        z_grasp = max(0.012, base + grasp_height * h)
        z_hover = max(self._top(object), 0.0) + CLEARANCE + 0.05
        z_before = float(p[2])
        # a square block can be gripped across either pair of faces: try the other if the first is blocked
        yaws = [yaw] + ([yaw + np.pi / 2] if o.shape == "box" and abs(o.size[0] - o.size[1]) < 1e-6 else [])
        err = None
        for yaw in yaws:
            try:
                self._tcp_to([p[0], p[1], z_hover], yaw, speed)
                self._descend([p[0], p[1], z_grasp], yaw, speed, ignore={object})
                err = None
                break
            except (IKFailure, Collision) as e:
                err = e
                try:
                    self._descend([p[0], p[1], z_hover], yaw, "normal", {object})
                except (IKFailure, Collision):
                    pass
        if err is not None:
            return self._fail(str(err))
        stop_err = float(np.linalg.norm(w.tcp() - np.array([p[0], p[1], z_grasp])))
        if stop_err > 0.012:
            r = self._fail(f"hand stopped {stop_err * 100:.1f} cm short of the requested grasp point",
                           tcp_m=_r(w.tcp()), touched=sorted(mv.touched))
            self._retreat(p, yaw, z_hover, object)
            return r
        w.set_gripper(True)
        w.data.ctrl[7] = GRIP[grip_level]
        w.settle(0.5)
        width = w.gripper_width()
        if width < 0.004:
            self.open_gripper()
            self._retreat(p, yaw, z_hover, object)
            return self._fail("fingers closed on nothing", gripper_width_m=round(width, 3))
        mv.attach(object)
        z_up = float(w.tcp()[2] + lift_height)
        try:
            self._descend([w.tcp()[0], w.tcp()[1], z_up], yaw, speed, set(mv.held_ignore) | {object})
        except (IKFailure, Collision) as e:
            return self._fail(str(e), gripper_width_m=round(width, 3), holding=mv.held)
        w.settle(1.0)                              # hold still for a second, so an object that is slipping out of the fingers is not reported as held
        mv.held_ignore = set()
        p1 = w.obj_pos(object)
        rise = float(p1[2] - z_before)
        near = float(np.linalg.norm(p1 - w.tcp()))
        holding = rise > 0.5 * lift_height and near < 0.08
        if not holding:
            mv.detach()
        return {"ok": bool(holding), "holding": object if holding else None,
                "gripper_width_m": round(w.gripper_width(), 3),
                "object_rise_m": round(rise, 3), "requested_lift_m": round(lift_height, 3),
                "object_tilt_deg": round(w.obj_tilt_deg(object), 1), "touched": sorted(mv.touched)}

    def _support(self, target: str):
        if target in self.targets:
            t = self.targets[target]
            xy = np.array(t["xy"], float)
            for dx, dy in t.get("slots", []):            # zones with slots: use the first free one
                cand = xy + [dx, dy]
                if all(np.linalg.norm(self.w.obj_pos(o.name)[:2] - cand) > 0.03 for o in self.w.scene.objects if o.name != self.mv.held):
                    xy = cand
                    break
            return xy, float(t["top_z"]), set(t.get("ignore", [target]))
        o = self._obj(target)
        if o is not None:
            p = self.w.obj_pos(target)
            return p[:2].copy(), float(p[2] + self._half_h(target)), {target}
        return None

    def place(self, target: str, release_height: float = 0.02, speed: str = "normal", settle_time: float = 0.3) -> dict:
        w, mv = self.w, self.mv
        self._refresh_held()
        if not mv.held:
            return self._fail("not holding anything")
        sup = self._support(target)
        if sup is None:
            return self._fail(f"unknown target '{target}'")
        xy, top_z, ignore = sup
        name = mv.held
        release_height = float(np.clip(release_height, 0.0, 0.3))
        yaw = self.yaw
        # carry the object above the target, let it stop swinging, then measure where it sits in the grip
        bottom = w.obj_pos(name)[2] - self._half_h(name)
        z_hover = max(top_z + 0.30, w.tcp()[2] - bottom + top_z + release_height + 0.05)
        try:
            self._tcp_to([xy[0], xy[1], z_hover], yaw, speed)
        except (IKFailure, Collision) as e:
            return self._fail(str(e), holding=mv.held)
        w.settle(0.25)
        off = w.obj_pos(name)[:2] - w.tcp()[:2]          # aim the object, not the hand
        bottom = w.obj_pos(name)[2] - self._half_h(name)
        dz = float(w.tcp()[2] - bottom)
        z_release = top_z + release_height + dz
        try:
            self._descend([xy[0] - off[0], xy[1] - off[1], z_release], yaw, speed,
                          ignore=ignore | {"floor"} if release_height < 0.005 else ignore)
        except (IKFailure, Collision) as e:
            return self._fail(str(e), holding=mv.held)
        for _ in range(2):                                 # closed-loop alignment: the object can shift in the grip during the descent
            resid = xy - w.obj_pos(name)[:2]
            if np.linalg.norm(resid) < 0.002:
                break
            try:
                self._descend([w.tcp()[0] + resid[0], w.tcp()[1] + resid[1], w.tcp()[2]], yaw, "slow", ignore)
            except (IKFailure, Collision):
                break
            w.settle(0.15)
        self.open_gripper()
        w.settle(settle_time)
        z_up = float(w.tcp()[2] + 0.15)
        try:                                              # straight up, so the open fingers do not sweep the object over
            self._descend([w.tcp()[0], w.tcp()[1], z_up], yaw, "normal", {name})
        except (IKFailure, Collision):
            pass
        w.settle(0.4)
        p = w.obj_pos(name)
        return {"ok": True, "released": name, "object_position_m": _r(p), "object_tilt_deg": round(w.obj_tilt_deg(name), 1),
                "touched": sorted(mv.touched)}

    def done(self) -> dict:
        return {"ok": True}
