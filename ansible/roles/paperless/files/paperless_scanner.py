"""eSCL (AirScan) document feeder -> Paperless consume folder.

Usage: python3 -I paperless_scanner.py            (the watcher; settings come from the environment)
       python3 -I paperless_scanner.py --healthcheck

The printer cannot push scans to a network folder, so this pulls them: it polls the scanner's
status and, when paper appears in the document feeder and the device stays idle for
SCANNER_SETTLE_SECONDS, scans every sheet into one PDF and moves it into the consume folder.

One stack is scanned once: after a scan (or after someone else used the device while the
feeder was loaded, e.g. a copy started on the panel) nothing happens until the feeder has been
seen empty again. A stack already in the feeder when this starts is left alone for the same
reason.

The printer is expected to be off most of the time: while it does not answer, this only tries
a connection every 15 s and logs the change once. A printer that comes back after at least
SCANNER_POWER_ON_SECONDS of silence was switched on, so a stack found in its feeder then is a
new one and is scanned (load paper, press power, walk away).

Every stack that does not reach Paperless is logged on a line starting "Scan failed:".

Everything it touches:
  GET    <SCANNER_URL>/ScannerCapabilities, <SCANNER_URL>/ScannerStatus
  POST   <SCANNER_URL>/ScanJobs
  GET    <job>/NextDocument      DELETE <job>
  writes <CONSUME_DIR>/._scan-*.part (ignored by Paperless), renamed to <CONSUME_DIR>/scan-*.pdf
  writes HEARTBEAT_FILE
"""

import contextlib
import dataclasses
import http.client
import os
import signal
import ssl
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

URL = urllib.parse.urlsplit(os.environ.get("SCANNER_URL", "http://127.0.0.1:80/eSCL"))
HOST = URL.hostname or "127.0.0.1"
PORT = URL.port or (443 if URL.scheme == "https" else 80)
CONSUME_DIR = os.environ.get("CONSUME_DIR", "/consume")
HEARTBEAT_FILE = os.environ.get("HEARTBEAT_FILE", "/tmp/paperless-scanner.alive")
POLL_SECONDS = float(os.environ.get("SCANNER_POLL_SECONDS", "3"))
SETTLE_SECONDS = float(os.environ.get("SCANNER_SETTLE_SECONDS", "4"))
RESOLUTION = int(os.environ.get("SCANNER_RESOLUTION", "300"))
COLOR_MODE = os.environ.get("SCANNER_COLOR_MODE", "RGB24")
# Scan area in 1/300 inch (the unit eSCL uses whatever the resolution). Default: A4.
PAGE_WIDTH = int(os.environ.get("SCANNER_PAGE_WIDTH", "2480"))
PAGE_HEIGHT = int(os.environ.get("SCANNER_PAGE_HEIGHT", "3508"))
MAX_PAGES = int(os.environ.get("SCANNER_MAX_PAGES", "100"))
# Silence at least this long counts as "the printer was off" (0 disables scan-on-power-on).
POWER_ON_SECONDS = float(os.environ.get("SCANNER_POWER_ON_SECONDS", "60"))

STATUS_TIMEOUT = 10
# One NextDocument answer is one scanned sheet: the request blocks while the sheet is fed.
PAGE_TIMEOUT = 120
# The scanner answers 503 while the next sheet is not ready yet.
BUSY_RETRIES = 30
UNREACHABLE_POLL_SECONDS = 15
# How often one stack is offered to a scanner that refuses the job.
START_ATTEMPTS = 3
HEALTH_MAX_AGE = 300

NS_SCAN = "http://schemas.hp.com/imaging/escl/2011/05/03"
NS_PWG = "http://www.pwg.org/schemas/2010/12/sm"


class ScannerError(Exception):
    pass


class NotStarted(ScannerError):
    """The scanner refused the job (warming up, busy): no sheet was fed, so it can be retried."""


class Busy(ScannerError):
    """NextDocument kept answering 503."""


IO_ERRORS = (OSError, http.client.HTTPException)


class Stop(Exception):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def heartbeat() -> None:
    with open(HEARTBEAT_FILE, "w") as f:
        f.write(str(int(time.time())))


# --- HTTP -----------------------------------------------------------------------------


def request(
    method: str, path: str, body: bytes | None = None, timeout: float = STATUS_TIMEOUT
) -> tuple[int, http.client.HTTPMessage, bytes]:
    if URL.scheme == "https":
        # Printers ship a self-signed certificate; there is nothing to verify it against.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(
            HOST, PORT, timeout=timeout, context=context
        )
    else:
        conn = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", f"{HOST}:{PORT}")
        conn.putheader("Connection", "close")
        if body is not None:
            conn.putheader("Content-Type", "text/xml")
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        response = conn.getresponse()
        return response.status, response.msg, response.read()
    finally:
        conn.close()


