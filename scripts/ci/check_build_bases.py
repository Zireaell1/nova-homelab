import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import jinja2

from _common import ROLES, load, read

TITLE = "Every image a Containerfile builds FROM exists in its registry"

FROM = re.compile(r"^FROM\s+(\S+)", re.MULTILINE)
CHALLENGE = re.compile(r'(\w+)="([^"]*)"')
ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def split(ref: str) -> tuple[str, str, str]:
    name, _, tag = ref.rpartition(":")
    host, _, repo = name.partition("/")
    if host == "docker.io":
        host = "registry-1.docker.io"
        if "/" not in repo:
            repo = f"library/{repo}"
    return host, repo, tag


def head(url: str, token: str | None = None) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"Accept": ACCEPT})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        if e.code == 401 and token is None:
            raise
        return e.code


def status(ref: str) -> int:
    host, repo, tag = split(ref)
    url = f"https://{host}/v2/{repo}/manifests/{tag}"
    try:
        return head(url)
    except urllib.error.HTTPError as e:
        params = dict(CHALLENGE.findall(e.headers.get("WWW-Authenticate", "")))
        query = urllib.parse.urlencode(
            {k: v for k, v in params.items() if k in ("service", "scope")}
        )
        with urllib.request.urlopen(f"{params['realm']}?{query}", timeout=20) as r:
            body = json.load(r)
        return head(url, body.get("token") or body.get("access_token"))


def check() -> list[str]:
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    bad = []
    for path in sorted(ROLES.glob("*/templates/Containerfile*.j2")):
        defaults = load(path.parents[1] / "defaults" / "main.yml") or {}
        try:
            text = env.from_string(read(path)).render(**defaults)
        except jinja2.UndefinedError as e:
            bad.append(
                f"{path}: cannot render the FROM lines from the role defaults ({e})"
            )
            continue
        for ref in dict.fromkeys(FROM.findall(text)):
            try:
                code = status(ref)
            except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
                print(f"       (skipped {ref}: {e})", file=sys.stderr)
                continue
            # Only a 404 means "missing"; a rate limit (429) or an outage (5xx) skips.
            if code == 404:
                bad.append(f"{path}: {ref} does not exist (yet) in its registry")
            elif code != 200:
                print(
                    f"       (skipped {ref}: registry answered {code})", file=sys.stderr
                )
    return bad
