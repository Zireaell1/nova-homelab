import re
from collections import Counter

import jinja2
import yaml

from _common import GROUP_VARS, ROLES, load, read

TITLE = "Alert rules: unique uids, NoData is healthy, every expr compares"

TEMPLATE = ROLES / "grafana/templates/alerting.yml.j2"
SEVERITIES = {"critical", "warning"}
ANNOTATIONS = ("summary", "impact", "action")
COMPARES = re.compile(r"(==|!=|>=|<=|(?<![-=])>|<(?!-))|\babsent(_over_time)?\(")


def render() -> dict:
    ctx: dict = {}
    for f in sorted(ROLES.glob("*/defaults/main.yml")) + sorted(
        GROUP_VARS.rglob("*.yml")
    ):
        data = load(f)
        if isinstance(data, dict):
            ctx |= data
    env = jinja2.Environment(undefined=jinja2.ChainableUndefined)
    return yaml.safe_load(env.from_string(read(TEMPLATE)).render(**ctx))


def check() -> list[str]:
    try:
        doc = render()
    except (jinja2.TemplateError, yaml.YAMLError) as e:
        return [f"{TEMPLATE}: does not render to YAML: {e}"]

    bad = []
    rules = [(g["name"], r) for g in doc.get("groups", []) for r in g.get("rules", [])]
    for uid, n in Counter(r.get("uid") for _, r in rules).items():
        if n > 1:
            bad.append(f"uid {uid!r} is used {n} times (provisioning keeps only one)")

    for group, r in rules:
        where = f"{group}/{r.get('uid')}"
        refs = {d.get("refId"): d for d in r.get("data", [])}
        cond = refs.get(r.get("condition"))
        if cond is None:
            bad.append(f"{where}: condition {r.get('condition')!r} matches no refId")
            continue
        if r.get("noDataState") != "OK":
            bad.append(
                f"{where}: noDataState {r.get('noDataState')!r} — every expr is empty when healthy, so NoData must be OK"
            )
        expr = str(cond.get("model", {}).get("expr", ""))
        if expr and not COMPARES.search(expr):
            bad.append(
                f"{where}: expr has no comparison and would fire on any non-zero value: {expr}"
            )
        sev = (r.get("labels") or {}).get("severity")
        if sev not in SEVERITIES:
            bad.append(f"{where}: severity {sev!r} not in {sorted(SEVERITIES)}")
        missing = [a for a in ANNOTATIONS if not (r.get("annotations") or {}).get(a)]
        if missing:
            bad.append(f"{where}: missing annotation(s) {', '.join(missing)}")
    return bad
