"""ZTE web API -> Prometheus textfile.

Usage: python3 -I modem_metrics.py <modem_host> <interval_seconds> <output.prom> <pause_file>
Password: $CREDENTIALS_DIRECTORY/password (systemd LoadCredential). Logs go to stderr.

The modem allows one web session and the newest login wins, so every poll logs out again
and a pause file (written by `modem-pause`) stops polling while someone uses the web panel.
After a rejected login it waits LOGIN_BACKOFF seconds before trying again (the modem locks
its login after a few wrong passwords).

Everything it touches:
  GET  http://<modem>/goform/goform_get_cmd_process   LD, RD, wa_inner_version, the FIELDS below
  POST http://<modem>/goform/goform_set_cmd_process   goformId=LOGIN, goformId=LOGOUT
  reads  $CREDENTIALS_DIRECTORY/password, <pause_file>
  writes <output.prom>.<pid>, renamed to <output.prom>
"""

import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HOST, INTERVAL, OUT, PAUSE_FILE = (
    sys.argv[1],
    int(sys.argv[2]),
    sys.argv[3],
    sys.argv[4],
)
LOGIN_BACKOFF = 900
TIMEOUT = 10

FIELDS = (
    "network_type,network_provider,signalbar,ppp_status,modem_main_state,wan_lte_ca,"
    "realtime_time,ppp_dial_conn_fail_counter,realtime_tx_thrpt,realtime_rx_thrpt,"
    "monthly_tx_bytes,monthly_rx_bytes,"
    "lte_rsrp,lte_rsrq,lte_snr,lte_rssi,wan_active_band,wan_active_channel,lte_pci,cell_id,"
    "Z5g_rsrp,Z5g_rsrq,Z5g_SINR,Z5g_snr,Z5g_rssi,nr5g_action_band,nr5g_action_channel,"
    "nr5g_pci,nr5g_cell_id,"
    "tx_power,wan_connect_status,"
    "lte_rsrp_1,lte_rsrp_2,lte_rsrp_3,lte_rsrp_4,lte_snr_1,lte_snr_2,lte_snr_3,lte_snr_4,"
    "5g_rx0_rsrp,5g_rx1_rsrp,"
    "pm_sensor_mdm,pm_sensor_ambient,pm_sensor_pa1,pm_sensor_5g,pm_modem_5g,"
    "lte_band_lock,lte_pci_lock,lte_earfcn_lock,nr5g_nsa_band_lock,nr5g_sa_band_lock"
)

if FIELDS.count(",") >= 60:
    raise SystemExit("FIELDS: keep a request below 60 fields")
# (metric, rat, field -> antenna label)
ANTENNA = (
    (
        "rsrp_dbm",
        "lte",
        {"lte_rsrp_1": "1", "lte_rsrp_2": "2", "lte_rsrp_3": "3", "lte_rsrp_4": "4"},
    ),
    (
        "sinr_db",
        "lte",
        {"lte_snr_1": "1", "lte_snr_2": "2", "lte_snr_3": "3", "lte_snr_4": "4"},
    ),
    ("rsrp_dbm", "nr", {"5g_rx0_rsrp": "0", "5g_rx1_rsrp": "1"}),
)
TEMPS = {
    "pm_sensor_mdm": "modem",
    "pm_sensor_ambient": "ambient",
    "pm_sensor_pa1": "power_amp",
    "pm_sensor_5g": "5g",
    "pm_modem_5g": "5g_modem",
}
LOCKS = (
    "lte_band_lock",
    "lte_pci_lock",
    "lte_earfcn_lock",
    "nr5g_nsa_band_lock",
    "nr5g_sa_band_lock",
)
# (metric, help, lte field, nr field)
SIGNAL = (
    ("rsrp_dbm", "Reference signal received power", "lte_rsrp", "Z5g_rsrp"),
    ("rsrq_db", "Reference signal received quality", "lte_rsrq", "Z5g_rsrq"),
    (
        "sinr_db",
        "Signal to interference plus noise ratio",
        "lte_snr",
        ("Z5g_SINR", "Z5g_snr"),
    ),
    ("rssi_dbm", "Received signal strength", "lte_rssi", "Z5g_rssi"),
)
# (rat, band, channel, pci, cell)
CELL = (
    ("lte", "wan_active_band", "wan_active_channel", "lte_pci", "cell_id"),
    ("nr", "nr5g_action_band", "nr5g_action_channel", "nr5g_pci", "nr5g_cell_id"),
)

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def log(level: str, msg: str) -> None:
    print(f"[{level}] {msg}", file=sys.stderr, flush=True)


