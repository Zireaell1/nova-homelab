import posixpath

from _common import ROLES, load, walk

TITLE = "podman_service destinations have a created parent directory"


def check() -> list[str]:
    bad = []
    for f in sorted(ROLES.glob("*/tasks/main.yml")):
        role, tasks = f.parts[2], list(walk(load(f)))
        pre: set[str] = set()
        for t in tasks:
            mod = t.get("ansible.builtin.file")
            if isinstance(mod, dict) and mod.get("state") == "directory":
                lp = t.get("loop") or []
                if isinstance(lp, list):
                    pre |= {str(x) for x in lp}
        for t in tasks:
            if "ansible.builtin.include_role" not in t:
                continue
            v = t.get("vars") or {}
            dirs = set(v.get("podman_service_dirs") or []) | pre
            entries = (v.get("podman_service_templates") or []) + (
                v.get("podman_service_secrets") or []
            )
            for e in entries:
                parent = posixpath.dirname(str(e.get("dest")))
                if parent not in dirs:
                    bad.append(f"{role}: {e.get('dest')} (parent {parent} not created)")
    return bad