def escl(path: str) -> str:
    return URL.path.rstrip("/") + "/" + path


# --- eSCL XML -------------------------------------------------------------------------


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first_text(root: ET.Element, name: str) -> str | None:
    for element in root.iter():
        if local(element.tag) == name:
            return (element.text or "").strip()
    return None


FEEDER_EMPTY = "ScannerAdfEmpty"
FEEDER_LOADED = "ScannerAdfLoaded"
# After a scan the feeder sensor can take a moment to settle.
AFTER_SCAN_CHECKS = 5


def read_status() -> tuple[str | None, str | None]:
    status, _, body = request("GET", escl("ScannerStatus"))
    if status != 200:
        raise ScannerError(f"ScannerStatus answered HTTP {status}")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise ScannerError(f"ScannerStatus is not XML: {e}") from e
    return first_text(root, "State"), first_text(root, "AdfState")


@dataclasses.dataclass
class Caps:
    """What the feeder supports; what the scanner leaves out stays as configured."""

    max_width: int | None = None
    max_height: int | None = None
    resolutions: list[int] = dataclasses.field(default_factory=list[int])
    color_modes: list[str] = dataclasses.field(default_factory=list[str])
    format_ext: bool = False
    has_adf: bool = False


def read_capabilities() -> Caps:
    caps = Caps()
    status, _, body = request("GET", escl("ScannerCapabilities"))
    try:
        if status != 200:
            raise ScannerError(f"HTTP {status}")
        root = ET.fromstring(body)
    except (ScannerError, ET.ParseError) as e:
        log(
            f"ScannerCapabilities unreadable ({e}): scanning with the configured settings"
        )
        return caps
    model = first_text(root, "MakeAndModel") or "unknown model"
    log(f"Scanner: {model}, eSCL {first_text(root, 'Version') or '?'}")
    for element in root.iter():
        if local(element.tag) != "AdfSimplexInputCaps":
            continue
        caps.has_adf = True
        for node in element.iter():
            name, text = local(node.tag), (node.text or "").strip()
            if name == "MaxWidth" and text.isdigit():
                caps.max_width = int(text)
            elif name == "MaxHeight" and text.isdigit():
                caps.max_height = int(text)
            elif name == "XResolution" and text.isdigit():
                caps.resolutions.append(int(text))
            elif name == "ColorMode":
                caps.color_modes.append(text)
            elif name == "DocumentFormatExt":
                caps.format_ext = True
        break
    if not caps.has_adf:
        log("The scanner lists no document feeder: nothing will be scanned")
    return caps


def scan_settings(caps: Caps) -> tuple[bytes, int]:
    width, height, resolution, color = PAGE_WIDTH, PAGE_HEIGHT, RESOLUTION, COLOR_MODE
    if caps.max_width:
        width = min(width, caps.max_width)
    if caps.max_height:
        height = min(height, caps.max_height)
    if caps.resolutions and resolution not in caps.resolutions:
        resolution = min(caps.resolutions, key=lambda r: abs(r - resolution))
    if caps.color_modes and color not in caps.color_modes:
        color = next(
            (c for c in ("RGB24", "Grayscale8") if c in caps.color_modes),
            caps.color_modes[0],
        )
    ext = (
        "<scan:DocumentFormatExt>image/jpeg</scan:DocumentFormatExt>"
        if caps.format_ext
        else ""
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<scan:ScanSettings xmlns:scan="{NS_SCAN}" xmlns:pwg="{NS_PWG}">'
        "<pwg:Version>2.0</pwg:Version>"
        "<pwg:ScanRegions><pwg:ScanRegion>"
        "<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>"
        "<pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset>"
        f"<pwg:Width>{width}</pwg:Width><pwg:Height>{height}</pwg:Height>"
        "</pwg:ScanRegion></pwg:ScanRegions>"
        "<pwg:InputSource>Feeder</pwg:InputSource>"
        f"<scan:ColorMode>{color}</scan:ColorMode>"
        "<pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>"
        f"{ext}"
        f"<scan:XResolution>{resolution}</scan:XResolution>"
        f"<scan:YResolution>{resolution}</scan:YResolution>"
        "<scan:Duplex>false</scan:Duplex>"
        "</scan:ScanSettings>"
    )
    return xml.encode(), resolution


# --- PDF ------------------------------------------------------------------------------


def jpeg_size(data: bytes) -> tuple[int, int, int]:
    """Width, height and component count from the JPEG frame header."""
    if data[:2] != b"\xff\xd8":
        raise ScannerError("the scanner sent something that is not a JPEG")
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            raise ScannerError("broken JPEG: marker expected")
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            i += 2
            continue
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return width, height, data[i + 9]
        i += 2 + length
    raise ScannerError("broken JPEG: no frame header")


