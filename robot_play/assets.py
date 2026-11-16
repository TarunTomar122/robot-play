"""Locates (and fetches on first use) the MuJoCo Menagerie robot models."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MENAGERIE = ROOT / "third_party" / "mujoco_menagerie"


def model_dir(name: str) -> Path:
    d = MENAGERIE / name
    if not d.exists():
        subprocess.run([str(ROOT / "scripts" / "fetch_models.sh")], check=True)
    return d
