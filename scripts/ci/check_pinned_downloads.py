import hashlib
import re
import sys
import urllib.error
import urllib.request

from _common import ROLES, read, role_vars

TITLE = "Pinned downloads match their sha256 (prints the right one when a pin moved)"

# (role, the get_url url with {var} placeholders, the sha256 variable)
PINS = [
    (
        "grafana",
        "https://raw.githubusercontent.com/rfmoz/grafana-dashboards/"
        "{grafana_node_exporter_full_commit}/prometheus/node-exporter-full.json",
        "grafana_node_exporter_full_sha256",
    ),
]
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def fill(template: str, values: dict) -> str:
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)


def check() -> list[str]:
    bad = []
    for role, template, sha_var in PINS:
        jinja = PLACEHOLDER.sub(lambda m: "{{ " + m.group(1) + " }}", template)
        if jinja not in read(ROLES / role / "tasks" / "main.yml"):
            bad.append(f"{role}: tasks/main.yml no longer fetches {jinja}; update PINS")
            continue
        values = role_vars(ROLES / role)
        url = fill(template, values)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                digest = hashlib.sha256(r.read()).hexdigest()
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"       (skipped {url}: {e})", file=sys.stderr)
            continue
        if digest != values[sha_var]:
            bad.append(
                f"{role}: {sha_var} is {values[sha_var]}, but the file at the pinned "
                f"commit hashes to {digest}: put that in roles/{role}/defaults/main.yml"
            )
    return bad
