from _common import ROLES, inventory_vars_files, load, walk

TITLE = "No register: name shadows a defined variable"


def check() -> list[str]:
    defined: dict[str, list[str]] = {}
    for f in [*sorted(ROLES.glob("*/defaults/*.yml")), *inventory_vars_files()]:
        d = load(f)
        if isinstance(d, dict):
            for k in d:
                defined.setdefault(k, []).append(str(f))
    bad = []
    for f in sorted(ROLES.glob("*/tasks/*.yml")):
        for t in walk(load(f)):
            reg = t.get("register")
            if reg in defined:
                bad.append(f"{f}: register: {reg} shadows {defined[reg]}")
    return bad
