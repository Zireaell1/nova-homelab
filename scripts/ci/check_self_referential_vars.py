import re

from _common import inventory_vars_files, load

TITLE = "No variable references itself"


def check() -> list[str]:
    bad = []
    for f in inventory_vars_files():
        for k, v in (load(f) or {}).items():
            if isinstance(v, str) and k in re.findall(r"\{\{\s*([a-z_0-9]+)", v):
                bad.append(f"{f}: {k}: {v}")
    return bad
