"""Descriptive audit of the final own notebooks of the two-sided job (PROTOCOL.md v1.15 and v1.16). Not registered; the keyword counts are a sentence search and the reading of the hits is mine.

  python scripts/notebook_audit_mixed.py > results/notebook_audit_mixed.md
Run from the repository root (or from the unpacked archive folder); reads runs/mixed and runs/mixed_silent."""
import glob
import json
import re
from pathlib import Path


def final_notebook(path):
    lines = [json.loads(x) for x in Path(path).read_text().splitlines()[1:]]
    prac = [r for r in lines if r["phase"] == "practice"]
    nb = (prac[-1].get("memory") if prac else "") or ""
    if isinstance(nb, dict):
        nb = nb.get("notebook", "")
    elif isinstance(nb, str) and nb.startswith("{"):
        nb = json.loads(nb).get("notebook", "")
    return nb, sum(r["result"]["success"] for r in prac), len(prac)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.;])\s+|\n", text) if s.strip()]


def main():
    print("# Final own notebooks (12 practice episodes) of the two-sided job: a descriptive sentence search\n")
    print("Not registered. Counts come from regular expressions over the last notebook of each run; the reading of the sentences is mine, not a blind coding. `link` = the notebook has a sentence that mentions both damage (crack, damage, fragile, break) and the grip (the whole word firm, grip, squeeze, force; `confirmed` does not count).\n")
    print("| job | model | notebooks | mention `firm` | mention a crack | have a damage-and-grip sentence | practice episodes solved |")
    print("|---|---|---|---|---|---|---|")
    detail = []
    for folder, job in (("runs/mixed", "with error message"), ("runs/mixed_silent", "no error message")):
        for tag, name in (("claude-haiku-5-5", "Haiku"), ("gpt-6-luna", "Luna")):
            files = sorted(glob.glob(f"{folder}/{tag}__*__notebook__quirk__p12__*.jsonl"))
            n = fm = ck = lk = ps = pn = 0
            for f in files:
                nb, s, p = final_notebook(f)
                t = nb.lower()
                n += 1
                fm += bool(re.search(r"\bfirm\b", t))
                ck += bool(re.search(r"crack|damag", t))
                hit = [x for x in sentences(nb) if re.search(r"crack|damag|fragile|break|squeeze limit", x, re.I) and re.search(r"\bfirm\b|\bgrip|squeez|\bforce\b", x, re.I)]
                lk += bool(hit)
                ps += s
                pn += p
                detail.append((job, name, Path(f).stem.split("__")[-1], hit))
            print(f"| {job} | {name} | {n} | {fm} | {ck} | {lk} | {ps} of {pn} |")
    print("\n## The damage-and-grip sentences of the job with no error message (read these, not the counts)\n")
    for job, name, seed, hit in detail:
        if job == "no error message" and hit:
            for x in hit:
                print(f"- {name} {seed}: {x[:260]}")


if __name__ == "__main__":
    main()
