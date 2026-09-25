import re
from pathlib import Path

from _common import load, read

TITLE = "Every service_endpoints reference exists in the registry"

REGISTRY = Path("ansible/group_vars/all/endpoints.yml")
REF = re.compile(r"service_endpoints\[['\"]([a-z0-9_]+)['\"]\]")


def check() -> list[str]:
    known = set(load(REGISTRY)["service_endpoints"])
    bad = []
    for f in sorted(Path("ansible").rglob("*")):
        if not f.is_file() or f.suffix not in {".j2", ".yml", ".yaml"}:
            continue
        for n, line in enumerate(read(f).splitlines(), 1):
            for key in REF.findall(line):
                if key not in known:
                    bad.append(
                        f"{f}:{n}: service_endpoints['{key}'] is not in {REGISTRY}"
                    )
    return bad
