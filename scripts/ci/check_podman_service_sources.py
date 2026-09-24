from _common import ROLES, load, walk

TITLE = "podman_service template sources exist"


def check() -> list[str]:
    bad = []
    for f in sorted(ROLES.glob("*/tasks/main.yml")):
        role = f.parts[2]
        for t in walk(load(f)):
            if "ansible.builtin.include_role" not in t:
                continue
            v = t.get("vars") or {}
            srcs = [
                e["src"]
                for e in (v.get("podman_service_templates") or [])
                if isinstance(e, dict) and "src" in e
            ]
            srcs += [n + ".j2" for n in (v.get("podman_service_quadlets") or [])]
            srcs += [n + ".j2" for n in (v.get("podman_service_units") or [])]
            for s in srcs:
                if "{{" in s:
                    continue
                p = ROLES / role / "templates" / s
                if not p.exists():
                    bad.append(f"{role}: {s} -> {p}")
    return bad
