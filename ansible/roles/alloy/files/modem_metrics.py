"""ZTE web API -> Prometheus textfile.

Usage: python3 -I modem_metrics.py <modem_host> <interval_seconds> <output.prom> <pause_file>
Password: $CREDENTIALS_DIRECTORY/password (systemd LoadCredential). Logs go to stderr.

The modem allows one web session and the newest login wins, so every poll logs out again
and a pause file (written by `modem-pause`) stops polling while someone uses the web panel.
After a rejected login it waits LOGIN_BACKOFF seconds before trying again (the modem locks
its login after a few wrong passwords).

Everything it touches:
  GET  http://<modem>/goform/goform_get_cmd_process   LD, RD, wa_inner_version, the FIELDS below (in chunks)
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
# After the first report, field-check changes go to the journal at most this often.
FIELD_REPORT_INTERVAL = 3600

FIELDS = (
    "network_type",
    "network_provider",
    "signalbar",
    "ppp_status",
    "modem_main_state",
    "wan_lte_ca",
    "realtime_time",
    "ppp_dial_conn_fail_counter",
    "realtime_tx_thrpt",
    "realtime_rx_thrpt",
    "realtime_tx_bytes",
    "realtime_rx_bytes",
    "monthly_tx_bytes",
    "monthly_rx_bytes",
    "lte_rsrp",
    "lte_rsrq",
    "lte_snr",
    "lte_rssi",
    "wan_active_band",
    "wan_active_channel",
    "lte_pci",
    "cell_id",
    "Z5g_rsrp",
    "Z5g_rsrq",
    "Z5g_SINR",
    "Z5g_snr",
    "Z5g_rssi",
    "nr5g_action_band",
    "nr5g_action_channel",
    "nr5g_pci",
    "nr5g_cell_id",
    "nr5g_nsa_bandwidth",
    "tx_power",
    "wan_connect_status",
    "lte_rsrp_1",
    "lte_rsrp_2",
    "lte_rsrp_3",
    "lte_rsrp_4",
    "lte_snr_1",
    "lte_snr_2",
    "lte_snr_3",
    "lte_snr_4",
    "5g_rx0_rsrp",
    "5g_rx1_rsrp",
    "lte_band_lock",
    "lte_pci_lock",
    "lte_earfcn_lock",
    "lte_freq_lock",
    "nr5g_nsa_band_lock",
    "nr5g_sa_band_lock",
    "nr5g_cell_lock",
    "bandwidth",
    "lte_ca_pcell_band",
    "lte_ca_pcell_bandwidth",
    "lte_ca_pcell_arfcn",
    "lte_multi_ca_scell_info",
    "lte_multi_ca_scell_sig_info",
    "nr_multi_ca_scell_info",
    "ngbr_cell_info",
    "net_select",
    "net_select_mode",
    "mdm_mcc",
    "mdm_mnc",
    "simcard_roam",
    "wa_inner_version",
    "new_version_state",
    "current_upgrade_state",
    "sms_unread_num",
)
# Marks every field of a request the modem refused; the field report names them.
REFUSED = object()
# The modem drops long field lists; other tools split at 60, this stays well below.
CHUNK = 40
# Identity, location and secrets the web panel also serves. Never read them.
NEVER = ("imei", "imsi", "msisdn", "iccid", "gps_", "mac", "wan_ipaddr", "ssid")
NEVER += ("password", "passwd", "ppp_username", "apn_config", "mec_", "pin_")
if bad := [f for f in FIELDS if any(n in f.lower() for n in NEVER)]:
    raise SystemExit(f"FIELDS must not contain {bad}")
if len(set(FIELDS)) != len(FIELDS):
    raise SystemExit("FIELDS has duplicates")
# lte_rsrp_1..4 / lte_snr_1..4: on other ZTE models (MC7010) a rolling history of the last
# four lte_rsrp / lte_snr readings, not four antennas. 5g_rx0/1_rsrp are real receive paths.
ANTENNA_HELP = {
    "lte": "lte_rsrp_1..4 / lte_snr_1..4 as reported (on some ZTE models the last four readings, not antennas)",
    "nr": "Per 5G receive path",
}
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
# Allowed bands: LTE as a hex bitmask (bit 0 = band 1), 5G as a comma-separated list.
# With no band lock the modem lists every band it supports.
BAND_MASKS = {"lte_band_lock": "lte"}
BAND_LISTS = {"nr5g_nsa_band_lock": "nr_nsa", "nr5g_sa_band_lock": "nr_sa"}
CELL_LOCK = {"lte_pci_lock": "pci", "lte_earfcn_lock": "earfcn"}
# LTE downlink EARFCN ranges -> band (3GPP TS 36.101), for readable neighbour labels.
EARFCN_BANDS = (
    (0, 599, 1),
    (1200, 1949, 3),
    (2750, 3449, 7),
    (3450, 3799, 8),
    (6150, 6449, 20),
    (9210, 9659, 28),
    (9920, 10359, 32),
    (37750, 38249, 38),
    (38650, 39649, 40),
    (39650, 41589, 41),
)
# Channel widths in MHz; "20", "20.0" and "20MHz" are all accepted.
WIDTHS = {"bandwidth", "lte_ca_pcell_bandwidth", "nr5g_nsa_bandwidth"}
# ';'-separated groups of ','-separated values, checked by their parsers below.
STRUCTURED = {
    "ngbr_cell_info",
    "lte_multi_ca_scell_info",
    "lte_multi_ca_scell_sig_info",
}
# Formats not known yet: logged raw with the first field report (when not empty), not exported.
RAW = ("lte_freq_lock", "nr5g_cell_lock", "nr_multi_ca_scell_info")
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
SCELL_SIGNAL = (
    ("scell_rsrp_dbm", "Secondary carrier: reference signal received power"),
    ("scell_rsrq_db", "Secondary carrier: reference signal received quality"),
    ("scell_sinr_db", "Secondary carrier: signal to interference plus noise ratio"),
    ("scell_rssi_dbm", "Secondary carrier: received signal strength"),
)
# (rat, band, channel, pci, cell)
CELL = (
    ("lte", "wan_active_band", "wan_active_channel", "lte_pci", "cell_id"),
    ("nr", "nr5g_action_band", "nr5g_action_channel", "nr5g_pci", "nr5g_cell_id"),
)

# Fields that must parse as numbers; the rest are labels and only need to be present.
NUMERIC = {
    "signalbar",
    "realtime_time",
    "ppp_dial_conn_fail_counter",
    "realtime_tx_thrpt",
    "realtime_rx_thrpt",
    "monthly_tx_bytes",
    "monthly_rx_bytes",
    "tx_power",
    "realtime_tx_bytes",
    "realtime_rx_bytes",
    "sms_unread_num",
    "lte_ca_pcell_arfcn",
    *(s[2] for s in SIGNAL),
    *(f for s in SIGNAL for f in (s[3] if isinstance(s[3], tuple) else (s[3],))),
    *(f for _, _, fields in ANTENNA for f in fields),
}

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


def mhz(v):
    """'20', '20.0' or '20MHz' -> 20.0; None otherwise."""
    return num(str(v).strip().lower().removesuffix("mhz"))


def earfcn_band(v) -> str:
    n = num(v)
    for lo, hi, band in EARFCN_BANDS:
        if n is not None and lo <= n <= hi:
            return str(band)
    return ""


def lte_cell(v) -> dict[str, str]:
    """LTE cell id (ECI, 28-bit hex) -> base station (eNodeB) and its cell number."""
    try:
        eci = int(str(v).strip(), 16)
    except ValueError:
        return {}
    if not 0 < eci < 1 << 28:
        return {}
    return {"enb": str(eci >> 8), "sector": str(eci & 0xFF)}


def groups(v, width: int) -> list[list[str]] | None:
    """'a,b,c;d,e,f;' -> [[a,b,c],[d,e,f]]; None if a group has fewer than width values."""
    out = [[x.strip() for x in g.split(",")] for g in str(v).split(";") if g.strip()]
    return None if any(len(g) < width for g in out) else out


def parse_scells(v) -> list[dict] | None:
    """lte_multi_ca_scell_info: index,pci,state,band,earfcn,width per secondary cell."""
    gs = groups(v, 6)
    if (
        gs is None
        or any(num(x) is None for g in gs for x in g[:5])
        or any(mhz(g[5]) is None for g in gs)
    ):
        return None
    return [
        {
            "index": g[0],
            "pci": g[1],
            "state": g[2],
            "band": g[3],
            "earfcn": g[4],
            "width": mhz(g[5]),
        }
        for g in gs
    ]


def parse_scell_signal(v) -> list[list[float]] | None:
    """lte_multi_ca_scell_sig_info: rsrp,rsrq,sinr,rssi[,?,?] per secondary cell."""
    gs = groups(v, 4)
    if gs is None or any(num(x) is None for g in gs for x in g[:4]):
        return None
    return [[float(x) for x in g[:4]] for g in gs]


def parse_cells(v) -> list[dict] | None:
    """ngbr_cell_info: earfcn,pci,rsrq,rsrp[,rssi] per measured cell (serving ones included)."""
    gs = groups(v, 4)
    if gs is None or any(num(x) is None for g in gs for x in g[:4]):
        return None
    return [
        {
            "earfcn": g[0],
            "pci": g[1],
            "rsrq": num(g[2]),
            "rsrp": num(g[3]),
            "rssi": num(g[4]) if len(g) > 4 else None,
        }
        for g in gs
    ]


PARSERS = {
    "ngbr_cell_info": parse_cells,
    "lte_multi_ca_scell_info": parse_scells,
    "lte_multi_ca_scell_sig_info": parse_scell_signal,
}


def mask_bands(v) -> str | None:
    """'0x...' (or bare hex) bitmask -> '1,3,7,20'; None if it isn't hex."""
    try:
        m = int(str(v).strip(), 16)
    except ValueError:
        return None
    return ",".join(str(i + 1) for i in range(m.bit_length()) if m >> i & 1)


