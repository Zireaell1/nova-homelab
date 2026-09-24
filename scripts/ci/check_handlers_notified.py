from _common import ROLES, as_list, load, walk

TITLE = "Every handler is notified somewhere"


def check() -> list[str]:
    bad = []
    for hf in sorted(ROLES.glob("*/handlers/main.yml")):
        role = hf.parts[2]
        notified: set[str] = set()
        for sf in [*sorted(ROLES.glob(f"{role}/tasks/*.yml")), hf]:
            for t in walk(load(sf)):
                notified |= set(as_list(t.get("notify")))
        for h in walk(load(hf)):
            name = h.get("name")
            listens = set(as_list(h.get("listen")))
            if name and name not in notified and not listens & notified:
                bad.append(f"{role}: {name}")
    return bad
