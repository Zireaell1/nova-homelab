import re

from _common import HOST_VARS, ROLES, inventory_vars_files, load, read

TITLE = "Role constants (vars/main.yml) are set nowhere else; every host_vars key is tagged [install], [hw] or [site]"

TAGS = ("[install]", "[hw]", "[site]")
KEY = re.compile(r"^([a-z_][a-z0-9_]*):")


def check() -> list[str]:
    elsewhere: dict[str, list[str]] = {}
    for f in [*sorted(ROLES.glob("*/defaults/*.yml")), *inventory_vars_files()]:
        data = load(f)
        if isinstance(data, dict):
            for k in data:
                elsewhere.setdefault(k, []).append(str(f))
    bad = []
    for f in sorted(ROLES.glob("*/vars/main.yml")):
        for k in load(f) or {}:
            if k in elsewhere:
                bad.append(
                    f"{f}: {k} is a constant but also set in {', '.join(elsewhere[k])}"
                    " (vars/ outranks it: that value is silently ignored)"
                )
    for f in sorted(HOST_VARS.glob("*.yml")):
        for n, line in enumerate(read(f).splitlines(), 1):
            m = KEY.match(line)
            if m and not any(t in line for t in TAGS):
                bad.append(f"{f}:{n}: {m.group(1)} has no {'/'.join(TAGS)} tag")
    return bad
