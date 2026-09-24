from _common import ROLES, as_list, load, walk

TITLE = "Every notify: target has a handler"


def check() -> list[str]:
    bad = []
    for role in sorted(p for p in ROLES.iterdir() if p.is_dir()):
        defined: set[str] = set()
        for hf in role.glob("handlers/*.yml"):
            for h in walk(load(hf)):
                if h.get("name"):
                    defined.add(h["name"])
                defined |= set(as_list(h.get("listen")))
        for tf in role.glob("tasks/*.yml"):
            for t in walk(load(tf)):
                for target in as_list(t.get("notify")):
                    if target not in defined:
                        bad.append(f"{role.name}: notify '{target}' has no handler")
    return bad
