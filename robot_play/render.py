"""Turn an episode into a captioned video. The simulator is stepped as usual; a recorder takes a picture every few milliseconds of
simulated time and a caption bar explains, in plain words, which tool call is running and what it returned."""
from __future__ import annotations

import subprocess
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Helvetica.ttc"
W, H, BAR = 960, 540, 150


def _font(size, bold=False):
    try:
        return ImageFont.truetype(FONT, size, index=1 if bold else 0)
    except OSError:
        return ImageFont.load_default()


def _wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def say(tool: str, args: dict, res: dict | None) -> tuple[str, str]:
    """(what the agent asked, what happened) in everyday words."""
    a = ", ".join(f"{k}={v}" for k, v in args.items())
    ask = f"{tool}({a})"
    if res is None:
        return ask, "running..."
    if "error" in res and not res.get("ok", False):
        what = {"pick": "The pick did not happen: ", "place": "The place did not happen: "}.get(tool, "Error: ")
        return ask, what + res["error"] + "."
    if tool == "pick":
        if res.get("ok"):
            return ask, f"Picked up {res['holding']}. It rose {res['object_rise_m'] * 100:.0f} cm and the fingers are {res['gripper_width_m'] * 100:.1f} cm apart."
        return ask, (f"The grab failed. The object rose {abs(max(res.get('object_rise_m', 0), 0)) * 100 + 0.0:.0f} cm and the fingers ended {res.get('gripper_width_m', 0) * 100:.1f} cm apart, "
                     "so nothing is held.")
    if tool == "place":
        p = res.get("object_position_m", [0, 0, 0])
        return ask, f"Released {res['released']}. It came to rest at x={p[0]:.2f}, y={p[1]:.2f}, height {p[2] * 100:.1f} cm, tilted {res.get('object_tilt_deg', 0):.0f} degrees."
    if tool == "observe":
        return ask, "Looked at the scene: positions of every object and zone."
    if tool == "done":
        return ask, "The agent says it is finished. The simulator now checks."
    return ask, "Done."


class Recorder:
    def __init__(self, env, path: str | Path, title: str, speed: float = 2.0, fps: int = 30, final_note: str = ""):
        self.env, self.path, self.title, self.fps = env, Path(path), title, fps
        self.dt = speed / fps                              # simulated seconds between frames
        self.renderer = mujoco.Renderer(env.w.model, height=H - BAR, width=W)
        self.cam = mujoco.MjvCamera()
        self.cam.lookat[:] = [0.48, 0.0, 0.06]
        self.cam.distance, self.cam.azimuth, self.cam.elevation = 0.92, 150, -34
        self.frames: list[np.ndarray] = []
        self.caption = ("", "")
        self._next = 0.0
        w = env.w
        self._orig_step = w.step
        w.step = self._step
        self.final_note = final_note

    def _step(self, n: int = 1):
        w = self.env.w
        for _ in range(n):
            self._orig_step(1)
            if w.time >= self._next:
                self._next += self.dt
                self._capture()

    def _capture(self):
        self.renderer.update_scene(self.env.w.data, self.cam)
        self.frames.append(self._compose(self.renderer.render()))

    def _compose(self, scene: np.ndarray, note: str | None = None) -> np.ndarray:
        img = Image.new("RGB", (W, H), (24, 26, 31))
        img.paste(Image.fromarray(scene), (0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 34], fill=(0, 0, 0))
        d.text((14, 6), self.title, font=_font(20, True), fill=(255, 255, 255))
        y = H - BAR + 12
        ask, what = self.caption
        d.text((16, y), ask, font=_font(21, True), fill=(120, 200, 255))
        for i, line in enumerate(_wrap(d, note or what, _font(22), W - 32)[:4]):
            d.text((16, y + 34 + i * 28), line, font=_font(22), fill=(240, 240, 240))
        return np.asarray(img)

    def hold(self, seconds: float):
        if not self.frames:
            self._capture()
        last = self.frames[-1]
        # re-compose the last scene with the (new) caption so the result text appears under a still picture
        self.renderer.update_scene(self.env.w.data, self.cam)
        shot = self._compose(self.renderer.render())
        self.frames.extend([shot] * int(seconds * self.fps))

    def set_caption(self, tool, args, res):
        self.caption = say(tool, args, res)

    def save(self, outcome: str | None = None):
        if outcome:
            self.caption = (self.caption[0], outcome)
            self.hold(3.0)
        self.env.w.step = self._orig_step
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(self.fps), "-i", "-",
               "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(self.path)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for f in self.frames:
            p.stdin.write(f.tobytes())
        p.stdin.close()
        p.wait()
        return self.path


def record_episode(episode, calls: list[tuple[str, dict]], path, title: str, speed: float = 2.0, outcome_prefix: str = ""):
    """Replay a list of tool calls on `episode` while recording a captioned video."""
    rec = Recorder(episode.env, path, title, speed=speed)
    for name, args in calls:
        rec.set_caption(name, args, None)
        res = episode.call(name, args)
        rec.set_caption(name, args, res)
        rec.hold(2.2)
    r = episode.result()
    ok = "SUCCESS" if r["success"] else "FAILED"
    rec.save(f"{outcome_prefix}Simulator verdict: {ok}. Tool calls used: {r['calls']} of {episode.max_calls}.")
    return r
