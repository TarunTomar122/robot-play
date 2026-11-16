"""MuJoCo world: robot + work surface + objects, with physics stepping and collision helpers.

Everything the agent can observe or be scored on is read from the simulator state here; nothing is
decided by the language model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import mujoco
import numpy as np

from .assets import model_dir

BOX = mujoco.mjtGeom.mjGEOM_BOX
CYL = mujoco.mjtGeom.mjGEOM_CYLINDER


@dataclass
class ObjectSpec:
    name: str
    shape: str                     # "box" | "cylinder"
    size: tuple                    # box: half extents (x,y,z); cylinder: (radius, half_height, 0)
    pos: tuple                     # initial x, y (z is set so it rests on the floor)
    rgba: tuple = (0.8, 0.8, 0.8, 1)
    mass: float = 0.05
    friction: tuple = (1.0, 0.01, 0.001)
    com_z: float | None = None     # centre of mass height above the object's base (None = centre)
    yaw: float = 0.0
    base: tuple | None = None          # (radius, height) of a wide base under a cylinder's neck


@dataclass
class StaticSpec:
    """Fixed geometry: bins, walls, target pads."""
    name: str
    shape: str
    size: tuple
    pos: tuple
    rgba: tuple = (0.5, 0.5, 0.5, 1)
    collide: bool = True


@dataclass
class SceneSpec:
    objects: list[ObjectSpec] = field(default_factory=list)
    statics: list[StaticSpec] = field(default_factory=list)


TORSION = 0.03                # torsional friction coefficient [m]; keeps a held block from pivoting in the pads
GRIP_FORCE_SCALE = 5.0        # Menagerie's tendon gains give ~2 N firm; x5 gives ~10 N per pad


class PandaWorld:
    ARM = [f"joint{i}" for i in range(1, 8)]
    HOME_Q = np.array([0, -0.2, 0, -2.2, 0, 2.0, -0.7853])
    TCP_OFFSET = np.array([0, 0, 0.1034])     # fingertip centre in the hand frame
    GRIP_OPEN, GRIP_CLOSED = 255.0, 0.0

    def __init__(self, scene: SceneSpec):
        self.scene = scene
        spec = mujoco.MjSpec.from_file(str(model_dir("franka_emika_panda") / "scene.xml"))
        spec.geom("floor").friction = [1.0, 0.005, 0.0001]
        wb = spec.worldbody
        for s in scene.statics:
            b = wb.add_body(name=s.name, pos=[*s.pos[:2], 0])
            geom = b.add_geom(name=s.name + "_g", type=BOX if s.shape == "box" else CYL,
                              size=list(s.size), pos=[0, 0, s.pos[2]], rgba=list(s.rgba))
            if not s.collide:
                geom.contype = 0
                geom.conaffinity = 0
        for o in scene.objects:
            z0 = o.size[2] if o.shape == "box" else o.size[1]
            b = wb.add_body(name=o.name, pos=[o.pos[0], o.pos[1], z0 + 0.001],
                            quat=[np.cos(o.yaw / 2), 0, 0, np.sin(o.yaw / 2)])
            b.add_freejoint(name=o.name + "_free")
            g = b.add_geom(name=o.name + "_g", type=BOX if o.shape == "box" else CYL,
                           size=list(o.size), rgba=list(o.rgba), mass=o.mass * (0.2 if o.base else 1.0),
                           friction=[o.friction[0], TORSION, o.friction[2]], condim=4)
            if o.base:                  # wide base under a narrow neck (a flask): most of the mass sits in the base
                br, bh = o.base
                b.add_geom(name=o.name + "_base", type=CYL, size=[br, bh / 2, 0], pos=[0, 0, bh / 2 - z0],
                           rgba=list(o.rgba), mass=o.mass * 0.8, friction=[o.friction[0], TORSION, o.friction[2]], condim=4)
            if o.com_z is not None:      # shift the inertial frame: heavy-bottom / off-centre objects
                g.mass = 0                # geometry carries no mass; set it through the body inertial
                b.mass = o.mass
                b.ipos = [0, 0, o.com_z - z0]
                if o.shape == "box":
                    a, bb, c = (2 * v for v in o.size)
                    b.inertia = [o.mass / 12 * (bb**2 + c**2), o.mass / 12 * (a**2 + c**2), o.mass / 12 * (a**2 + bb**2)]
                else:
                    r, h = o.size[0], 2 * o.size[1]
                    b.inertia = [o.mass * (3 * r * r + h * h) / 12] * 2 + [o.mass * r * r / 2]
                b.explicitinertial = True
        for g in spec.geoms:                       # object friction decides contact friction (MuJoCo takes the max)
            if g.parent.name in ("hand", "left_finger", "right_finger"):
                g.friction = [0.05, TORSION, 0.0001]
        for b in spec.bodies:                      # gravity-compensate the arm so position control is accurate
            if b.name.startswith(("link", "hand", "left_finger", "right_finger")):
                b.gravcomp = 1.0
        gk = GRIP_FORCE_SCALE                      # Menagerie's tendon gains give only ~2 N; scale to a plausible 10 N firm grip
        act = spec.actuator("actuator8")
        act.gainprm[0] *= gk
        act.biasprm[1] *= gk
        act.biasprm[2] *= gk
        self.model = spec.compile()
        self.data = mujoco.MjData(self.model)
        self.scratch = mujoco.MjData(self.model)
        m = self.model
        self.arm_qadr = np.array([m.jnt_qposadr[m.joint(n).id] for n in self.ARM])
        self.arm_dadr = np.array([m.jnt_dofadr[m.joint(n).id] for n in self.ARM])
        self.finger_qadr = np.array([m.jnt_qposadr[m.joint(n).id] for n in ("finger_joint1", "finger_joint2")])
        self.q_lo = m.jnt_range[[m.joint(n).id for n in self.ARM], 0].copy()
        self.q_hi = m.jnt_range[[m.joint(n).id for n in self.ARM], 1].copy()
        self.hand_id = m.body("hand").id
        self.obj_ids = {o.name: m.body(o.name).id for o in scene.objects}
        self.obj_geoms = {o.name: m.geom(o.name + "_g").id for o in scene.objects}
        # geoms of the robot (everything under link0), used for collision classification
        robot_root = m.body("link0").id
        self.robot_bodies = {b for b in range(m.nbody) if self._is_descendant(b, robot_root)}
        self.time = 0.0
        self.reset()

    def _is_descendant(self, b: int, root: int) -> bool:
        while b != 0:
            if b == root:
                return True
            b = self.model.body_parentid[b]
        return False

    # ---------------------------------------------------------------- state
    def reset(self):
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self.arm_qadr] = self.HOME_Q
        self.data.qpos[self.finger_qadr] = 0.04
        self.data.ctrl[:7] = self.HOME_Q
        self.data.ctrl[7] = self.GRIP_OPEN
        # re-seat free joints at their initial poses
        for o in self.scene.objects:
            adr = self.model.jnt_qposadr[self.model.joint(o.name + "_free").id]
            z0 = o.size[2] if o.shape == "box" else o.size[1]
            self.data.qpos[adr:adr + 3] = [o.pos[0], o.pos[1], z0 + 0.001]
            self.data.qpos[adr + 3:adr + 7] = [np.cos(o.yaw / 2), 0, 0, np.sin(o.yaw / 2)]
        mujoco.mj_forward(self.model, self.data)
        self.settle(0.6)
        self.time = 0.0

    @property
    def q(self) -> np.ndarray:
        return self.data.qpos[self.arm_qadr].copy()

    def gripper_width(self) -> float:
        return float(self.data.qpos[self.finger_qadr].sum())

    def tcp(self, data=None) -> np.ndarray:
        d = data or self.data
        R = d.xmat[self.hand_id].reshape(3, 3)
        return d.xpos[self.hand_id] + R @ self.TCP_OFFSET

    def hand_R(self, data=None) -> np.ndarray:
        return (data or self.data).xmat[self.hand_id].reshape(3, 3).copy()

    def obj_pos(self, name: str) -> np.ndarray:
        return self.data.xpos[self.obj_ids[name]].copy()

    def obj_quat(self, name: str) -> np.ndarray:
        return self.data.xquat[self.obj_ids[name]].copy()

    def obj_tilt_deg(self, name: str) -> float:
        R = self.data.xmat[self.obj_ids[name]].reshape(3, 3)
        return float(np.degrees(np.arccos(np.clip(R[2, 2], -1, 1))))

    # ---------------------------------------------------------------- stepping
    def step(self, n: int = 1):
        for _ in range(n):
            mujoco.mj_step(self.model, self.data)
        self.time += n * self.model.opt.timestep

    def settle(self, seconds: float):
        self.step(int(seconds / self.model.opt.timestep))

    def set_gripper(self, closed: bool):
        self.data.ctrl[7] = self.GRIP_CLOSED if closed else self.GRIP_OPEN

    # ---------------------------------------------------------------- contacts
    def _geom_body(self, g: int) -> int:
        return int(self.model.geom_bodyid[g])

    def robot_contacts(self, data=None, ignore: set[str] = frozenset()) -> list[str]:
        """Names of non-robot bodies the robot is touching (floor excluded, base excluded)."""
        d = data or self.data
        out = []
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = self._geom_body(c.geom1), self._geom_body(c.geom2)
            r1, r2 = b1 in self.robot_bodies, b2 in self.robot_bodies
            if r1 == r2:
                continue
            robot_b, other_b = (b1, b2) if r1 else (b2, b1)
            if other_b == 0:                      # floor
                if robot_b == self.model.body("link0").id:
                    continue
                out.append("floor")
                continue
            name = self.model.body(other_b).name
            if name not in ignore:
                out.append(name)
        return out

    def arm_in_collision(self, q: np.ndarray, ignore: set[str] = frozenset(), fingers_open: bool = True) -> list[str]:
        d = self.scratch
        d.qpos[:] = self.data.qpos
        d.qpos[self.arm_qadr] = q
        if fingers_open:
            d.qpos[self.finger_qadr] = 0.04
        mujoco.mj_forward(self.model, d)
        return self.robot_contacts(d, ignore)

    def finger_force_contacts(self, name: str) -> int:
        """Number of fingertip-pad contacts currently touching the named object."""
        gid = self.obj_geoms[name]
        n = 0
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            if gid in (c.geom1, c.geom2):
                other = c.geom2 if c.geom1 == gid else c.geom1
                if self._geom_body(other) in self.robot_bodies and self._geom_body(other) != self.model.body("link0").id:
                    n += 1
        return n
