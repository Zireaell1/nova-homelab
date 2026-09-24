from pathlib import Path

from _common import ROLES, load, read

TITLE = "Every endpoint has a Caddy route and an Authelia rule"

REGISTRY = Path("ansible/group_vars/all/endpoints.yml")
KEY = "service_endpoints"


def check() -> list[str]:
    endpoints = load(REGISTRY)[KEY]
    caddy = read(ROLES / "caddy/templates/Caddyfile.j2")
    authelia = read(ROLES / "authelia/templates/configuration.yml.j2")
    bad = []
    for name, e in endpoints.items():
        if (e or {}).get("root"):
            c_ref, a_ref = "\n{{ vault_domain }} {", "domain: '{{ vault_domain }}'"
        else:
            c_ref = a_ref = f"{KEY}['{name}']"
        if c_ref not in caddy:
            bad.append(f"{name}: in registry but no block in Caddyfile.j2")
        if a_ref not in authelia:
            bad.append(f"{name}: in registry but no access_control rule")
    return bad