def esc(v) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def num(v):
    try:
        return float(str(v).strip())
    except TypeError, ValueError:
        return None


def sha256u(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest().upper()


class Modem:
    def __init__(self, host: str) -> None:
        self.base = f"http://{host}/"
        self.stok = ""

    def _req(self, path: str, form: dict | None = None) -> tuple[dict, str]:
        headers = {"Referer": self.base, "X-Requested-With": "XMLHttpRequest"}
        if self.stok:
            headers["Cookie"] = f"stok={self.stok}"
        body = None
        if form is not None:
            body = urllib.parse.urlencode({"isTest": "false", **form}).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        req = urllib.request.Request(self.base + path, data=body, headers=headers)  # noqa: S310 - http://<modem ip> only
        with OPENER.open(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
            cookie = r.headers.get("Set-Cookie", "")
        return json.loads(raw), cookie

    def get(self, cmd: str) -> dict:
        multi = "&multi_data=1" if "," in cmd else ""
        return self._req(
            f"goform/goform_get_cmd_process?isTest=false&cmd={cmd}{multi}&_={int(time.time() * 1000)}"
        )[0]

    def login(self, password: str) -> bool:
        ld = str(self.get("LD").get("LD", "")).upper()
        if not ld:
            raise RuntimeError("no LD value from the modem")
        result, cookie = self._req(
            "goform/goform_set_cmd_process",
            {"goformId": "LOGIN", "password": sha256u(sha256u(password) + ld)},
        )
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name.lower().endswith("stok"):
                self.stok = value.strip('"')
        return str(result.get("result")) == "0" and bool(self.stok)

    def logout(self) -> bool:
        wa = str(self.get("wa_inner_version").get("wa_inner_version", ""))
        rd = str(self.get("RD").get("RD", ""))
        result, _ = self._req(
            "goform/goform_set_cmd_process",
            {"goformId": "LOGOUT", "AD": sha256u(sha256u(wa) + rd)},
        )
        self.stok = ""
        return str(result.get("result")) == "success"


class Prom:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.seen: set[str] = set()

    def add(self, name: str, help_: str, value, labels: dict | None = None) -> None:
        if value is None:
            return
        full = f"homelab_modem_{name}"
        if full not in self.seen:
            self.seen.add(full)
            self.lines += [f"# HELP {full} {help_}", f"# TYPE {full} gauge"]
        lab = ",".join(f'{k}="{esc(v)}"' for k, v in (labels or {}).items())
        self.lines.append(
            f"{full}{{{lab}}} {value:.15g}" if lab else f"{full} {value:.15g}"
        )

    def write(self) -> None:
        tmp = f"{OUT}.{os.getpid()}"
        with open(tmp, "w") as fh:
            fh.write("\n".join(self.lines) + "\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, OUT)


def paused_until() -> float:
    try:
        with open(PAUSE_FILE) as fh:
            until = float(fh.read().strip())
    except OSError, ValueError:
        return 0.0
    return until if until > time.time() else 0.0


def poll(password: str, p: Prom) -> bool:
    m = Modem(HOST)
    if not m.login(password):
        log("ERROR", "login rejected; backing off before the next attempt")
        p.add("login_ok", "Whether the last login was accepted", 0)
        return False
    p.add("login_ok", "Whether the last login was accepted", 1)
    try:
        try:
            d = m.get(FIELDS)
        except (OSError, ValueError) as e:
            log("WARN", f"read failed ({e}); retrying once")
            time.sleep(2)
            d = m.get(FIELDS)
    finally:
        try:
            if not m.logout():
                log("WARN", "logout not acknowledged; the session expires on its own")
        except Exception as e:  # noqa: BLE001 - the poll result matters more than the logout
            log("WARN", f"logout failed: {e}")

    p.add(
        "info",
        "Connection state as reported by the modem",
        1,
        {
            "network_type": d.get("network_type", ""),
            "provider": d.get("network_provider", ""),
            "ppp_status": d.get("ppp_status", ""),
            "state": d.get("modem_main_state", ""),
            "lte_ca": d.get("wan_lte_ca", ""),
            "wan": d.get("wan_connect_status", ""),
        },
    )
    p.add("signal_bars", "Signal bars shown in the web panel", num(d.get("signalbar")))
    for metric, help_, lte, nr in SIGNAL:
        p.add(metric, help_, num(d.get(lte)), {"rat": "lte"})
        for f in nr if isinstance(nr, tuple) else (nr,):
            if num(d.get(f)) is not None:
                p.add(metric, help_, num(d.get(f)), {"rat": "nr"})
                break
    for rat, band, chan, pci, cell in CELL:
        if d.get(band) or d.get(cell):
            p.add(
                "cell_info",
                "Serving cell; a change of labels is a handover",
                1,
                {
                    "rat": rat,
                    "band": d.get(band, ""),
                    "channel": d.get(chan, ""),
                    "pci": d.get(pci, ""),
                    "cell_id": d.get(cell, ""),
                },
            )
    for metric, rat, fields in ANTENNA:
        for f, antenna in fields.items():
            p.add(
                f"antenna_{metric}",
                "Per receive antenna; one far below the others points at that antenna or its cable",
                num(d.get(f)),
                {"rat": rat, "antenna": antenna},
            )
    p.add(
        "tx_power_dbm",
        "Uplink transmit power; near its maximum (23-26 dBm) means the cell barely hears the modem",
        num(d.get("tx_power")),
    )
    for f, sensor in TEMPS.items():
        p.add(
            "temperature_celsius",
            "Temperatures reported by the modem",
            num(d.get(f)),
            {"sensor": sensor},
        )
    locks = {f: d.get(f, "") for f in LOCKS}
    if any(locks.values()):
        p.add(
            "lock_info", "Band, cell or channel locks as set in the web panel", 1, locks
        )
    p.add(
        "session_uptime_seconds",
        "Seconds since the current mobile data session started",
        num(d.get("realtime_time")),
    )
    p.add(
        "dial_failures",
        "Failed reconnect attempts counted by the modem",
        num(d.get("ppp_dial_conn_fail_counter")),
    )
    for direction, f in (("tx", "realtime_tx_thrpt"), ("rx", "realtime_rx_thrpt")):
        p.add(
            "throughput",
            "Current throughput as reported by the modem (bytes per second)",
            num(d.get(f)),
            {"direction": direction},
        )
    for direction, f in (("tx", "monthly_tx_bytes"), ("rx", "monthly_rx_bytes")):
        p.add(
            "monthly_bytes",
            "Data used this month",
            num(d.get(f)),
            {"direction": direction},
        )
    return True


def main() -> None:
    cred = os.path.join(os.environ.get("CREDENTIALS_DIRECTORY", ""), "password")
    with open(cred) as fh:
        password = fh.read().strip()
    next_login = 0.0
    while True:
        started = time.time()
        p = Prom()
        until = paused_until()
        p.add(
            "paused",
            "Polling paused with modem-pause (the web panel is free)",
            1 if until else 0,
        )
        p.add(
            "paused_until_timestamp_seconds",
            "When the pause ends (0 = not paused)",
            until,
        )
        ok = False
        if not until and started < next_login:
            p.add("login_ok", "Whether the last login was accepted", 0)
        elif not until:
            # One bad poll must not kill the collector.
            try:
                ok = poll(password, p)
                if not ok:
                    next_login = started + LOGIN_BACKOFF
            except Exception as e:  # noqa: BLE001
                log("ERROR", f"poll failed: {e}")
        p.add(
            "login_backoff_until_timestamp_seconds",
            "No login attempts before this time after a rejected password (0 = none)",
            next_login if next_login > started else 0,
        )
        p.add(
            "up",
            "Whether the last poll read the modem (0 while paused)",
            1 if ok else 0,
        )
        p.add("last_poll_timestamp_seconds", "Unix time of the last loop", started)
        p.add(
            "poll_duration_seconds",
            "Seconds the last poll took",
            round(time.time() - started, 3),
        )
        p.write()
        # Sleep in short steps so a new pause takes effect within a second.
        while time.time() < started + INTERVAL:
            if not until and paused_until():
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