def list_bands(v) -> str | None:
    """'78,1,3' -> '1,3,78'; None if any item isn't a number."""
    items = [x.strip() for x in str(v).split(",") if x.strip()]
    if not all(x.isdigit() for x in items):
        return None
    return ",".join(str(b) for b in sorted({int(x) for x in items}))


KINDS = {
    "missing": ("WARN", "not in the reply at all"),
    "empty": (
        "INFO",
        "empty (unknown to this firmware, or no value right now, e.g. 5G on LTE)",
    ),
    "malformed": ("WARN", "unexpected values, not exported"),
    "refused": (
        "WARN",
        "refused: the request they were in came back as result=failure",
    ),
}


def check_fields(d: dict) -> dict[str, tuple[str, str]]:
    """Every requested field that didn't come back usable: field -> (kind, shown as)."""
    found = {}
    for f in FIELDS:
        v = str(d.get(f, "")).strip()
        if d.get(f) is REFUSED:
            found[f] = ("refused", f)
        elif f not in d:
            found[f] = ("missing", f)
        elif not v:
            found[f] = ("empty", f)
        elif (
            (f in NUMERIC and num(v) is None)
            or (f in BAND_MASKS and mask_bands(v) is None)
            or (f in BAND_LISTS and list_bands(v) is None)
            or (f in WIDTHS and mhz(v) is None)
            or (f in STRUCTURED and PARSERS[f](v) is None)
        ):
            found[f] = ("malformed", f"{f}={v[:40]!r}")
    return found


