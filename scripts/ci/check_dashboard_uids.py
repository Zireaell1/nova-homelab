import json
import re
from pathlib import Path

TITLE = "Grafana dashboards keep a stable uid (metadata.name == file name)"

DASHBOARDS = Path("ansible/roles/grafana/files/dashboards")
UID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def check() -> list[str]:
    problems = []
    seen: dict[str, str] = {}
    for f in sorted(DASHBOARDS.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f"{f}: invalid JSON ({e})")
            continue
        if not str(d.get("apiVersion", "")).startswith("dashboard.grafana.app/v2"):
            problems.append(
                f"{f}: not a v2 dashboard (apiVersion {d.get('apiVersion')!r})"
            )
            continue
        uid = (d.get("metadata") or {}).get("name")
        if not uid:
            problems.append(
                f"{f}: metadata.name is missing; it was probably exported with "
                f"'Export for sharing externally'. Set it back to {f.stem!r}"
            )
            continue
        if uid != f.stem:
            problems.append(f"{f}: metadata.name is {uid!r}, expected {f.stem!r}")
        if not UID.match(uid):
            problems.append(f"{f}: {uid!r} is not a valid uid (a-z, 0-9, '-', max 40)")
        if uid in seen:
            problems.append(f"{f}: uid {uid!r} already used by {seen[uid]}")
        seen[uid] = f.name
    return problems
