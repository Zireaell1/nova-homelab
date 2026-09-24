from pathlib import Path

from _common import ROLES, load

TITLE = "backup_targets with stop: true resolve to a quadlet"


def check() -> list[str]:
    quadlets = {
        f.name.removesuffix(".j2") for f in ROLES.glob("*/templates/*.container.j2")
    }
    targets = load(Path("ansible/group_vars/all/backup.yml"))["backup_targets"]
    return [
        f"{t['name']}: stop: true but no {t['name']}.container quadlet exists"
        for t in targets
        if t.get("stop") and f"{t['name']}.container" not in quadlets
    ]