def log_grouped(found: dict[str, tuple[str, str]], prefix: str = "") -> None:
    for kind, (level, title) in KINDS.items():
        shown = [s for k, s in found.values() if k == kind]
        if shown:
            log(level, f"  {prefix}{title}: {', '.join(shown)}")


class FieldReport:
    """The field check: in full on the first read, then only what changed, at most hourly."""

    def __init__(self) -> None:
        self.logged: dict[str, tuple[str, str]] | None = None
        self.logged_at = 0.0

    def update(self, d: dict) -> None:
        found = check_fields(d)
        now = time.time()
        if found == self.logged:
            return
        total = len(FIELDS)
        usable = f"{total - len(found)} of {total} fields usable"
        if self.logged is None:
            log("INFO", f"field check: {usable}")
            log_grouped(found)
            for f in RAW:
                if d.get(f) is not REFUSED and str(d.get(f, "")).strip():
                    log("INFO", f"  raw {f}={str(d[f])[:300]!r}")
        elif now - self.logged_at >= FIELD_REPORT_INTERVAL:
            log("INFO", f"field check changed: {usable}")
            fixed = sorted(set(self.logged) - set(found))
            if fixed:
                log("INFO", f"  now usable: {', '.join(fixed)}")
            log_grouped(
                {f: v for f, v in found.items() if self.logged.get(f) != v}, "now "
            )
        else:
            return
        self.logged, self.logged_at = found, now


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

    def read(self, fields: tuple[str, ...]) -> dict:
        """All fields in requests of CHUNK, one retry per request (the modem drops one now and then)."""
        out: dict = {}
        for i in range(0, len(fields), CHUNK):
            cmd = ",".join(fields[i : i + CHUNK])
            try:
                part = self.get(cmd)
            except (OSError, ValueError) as e:
                log("WARN", f"read failed ({e}); retrying once")
                time.sleep(2)
                part = self.get(cmd)
            if not isinstance(part, dict):
                raise TypeError(f"reply is not a JSON object: {str(part)[:80]!r}")
            # A name the firmware declines turns the whole reply into {"result": "failure"}.
            if part.get("result") == "failure" and not any(
                f in part for f in fields[i : i + CHUNK]
            ):
                out |= dict.fromkeys(fields[i : i + CHUNK], REFUSED)
                continue
            out |= part
        return out

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
    """Metric families in first-seen order; the text format wants each family in one block."""

    def __init__(self) -> None:
        self.families: dict[str, list[str]] = {}

    def add(
        self,
        name: str,
        help_: str,
        value,
        labels: dict | None = None,
        typ: str = "gauge",
    ) -> None:
        if value is None:
            return
        full = f"homelab_modem_{name}"
        lines = self.families.setdefault(
            full, [f"# HELP {full} {help_}", f"# TYPE {full} {typ}"]
        )
        lab = ",".join(f'{k}="{esc(v)}"' for k, v in (labels or {}).items())
        lines.append(f"{full}{{{lab}}} {value:.15g}" if lab else f"{full} {value:.15g}")

    def write(self) -> None:
        tmp = f"{OUT}.{os.getpid()}"
        with open(tmp, "w") as fh:
            fh.write(
                "\n".join(line for lines in self.families.values() for line in lines)
                + "\n"
            )
        os.chmod(tmp, 0o644)
        os.replace(tmp, OUT)


