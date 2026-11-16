"""IK, collision-checked planning and trajectory following for the Panda."""
from __future__ import annotations

import mujoco
import numpy as np

from .world import PandaWorld

R_DOWN = np.diag([1.0, -1.0, -1.0])   # tool z pointing down, finger axis along world y at yaw 0

SPEEDS = {"slow": 0.6, "normal": 1.2, "fast": 2.4}   # mean joint speed, rad/s


def rot_z(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def target_R(yaw: float) -> np.ndarray:
    return rot_z(yaw) @ R_DOWN


class IKFailure(Exception):
    pass


def ik(w: PandaWorld, pos: np.ndarray, yaw: float, q_seed: np.ndarray, iters: int = 300,
       pos_tol: float = 5e-4, rot_tol: float = 5e-3) -> np.ndarray:
    """Damped least squares to a top-down TCP pose. Raises IKFailure if it does not converge."""
    m, d = w.model, w.scratch
    d.qpos[:] = w.data.qpos
    Rt = target_R(yaw)
    q = np.clip(q_seed.copy(), w.q_lo, w.q_hi)
    jacp = np.zeros((3, m.nv))
    jacr = np.zeros((3, m.nv))
    for _ in range(iters):
        d.qpos[w.arm_qadr] = q
        mujoco.mj_kinematics(m, d)
        mujoco.mj_comPos(m, d)
        p = w.tcp(d)
        R = w.hand_R(d)
        e_pos = pos - p
        e_rot = 0.5 * sum(np.cross(R[:, i], Rt[:, i]) for i in range(3))
        if np.linalg.norm(e_pos) < pos_tol and np.linalg.norm(e_rot) < rot_tol:
            return q
        mujoco.mj_jac(m, d, jacp, jacr, p, w.hand_id)
        J = np.vstack([jacp[:, w.arm_dadr], jacr[:, w.arm_dadr]])
        err = np.concatenate([e_pos, e_rot])
        JJt = J @ J.T + (0.02 ** 2) * np.eye(6)
        dq = J.T @ np.linalg.solve(JJt, err)
        null = (np.eye(7) - J.T @ np.linalg.solve(JJt, J)) @ (0.5 * (PandaWorld.HOME_Q - q))
        dq = dq + 0.2 * null
        n = np.linalg.norm(dq)
        if n > 0.3:
            dq *= 0.3 / n
        q = np.clip(q + dq, w.q_lo, w.q_hi)
    raise IKFailure(f"no joint solution within tolerance for target {np.round(pos, 3).tolist()}")


def ik_best_yaw(w: PandaWorld, pos: np.ndarray, yaw: float, q_seed: np.ndarray) -> np.ndarray:
    """The hand is symmetric under a 180 degree turn, so try yaw and yaw + pi and keep the closer solution."""
    best, err = None, None
    for y in (yaw, yaw + np.pi, yaw - np.pi):
        try:
            q = ik(w, pos, y, q_seed)
        except IKFailure as e:
            err = e
            continue
        if best is None or np.linalg.norm(q - q_seed) < np.linalg.norm(best - q_seed):
            best = q
    if best is None:
        raise err
    return best


class Collision(Exception):
    def __init__(self, with_: list[str], where: str):
        self.with_ = sorted(set(with_))
        super().__init__(f"{where}: arm/hand would touch {', '.join(self.with_)}")


class Mover:
    """Owns collision checking, planning and execution for one world."""

    def __init__(self, w: PandaWorld):
        self.w = w
        self.held: str | None = None
        self.held_rel_pos = np.zeros(3)
        self.held_rel_R = np.eye(3)
        self.touched: set[str] = set()      # non-target bodies the arm touched during the last motion
        self.held_ignore: set[str] = set()  # supports the object was resting on when it was picked
        self.real_fingers = False           # True while a plain `move_to` is planned: the hand is then planned with the finger opening it really has, not with an open hand

    # ------------------------------------------------------------ held-object handling
    def attach(self, name: str):
        w = self.w
        R = w.hand_R()
        self.held = name
        self.held_rel_pos = R.T @ (w.obj_pos(name) - w.data.xpos[w.hand_id])
        self.held_rel_R = R.T @ w.data.xmat[w.obj_ids[name]].reshape(3, 3)
        self.held_ignore = set()
        gid = w.obj_ids[name]
        for i in range(w.data.ncon):
            c = w.data.contact[i]
            b1, b2 = int(w.model.geom_bodyid[c.geom1]), int(w.model.geom_bodyid[c.geom2])
            if gid in (b1, b2):
                other = b2 if b1 == gid else b1
                if other not in w.robot_bodies:
                    self.held_ignore.add("floor" if other == 0 else w.model.body(other).name)

    def detach(self):
        self.held = None
        self.held_ignore = set()

    def _place_held_in(self, d):
        w = self.w
        R = d.xmat[w.hand_id].reshape(3, 3)
        pos = d.xpos[w.hand_id] + R @ self.held_rel_pos
        Ro = R @ self.held_rel_R
        quat = np.zeros(4)
        mujoco.mju_mat2Quat(quat, Ro.flatten())
        adr = w.model.jnt_qposadr[w.model.joint(self.held + "_free").id]
        d.qpos[adr:adr + 3] = pos
        d.qpos[adr + 3:adr + 7] = quat

    def colliding(self, q: np.ndarray, ignore: set[str] = frozenset()) -> list[str]:
        """Bodies hit by the arm, the hand, or the held object at configuration q."""
        w = self.w
        d = w.scratch
        d.qpos[:] = w.data.qpos
        d.qpos[w.arm_qadr] = q
        if self.held is None and not self.real_fingers:
            d.qpos[w.finger_qadr] = 0.04
        mujoco.mj_kinematics(w.model, d)
        if self.held:
            self._place_held_in(d)
        mujoco.mj_forward(w.model, d)
        out = []
        moving = set(w.robot_bodies)
        if self.held:
            moving.add(w.obj_ids[self.held])
        link0 = w.model.body("link0").id
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = int(w.model.geom_bodyid[c.geom1]), int(w.model.geom_bodyid[c.geom2])
            m1, m2 = b1 in moving, b2 in moving
            if m1 == m2:
                continue
            mv, other = (b1, b2) if m1 else (b2, b1)
            if mv == link0 and other == 0:
                continue
            if self.held and mv == w.obj_ids[self.held] and other in w.robot_bodies:
                continue
            name = "floor" if other == 0 else w.model.body(other).name
            if self.held and mv == w.obj_ids[self.held] and name in self.held_ignore:
                continue
            if name not in ignore:
                out.append(name)
        return out

    # ------------------------------------------------------------ planning
    def _segment_free(self, qa, qb, ignore, step=0.05) -> bool:
        n = max(2, int(np.linalg.norm(qb - qa) / step))
        return all(not self.colliding(qa + (qb - qa) * t, ignore) for t in np.linspace(0, 1, n + 1))

    def _escape(self, q0: np.ndarray, ignore: set[str], start_hits: set[str]) -> list[np.ndarray]:
        """The arm starts in contact with something (for example the fingers pressed against a bin wall after letting go inside it).
        Lift the hand straight up in 2 cm steps until it is clear. The way out may not touch anything new, so this cannot be used to tunnel through an obstacle."""
        w = self.w
        d = w.scratch
        d.qpos[:] = w.data.qpos
        d.qpos[w.arm_qadr] = q0
        mujoco.mj_kinematics(w.model, d)
        p0, R = w.tcp(d), w.hand_R(d)
        M = R @ R_DOWN
        yaw = float(np.arctan2(M[1, 0], M[0, 0]))
        qs, q = [q0], q0
        for k in range(1, 16):
            try:
                q = ik_best_yaw(w, p0 + np.array([0.0, 0.0, 0.02 * k]), yaw, q)
            except IKFailure:
                break
            hits = set(self.colliding(q, ignore))
            if hits - start_hits:
                raise Collision(sorted(hits - start_hits), "retreat from contact")
            qs.append(q)
            if not hits:
                return qs
        raise Collision(sorted(start_hits), "start pose in contact, no way up")

    def plan(self, q0: np.ndarray, q1: np.ndarray, ignore: set[str] = frozenset(), rng=None) -> list[np.ndarray]:
        w = self.w
        hits = self.colliding(q1, ignore)
        if hits:
            raise Collision(hits, "goal pose")
        start_hits = set(self.colliding(q0, ignore))
        if start_hits:
            lift = self._escape(q0, ignore, start_hits)
            return lift + self.plan(lift[-1], q1, ignore, rng)[1:]
        if self._segment_free(q0, q1, ignore):
            return [q0, q1]
        rng = rng or np.random.default_rng(0)
        path = self._rrt_connect(q0, q1, ignore, rng)
        if path is None:
            raise Collision(self.colliding(q0 + (q1 - q0) * 0.5, ignore) or ["obstacle"], "no collision-free path")
        return self._shortcut(path, ignore, rng)

    def _rrt_connect(self, q0, q1, ignore, rng, iters=1500, step=0.2):
        lo, hi = self.w.q_lo, self.w.q_hi
        Ta, Tb = [(q0, -1)], [(q1, -1)]
        swapped = False
        for _ in range(iters):
            qr = rng.uniform(lo, hi)
            qa = self._extend(Ta, qr, step, ignore)
            if qa is not None:
                qb = self._connect(Tb, qa, step, ignore)
                if qb is not None:
                    pa = self._trace(Ta)
                    pb = self._trace(Tb)
                    path = pa + pb[::-1]
                    return path[::-1] if swapped else path
            Ta, Tb = Tb, Ta
            swapped = not swapped
        return None

    @staticmethod
    def _nearest(T, q):
        return min(range(len(T)), key=lambda i: np.linalg.norm(T[i][0] - q))

    def _extend(self, T, q, step, ignore):
        i = self._nearest(T, q)
        qn = T[i][0]
        dvec = q - qn
        dist = np.linalg.norm(dvec)
        qnew = q if dist <= step else qn + dvec / dist * step
        if self._segment_free(qn, qnew, ignore, 0.08):
            T.append((qnew, i))
            return qnew
        return None

    def _connect(self, T, q, step, ignore):
        while True:
            r = self._extend(T, q, step, ignore)
            if r is None:
                return None
            if np.linalg.norm(r - q) < 1e-6:
                return r

    @staticmethod
    def _trace(T):
        out, i = [], len(T) - 1
        while i != -1:
            out.append(T[i][0])
            i = T[i][1]
        return out[::-1]

    def _shortcut(self, path, ignore, rng, tries=60):
        path = list(path)
        for _ in range(tries):
            if len(path) < 3:
                break
            i, j = sorted(rng.choice(len(path), 2, replace=False))
            if j - i > 1 and self._segment_free(path[i], path[j], ignore, 0.08):
                path = path[:i + 1] + path[j:]
        return path

    # ------------------------------------------------------------ execution
    def follow(self, path: list[np.ndarray], speed: str = "normal"):
        """Run a joint-space polyline with ONE min-jerk profile over its whole arc length (no stop-and-go at waypoints)."""
        w = self.w
        vmean = SPEEDS[speed]
        self.touched = set()
        pts = [np.asarray(q, float) for q in path]
        seg = np.array([float(np.max(np.abs(b - a))) for a, b in zip(pts[:-1], pts[1:])])
        L = float(seg.sum())
        if L > 1e-9:
            cum = np.concatenate([[0.0], np.cumsum(seg)])
            T = max(0.35, L / vmean)
            n = int(T / w.model.opt.timestep)
            for k in range(1, n + 1):
                u = k / n
                u = 10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5
                d = u * L
                i = min(int(np.searchsorted(cum, d, side="right")) - 1, len(seg) - 1)
                f = 0.0 if seg[i] < 1e-12 else (d - cum[i]) / seg[i]
                w.data.ctrl[:7] = pts[i] + (pts[i + 1] - pts[i]) * f
                w.step(1)
                if k % 25 == 0:
                    for name in w.robot_contacts(ignore={self.held} if self.held else set()):
                        self.touched.add(name)
        w.data.ctrl[:7] = path[-1]
        w.step(int(0.15 / w.model.opt.timestep))
