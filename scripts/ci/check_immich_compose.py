import re
import sys
import urllib.error
import urllib.request

from _common import ROLES, load

TITLE = "Immich's Postgres and Valkey pins match the compose file of the pinned Immich release"

COMPOSE = "https://raw.githubusercontent.com/immich-app/immich/{version}/docker/docker-compose.yml"
PINS = {
    "immich_postgres_version": r"image:\s*ghcr\.io/immich-app/postgres:(\S+)",
    "immich_redis_version": r"image:\s*docker\.io/valkey/valkey:(\S+)",
}


def check() -> list[str]:
    defaults = load(ROLES / "immich" / "defaults" / "main.yml")
    version = defaults["immich_version"]
    try:
        with urllib.request.urlopen(COMPOSE.format(version=version), timeout=20) as r:
            compose = r.read().decode()
    except (urllib.error.URLError, TimeoutError) as e:
        print(
            f"       (skipped: cannot fetch Immich {version} compose: {e})",
            file=sys.stderr,
        )
        return []
    bad = []
    for key, pattern in PINS.items():
        m = re.search(pattern, compose)
        if not m:
            bad.append(f"Immich {version} compose: no image line matching {pattern}")
        elif defaults[key] != m.group(1):
            bad.append(
                f"immich defaults: {key} is {defaults[key]!r}, Immich {version} ships {m.group(1)!r}"
            )
    return bad