class PdfWriter:
    """One JPEG per page, embedded as it is (DCTDecode): no re-encoding, nothing kept in memory."""

    def __init__(self, path: str, resolution: int) -> None:
        self.file = open(path, "wb")  # noqa: SIM115 (closed by close()/abort())
        self.resolution = resolution
        self.offsets: dict[int, int] = {}
        self.pages: list[int] = []
        self.file.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    def _object(self, number: int, body: bytes, stream: bytes | None = None) -> None:
        self.offsets[number] = self.file.tell()
        self.file.write(b"%d 0 obj\n" % number + body)
        if stream is not None:
            self.file.write(b"\nstream\n" + stream + b"\nendstream")
        self.file.write(b"\nendobj\n")

    def add_page(self, jpeg: bytes) -> None:
        width, height, components = jpeg_size(jpeg)
        colorspace = {1: b"/DeviceGray", 3: b"/DeviceRGB"}.get(components)
        if colorspace is None:
            raise ScannerError(
                f"JPEG with {components} colour components is not supported"
            )
        points_w = width * 72 / self.resolution
        points_h = height * 72 / self.resolution
        # Objects 1 and 2 are the catalog and the page tree, written last.
        image = 3 + 3 * len(self.pages)
        content, page = image + 1, image + 2
        self._object(
            image,
            b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %s"
            b" /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>"
            % (width, height, colorspace, len(jpeg)),
            jpeg,
        )
        draw = b"q %.2f 0 0 %.2f 0 0 cm /Im0 Do Q" % (points_w, points_h)
        self._object(content, b"<< /Length %d >>" % len(draw), draw)
        self._object(
            page,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f]"
            b" /Resources << /XObject << /Im0 %d 0 R >> >> /Contents %d 0 R >>"
            % (points_w, points_h, image, content),
        )
        self.pages.append(page)
        self.file.flush()

    def close(self) -> None:
        kids = b" ".join(b"%d 0 R" % p for p in self.pages)
        self._object(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        self._object(
            2, b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(self.pages))
        )
        count = 3 + 3 * len(self.pages)
        xref = self.file.tell()
        self.file.write(b"xref\n0 %d\n0000000000 65535 f \n" % count)
        for number in range(1, count):
            self.file.write(b"%010d 00000 n \n" % self.offsets[number])
        self.file.write(
            b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (count, xref)
        )
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()

    def abort(self) -> None:
        self.file.close()


# --- Scanning -------------------------------------------------------------------------


def next_page(job: str) -> bytes | None:
    """The next sheet as a JPEG, or None when the feeder is empty."""
    for _ in range(BUSY_RETRIES):
        status, _, body = request("GET", job + "/NextDocument", timeout=PAGE_TIMEOUT)
        if status == 200:
            return body or None
        if status in (404, 410):
            return None
        if status != 503:
            raise ScannerError(f"NextDocument answered HTTP {status}")
        time.sleep(1)
    raise Busy("the scanner stayed busy (HTTP 503)")


def start_job(settings: bytes) -> str:
    try:
        status, headers, _ = request("POST", escl("ScanJobs"), settings)
    except IO_ERRORS as e:
        raise NotStarted(str(e)) from e
    location = headers.get("Location")
    if status != 201 or not location:
        raise NotStarted(f"ScanJobs answered HTTP {status}")
    return urllib.parse.urlsplit(location).path.rstrip("/")


def scan_feeder() -> None:
    # Read for every scan: a printer that is still booting may answer the first read badly.
    try:
        caps = read_capabilities()
    except IO_ERRORS as e:
        raise NotStarted(str(e)) from e
    settings, resolution = scan_settings(caps)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    part = os.path.join(CONSUME_DIR, f"._scan-{stamp}.part")
    final = os.path.join(CONSUME_DIR, f"scan-{stamp}.pdf")
    # The output file first: a consume folder we cannot write to must not leave a job open.
    pdf = PdfWriter(part, resolution)
    try:
        job = start_job(settings)
    except BaseException:
        pdf.abort()
        os.unlink(part)
        raise
    problem = None
    try:
        while len(pdf.pages) < MAX_PAGES:
            page = next_page(job)
            if page is None:
                break
            pdf.add_page(page)
            heartbeat()
            log(f"Page {len(pdf.pages)} scanned ({len(page) // 1024} KiB)")
    except (ScannerError, *IO_ERRORS, Stop) as e:
        # Keep the sheets that did come through (a jam after page 7 still leaves 7 good pages).
        problem = e
    finally:
        with contextlib.suppress(*IO_ERRORS):
            request("DELETE", job)
        if pdf.pages:
            pdf.close()
            os.replace(part, final)
            log(
                f"{os.path.basename(final)}: {len(pdf.pages)} page(s) handed to Paperless"
            )
        else:
            pdf.abort()
            os.unlink(part)
    if isinstance(problem, Stop):
        raise problem
    if isinstance(problem, Busy) and not pdf.pages:
        # Nothing came out of the feeder, so the whole stack is still in it: safe to retry.
        raise NotStarted(str(problem))
    if problem is not None:
        raise ScannerError(
            f"scan ended early after {len(pdf.pages)} page(s): {problem}"
        )
    if not pdf.pages:
        log("The feeder gave no pages")
    check_feeder_after_scan(len(pdf.pages))