def paused_until() -> float:
    try:
        with open(PAUSE_FILE) as fh:
            until = float(fh.read().strip())
    except OSError, ValueError:
        return 0.0
    return until if until > time.time() else 0.0


def lte_ids(d: dict) -> dict[str, str]:
    """eNodeB (the base station) and its cell number, decoded from the ECI (cell_id)."""
    return lte_cell(d.get("cell_id", ""))


def carriers(d: dict, p: Prom) -> None:
    """Aggregated carriers (uplink = the primary) and every cell the modem measures."""
    p.add(
        "bandwidth_mhz",
        "Channel width of the serving LTE cell",
        mhz(d.get("bandwidth")),
    )
    pcell = {
        "role": "pcell",
        "index": "0",
        "band": str(d.get("lte_ca_pcell_band", "")).strip(),
        "channel": str(
            d.get("lte_ca_pcell_arfcn") or d.get("wan_active_channel", "")
        ).strip(),
        "pci": str(d.get("lte_pci", "")).strip(),
        "state": "",
    }
    scells = parse_scells(d.get("lte_multi_ca_scell_info", "")) or []
    cells = [pcell] if pcell["band"] else []
    cells += [
        {
            "role": "scell",
            "index": s["index"],
            "band": s["band"],
            "channel": s["earfcn"],
            "pci": s["pci"],
            "state": s["state"],
        }
        for s in scells
    ]
    widths = [mhz(d.get("lte_ca_pcell_bandwidth"))] + [s["width"] for s in scells]
    for c, w in zip(cells, widths if pcell["band"] else widths[1:], strict=False):
        p.add("ca_cell_info", "Aggregated carriers; the pcell carries the uplink", 1, c)
        p.add(
            "ca_bandwidth_mhz",
            "Channel width per aggregated carrier; their sum is the usable width",
            w,
            {"role": c["role"], "index": c["index"], "band": c["band"]},
        )
    for s, sig in zip(
        scells,
        parse_scell_signal(d.get("lte_multi_ca_scell_sig_info", "")) or [],
        strict=False,
    ):
        labels = {"index": s["index"], "band": s["band"]}
        for (metric, help_), v in zip(SCELL_SIGNAL, sig, strict=True):
            p.add(metric, help_, v, labels)
    serving = {(c["channel"], c["pci"]): c["role"] for c in cells}
    for c in parse_cells(d.get("ngbr_cell_info", "")) or []:
        labels = {
            "earfcn": c["earfcn"],
            "pci": c["pci"],
            "band": earfcn_band(c["earfcn"]),
            "role": serving.get((c["earfcn"], c["pci"]), "neighbour"),
        }
        p.add(
            "cell_rsrp_dbm",
            "Every cell the modem measures: serving, aggregated and neighbours",
            c["rsrp"],
            labels,
        )
        p.add(
            "cell_rsrq_db",
            "Every cell the modem measures: serving, aggregated and neighbours",
            c["rsrq"],
            labels,
        )
        p.add(
            "cell_rssi_dbm",
            "Every cell the modem measures: serving, aggregated and neighbours",
            c["rssi"],
            labels,
        )


