import re

from _common import ROLES, read

TITLE = "Quadlet [Service] restart/stop policy; every self-restarting unit backs off"

BACKOFF = ("RestartSteps", "RestartMaxDelaySec")


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
        bad += _backoff(name, svc)
        for key in ("StartLimitBurst", "StartLimitIntervalSec"):
            if re.search(rf"^{key}=", svc, re.MULTILINE):
                bad.append(f"{name}: {key} belongs in [Unit], not [Service]")
    units = [*ROLES.glob("*/templates/*.service.j2"), *ROLES.glob("*/files/*.service")]
    for f in sorted(units):
        bad += _backoff(f.name, read(f))
    return bad


def _backoff(name: str, svc: str) -> list[str]:
    """Restart= other than no needs RestartSteps= and RestartMaxDelaySec= (crash loops back off)."""
    if not re.search(r"^Restart=(?!no$)", svc, re.MULTILINE):
        return []
    return [
        f"{name}: Restart= without {key}= (backoff)"
        for key in BACKOFF
        if not re.search(rf"^{key}=", svc, re.MULTILINE)
    ]