def check_feeder_after_scan(pages: int) -> None:
    """A jam can end the job early without an error: only the feeder shows it."""
    adf = None
    for _ in range(AFTER_SCAN_CHECKS):
        time.sleep(POLL_SECONDS)
        with contextlib.suppress(*IO_ERRORS, ScannerError):
            _, adf = read_status()
            if adf == FEEDER_EMPTY:
                return
    if adf is not None:
        log(
            f"Scan failed: the feeder still reports {adf} after {pages} page(s) "
            "(jam or misfeed?); what came through went to Paperless, scan the rest"
        )


def remove_stale_parts() -> None:
    """A scan killed half-way (container stopped mid-stack) leaves an unfinished file."""
    with contextlib.suppress(OSError):
        for name in os.listdir(CONSUME_DIR):
            if name.startswith("._scan-") and name.endswith(".part"):
                with contextlib.suppress(OSError):
                    os.unlink(os.path.join(CONSUME_DIR, name))
                    log(f"Scan failed: {name} was interrupted; scan that stack again")


def watch() -> None:
    def stop(*_: object) -> None:
        raise Stop

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log(
        f"Watching {URL.scheme}://{HOST}:{PORT}{URL.path} every {POLL_SECONDS:g} s; "
        f"scanning {SETTLE_SECONDS:g} s after paper appears in the feeder"
    )
    remove_stale_parts()
    reachable = None
    armed = False
    loaded_since = None
    adf_reported = None
    first = True
    attempts = 0
    # When the scanner stopped answering, and whether it answered at all since we started.
    silent_since: float | None = None
    answered = False

    while True:
        heartbeat()
        try:
            state, adf = read_status()
        except (*IO_ERRORS, ScannerError) as e:
            if reachable is not False:
                log(f"Scanner unreachable (off, asleep or blocked?): {e}")
            if silent_since is None:
                silent_since = time.monotonic()
            reachable, loaded_since = False, None
            time.sleep(UNREACHABLE_POLL_SECONDS)
            continue
        if reachable is not True:
            log("Scanner reachable")
            # Off since our start counts as off: there is no earlier stack to protect.
            was_off = reachable is False and (
                not answered
                or silent_since is None
                or time.monotonic() - silent_since >= POWER_ON_SECONDS
            )
            if was_off and POWER_ON_SECONDS > 0:
                armed, attempts, first = True, 0, False
            reachable, silent_since, answered = True, None, True
        if (adf is not None) != adf_reported:
            adf_reported = adf is not None
            if not adf_reported:
                log("ScannerStatus carries no AdfState: the feeder cannot be watched")

        if adf is None or adf == FEEDER_EMPTY:
            armed, loaded_since, attempts = True, None, 0
        elif adf != FEEDER_LOADED:
            # Jam, misfeed, cover open, ...: never a reason to scan. Wait for an empty feeder.
            if armed or loaded_since is not None:
                log(f"Feeder reports {adf}: waiting until it is empty")
            armed, loaded_since = False, None
        elif not armed:
            if first:
                log("Feeder already loaded at start: left alone until emptied")
        elif state != "Idle":
            log(f"Feeder loaded but the device is {state}: left alone until emptied")
            armed, loaded_since = False, None
        elif loaded_since is None:
            loaded_since = time.monotonic()
            log(f"Paper in the feeder: scanning in {SETTLE_SECONDS:g} s")
        elif time.monotonic() - loaded_since >= SETTLE_SECONDS:
            armed, loaded_since = False, None
            try:
                scan_feeder()
            except NotStarted as e:
                attempts += 1
                armed = attempts < START_ATTEMPTS
                if armed:
                    log(f"Scan not started: {e}; trying again")
                else:
                    log(f"Scan failed: not started after {attempts} attempts: {e}")
            except (*IO_ERRORS, ScannerError) as e:
                log(f"Scan failed: {e}")
        first = False
        time.sleep(POLL_SECONDS)


def healthcheck() -> int:
    try:
        age = time.time() - os.stat(HEARTBEAT_FILE).st_mtime
    except OSError:
        return 1
    return 0 if age < HEALTH_MAX_AGE else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--healthcheck"]:
        sys.exit(healthcheck())
    try:
        watch()
    except Stop:
        log("Stopping")
