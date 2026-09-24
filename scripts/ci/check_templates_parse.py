import jinja2

from _common import ROLES, read

TITLE = "Every Jinja template parses"


def check() -> list[str]:
    env, bad = jinja2.Environment(), []
    for f in sorted(ROLES.glob("*/templates/**/*.j2")):
        try:
            env.parse(read(f))
        except jinja2.TemplateSyntaxError as e:
            bad.append(f"{f}:{e.lineno}: {e.message}")
    return bad
