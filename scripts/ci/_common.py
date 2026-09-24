from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLES = Path("ansible/roles")
GROUP_VARS = Path("ansible/group_vars")
HOST_VARS = Path("ansible/host_vars")


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def inventory_vars_files() -> list[Path]:
    return sorted(GROUP_VARS.rglob("*.yml")) + sorted(HOST_VARS.glob("*.yml"))


def walk(tasks: Any) -> Iterator[dict]:
    for t in tasks or []:
        if not isinstance(t, dict):
            continue
        yield t
        for key in ("block", "rescue", "always"):
            yield from walk(t.get(key))


def as_list(value: Any) -> list:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)
