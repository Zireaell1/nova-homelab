import re

from _common import GROUP_VARS, ROLES, load, read

TITLE = "Every quadlet Network= names a declared network, every network is used"

BUILTIN = {"pasta", "slirp4netns", "host", "none", "private", "bridge"}
NETWORK_LINE = re.compile(r"^\s*Network\s*=\s*([^\s:]+)", re.MULTILINE)


def check() -> list[str]:
    declared = {
        n["name"]
        for n in (load(GROUP_VARS / "all" / "podman.yml").get("podman_networks") or [])
    }
    used: set[str] = set()
    bad = []
    for f in sorted(ROLES.glob("*/templates/*.container.j2")):
        for ref in NETWORK_LINE.findall(read(f)):
            if ref in BUILTIN or ref.startswith("container:") or "{{" in ref:
                continue
            name = ref.removesuffix(".network")
            if not ref.endswith(".network"):
                bad.append(
                    f"{f}: Network={ref} is neither a built-in mode nor a .network quadlet"
                )
                continue
            used.add(name)
            if name not in declared:
                bad.append(f"{f}: Network={ref} is not in podman_networks")
    for name in sorted(declared - used):
        bad.append(f"podman_networks: '{name}' is declared but no quadlet joins it")
    return bad
