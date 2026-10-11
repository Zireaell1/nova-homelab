"""intel_gpu_top -J -> Prometheus textfile. One long-running intel_gpu_top, one .prom per sample.

Usage: python3 -I intel_gpu_metrics.py <interval_seconds> <output.prom>
Exits when intel_gpu_top exits; systemd restarts it. Logs go to stderr (the journal).

Everything it touches:
  runs    intel_gpu_top -J -s <interval_ms> -o -   (the only external command; igt-gpu-tools)
  reads   /proc/<pid>/cgroup                       (one per GPU client, to name its systemd unit)
  writes  <output.prom>.<pid>, renamed to <output.prom>
"""

import json
import os
import re
import subprocess
import sys
import time

INTERVAL = int(sys.argv[1])
OUT = sys.argv[2]


def log(level: str, msg: str) -> None:
    print(f"[{level}] {msg}", file=sys.stderr, flush=True)


def esc(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def engine_name(key: str) -> str:
    # "Render/3D", "Render/3D/0", "Video/1", "VideoEnhance", "Blitter", "Compute/0"
    base = re.sub(r"/\d+$", "", key)
    return {"Render/3D": "render"}.get(base, base.lower())


def unit_of(pid) -> str:
    """systemd unit a process runs in: a quadlet container shows up as e.g. "frigate"."""
    try:
        with open(f"/proc/{int(pid)}/cgroup") as fh:
            path = fh.read()
    except OSError, ValueError:
        return "unknown"
    units = [
        u
        for u in re.findall(r"/([\w.@-]+)\.service", path)
        if not u.startswith("user@")
    ]
    return units[-1] if units else "host"


def num(x):
    try:
        return float(x)
    except TypeError, ValueError:
        return None


class Prom:
    def __init__(self) -> None:
        self.out: list[str] = []

    def metric(self, name, help_, typ, rows) -> None:
        rows = [(lbl, v) for lbl, v in rows if v is not None]
        if not rows:
            return
        self.out.append(f"# HELP {name} {help_}")
        self.out.append(f"# TYPE {name} {typ}")
        for labels, v in rows:
            lbl = ",".join(f'{k}="{esc(val)}"' for k, val in labels.items())
            v = round(v, 3) if isinstance(v, float) else v
            self.out.append(f"{name}{{{lbl}}} {v}" if lbl else f"{name} {v}")

    def footer(self, success: int) -> str:
        self.metric(
            "intel_gpu_collector_success",
            "Whether the last sample was collected without error (1) or not (0)",
            "gauge",
            [({}, success)],
        )
        self.metric(
            "intel_gpu_collector_last_sample_timestamp_seconds",
            "When this file was written",
            "gauge",
            [({}, int(time.time()))],
        )
        return "\n".join(self.out) + "\n"


def render(s: dict) -> str:
    p = Prom()

    f = s.get("frequency", {})
    p.metric(
        "intel_gpu_frequency_mhz",
        "GPU frequency",
        "gauge",
        [
            ({"type": "requested"}, num(f.get("requested"))),
            ({"type": "actual"}, num(f.get("actual"))),
        ],
    )
    p.metric(
        "intel_gpu_rc6_percent",
        "Time the GPU spent in RC6 (idle power state)",
        "gauge",
        [({}, num(s.get("rc6", {}).get("value")))],
    )
    p.metric(
        "intel_gpu_power_watts",
        "Power draw (RAPL)",
        "gauge",
        [
            ({"domain": k.lower()}, num(v))
            for k, v in s.get("power", {}).items()
            if k != "unit"
        ],
    )
    p.metric(
        "intel_gpu_imc_bandwidth_mib_per_second",
        "Memory controller bandwidth",
        "gauge",
        [
            ({"direction": k}, num(v))
            for k, v in s.get("imc-bandwidth", {}).items()
            if k != "unit"
        ],
    )

    busy: dict[str, float] = {}
    for key, e in s.get("engines", {}).items():
        v = num(e.get("busy"))
        if v is not None:
            busy[engine_name(key)] = v
    p.metric(
        "intel_gpu_engine_busy_percent",
        "Engine class busy, averaged over the class's engines (intel_gpu_top class view)",
        "gauge",
        [({"engine": k}, v) for k, v in sorted(busy.items())],
    )

    # Per-process usage and GPU memory, summed by systemd unit (= container) and process name.
    clients: dict[tuple, float] = {}
    mem: dict[tuple, float] = {}
    for c in s.get("clients", {}).values():
        unit = unit_of(c.get("pid"))
        name = c.get("name", "unknown")
        for cls, e in c.get("engine-classes", {}).items():
            v = num(e.get("busy"))
            if v is not None:
                k = (unit, name, engine_name(cls))
                clients[k] = clients.get(k, 0.0) + v
        # On an iGPU the only region is "system", i.e. ordinary RAM.
        for region, m in c.get("memory", {}).items():
            for kind in ("total", "resident"):
                v = num(m.get(kind))
                if v is not None:
                    k = (unit, name, region, kind)
                    mem[k] = mem.get(k, 0.0) + v
    p.metric(
        "intel_gpu_client_busy_percent",
        "Engine class busy per systemd unit (container) and process name; "
        "summed over the class's engines, so it can exceed the class value",
        "gauge",
        [
            ({"unit": u, "client": n, "engine": e}, v)
            for (u, n, e), v in sorted(clients.items())
        ],
    )
    p.metric(
        "intel_gpu_client_memory_bytes",
        "GPU buffer memory per systemd unit (container) and process name",
        "gauge",
        [
            ({"unit": u, "client": n, "region": r, "type": t}, v)
            for (u, n, r, t), v in sorted(mem.items())
        ],
    )
    return p.footer(success=1)


def write(text: str) -> None:
    tmp = f"{OUT}.{os.getpid()}"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, OUT)


def fail(msg: str) -> int:
    """Log, and replace the file with success=0 so the alert fires instead of serving stale numbers."""
    log("ERROR", msg)
    try:
        write(Prom().footer(success=0))
    except OSError as e:
        log("ERROR", f"cannot write {OUT}: {e}")
    return 1


def main() -> int:
    cmd = ["intel_gpu_top", "-J", "-s", str(INTERVAL * 1000), "-o", "-"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, bufsize=1)
    except OSError as e:
        return fail(f"cannot start intel_gpu_top: {e}")
    if proc.stdout is None:
        return fail("intel_gpu_top has no stdout")
    log(
        "INFO",
        f"started intel_gpu_top (pid {proc.pid}), sample every {INTERVAL}s -> {OUT}",
    )

    # The stream is "[\n{...},\n{...}" and never closes: decode each top-level object once it completes.
    dec = json.JSONDecoder()
    buf = ""
    samples = good = 0
    for line in proc.stdout:
        buf += line
        start = buf.find("{")
        if start < 0:
            buf = ""
            continue
        try:
            obj, end = dec.raw_decode(buf, start)
        except json.JSONDecodeError:
            continue  # object not complete yet
        buf = buf[end:]
        samples += 1
        try:
            write(render(obj))
        except (AttributeError, TypeError, ValueError, OSError) as e:
            # odd JSON shape (AttributeError/TypeError/ValueError) or a failed write (OSError):
            # log it and keep sampling
            fail(f"sample {samples}: {type(e).__name__}: {e}")
            continue
        good += 1
        if good == 1:
            log("INFO", f"first sample written to {OUT}")

    rc = proc.wait()
    return fail(
        f"intel_gpu_top exited with code {rc} after {samples} samples; its own error is just above"
    )


if __name__ == "__main__":
    sys.exit(main())