def poll(password: str, p: Prom, report: FieldReport) -> bool:
    m = Modem(HOST)
    if not m.login(password):
        log("ERROR", "login rejected; backing off before the next attempt")
        p.add("login_ok", "Whether the last login was accepted", 0)
        return False
    p.add("login_ok", "Whether the last login was accepted", 1)
    try:
        d = m.read(FIELDS)
    finally:
        try:
            if not m.logout():
                log("WARN", "logout not acknowledged; the session expires on its own")
        except Exception as e:  # noqa: BLE001 - the poll result matters more than the logout
            log("WARN", f"logout failed: {e}")
    report.update(d)
    d = {k: v for k, v in d.items() if v is not REFUSED}
    # Logged in, but nothing came back: the modem ignored the session. Count it as a failed read.
    if all(num(d.get(f)) is None for f in NUMERIC):
        raise ValueError("the reply has no values (session not accepted?)")

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
            "network_mode": d.get("net_select", ""),
            "operator_select": d.get("net_select_mode", ""),
            "mcc": d.get("mdm_mcc", ""),
            "mnc": d.get("mdm_mnc", ""),
            "roaming": d.get("simcard_roam", ""),
            "firmware": d.get("wa_inner_version", ""),
        },
    )
    p.add(
        "firmware_update_info",
        "Firmware update state (version_idle / fota_idle = nothing waiting or running)",
        1 if d.get("new_version_state") or d.get("current_upgrade_state") else None,
        {
            "version_state": d.get("new_version_state", ""),
            "upgrade_state": d.get("current_upgrade_state", ""),
        },
    )
    p.add(
        "sms_unread",
        "Unread SMS on the modem (the operator's messages land here)",
        num(d.get("sms_unread_num")),
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
                    **(lte_ids(d) if rat == "lte" else {}),
                },
            )
    carriers(d, p)
    for metric, rat, fields in ANTENNA:
        for f, antenna in fields.items():
            p.add(
                f"antenna_{metric}",
                ANTENNA_HELP[rat],
                num(d.get(f)),
                {"rat": rat, "antenna": antenna},
            )
    p.add(
        "tx_power_dbm",
        "Uplink transmit power; near its maximum (23-26 dBm) means the cell barely hears the modem",
        num(d.get("tx_power")),
    )
    for f, rat in BAND_MASKS.items():
        p.add(
            "allowed_bands_info",
            "Bands the modem may use; every supported band means no band lock",
            1 if mask_bands(d.get(f, "")) else None,
            {"rat": rat, "bands": mask_bands(d.get(f, "")) or ""},
        )
    for f, rat in BAND_LISTS.items():
        p.add(
            "allowed_bands_info",
            "Bands the modem may use; every supported band means no band lock",
            1 if list_bands(d.get(f, "")) else None,
            {"rat": rat, "bands": list_bands(d.get(f, "")) or ""},
        )
    cell_lock = {label: str(d.get(f, "")).strip() for f, label in CELL_LOCK.items()}
    if any(cell_lock.values()):
        p.add(
            "cell_lock_info", "LTE locked to one cell (PCI on a channel)", 1, cell_lock
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
    for direction, f in (("tx", "realtime_tx_bytes"), ("rx", "realtime_rx_bytes")):
        p.add(
            "session_bytes_total",
            "Bytes in the current data session; rate() gives the exact average between polls",
            num(d.get(f)),
            {"direction": direction},
            "counter",
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
    report = FieldReport()
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
                ok = poll(password, p, report)
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
