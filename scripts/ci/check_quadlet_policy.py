import re

from _common import ROLES, read

TITLE = "Quadlet [Service] restart/stop policy"


def check() -> list[str]:
    bad = []
    for f in sorted(ROLES.glob("*/templates/*.container.j2")):
        name, body = f.name, read(f)
        m = re.search(r"^\[Service\](.*?)(?=^\[|\Z)", body, re.MULTILINE | re.DOTALL)
        if not m:
            continue
        svc = m.group(1)
        if re.search(r"^Restart=", svc, re.MULTILINE) and not re.search(
            r"^RestartSec=", svc, re.MULTILINE
        ):
            bad.append(f"{name}: Restart= without RestartSec=")
        stop = re.search(r"^StopTimeout=(\d+)", body, re.MULTILINE)
        tstop = re.search(r"^TimeoutStopSec=(\d+)", svc, re.MULTILINE)
        if stop and tstop and int(tstop.group(1)) != int(stop.group(1)) + 10:
            want = int(stop.group(1)) + 10
            bad.append(
                f"{name}: TimeoutStopSec={tstop.group(1)} should be {want} (StopTimeout + 10)"
            )
        if stop and not tstop:
            bad.append(f"{name}: StopTimeout= without TimeoutStopSec=")
        for key in ("StartLimitBurst", "StartLimitIntervalSec"):
            if re.search(rf"^{key}=", svc, re.MULTILINE):
                bad.append(f"{name}: {key} belongs in [Unit], not [Service]")
    return bad
