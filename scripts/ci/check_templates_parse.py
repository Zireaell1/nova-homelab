import re

import jinja2

from _common import ROLES, read

TITLE = "Every Jinja template parses, and no block tag silently joins two lines"

BLOCK_AT_EOL = re.compile(r"\S.*(\{%-?\s*end\w*\s*-?%\})[ \t]*$")


def check() -> list[str]:
    env, bad = jinja2.Environment(), []
    for f in sorted(ROLES.glob("*/templates/**/*.j2")):
        text = read(f)
        try:
            env.parse(text)
        except jinja2.TemplateSyntaxError as e:
            bad.append(f"{f}:{e.lineno}: {e.message}")
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines[:-1]):
            if BLOCK_AT_EOL.search(line) and lines[i + 1].strip():
                bad.append(
                    f"{f}:{i + 1}: block tag ends a line with content after it; "
                    f"trim_blocks joins line {i + 2} onto it"
                )
    return bad
