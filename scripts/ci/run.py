import importlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _common import ROOT  # noqa: E402

GHA = os.environ.get("GITHUB_ACTIONS") == "true"


def main(argv: list[str]) -> int:
    os.chdir(ROOT)
    names = sorted(p.stem for p in HERE.glob("check_*.py"))
    if argv:
        wanted = {a.removeprefix("check_").removesuffix(".py") for a in argv}
        unknown = wanted - {n.removeprefix("check_") for n in names}
        if unknown:
            print(f"unknown check(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        names = [n for n in names if n.removeprefix("check_") in wanted]

    failed = []
    for name in names:
        mod = importlib.import_module(name)
        problems = mod.check()
        status = "FAIL" if problems else "ok"
        print(
            f"::group::{status} · {mod.TITLE}" if GHA else f"[{status:>4}] {mod.TITLE}"
        )
        for p in problems:
            print(f"::error title={name}::{p}" if GHA else f"       {p}")
        if GHA:
            print("::endgroup::")
        if problems:
            failed.append(name)

    print(f"\n{len(names) - len(failed)}/{len(names)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
