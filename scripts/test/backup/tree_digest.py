"""Lists files under paths as `type mode size sha256 path`, so two trees can be diffed.

    tree_digest.py [--root PREFIX] [--exclude GLOB ...] PATH...

PATH is the path as it is on the source; with --root the tree is read from PREFIX/PATH (a restore
target) and printed as PATH, so a source listing and a restore listing compare line for line.
An --exclude glob drops matching paths and everything below them, like restic's --exclude.
"""

import argparse
import fnmatch
import hashlib
import os
import stat
import sys


def excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def entry(real: str, shown: str) -> str:
    st = os.lstat(real)
    mode = stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        return f"l {mode:o} - {os.readlink(real)} {shown}"
    if stat.S_ISDIR(st.st_mode):
        return f"d {mode:o} - - {shown}"
    digest = hashlib.sha256()
    with open(real, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return f"f {mode:o} {st.st_size} {digest.hexdigest()} {shown}"


def walk(root: str, path: str, patterns: list[str]) -> list[str]:
    out: list[str] = []
    real_top = root + path
    if not os.path.lexists(real_top):
        return [f"missing {path}"]
    if excluded(path, patterns):
        return out
    out.append(entry(real_top, path))
    if os.path.isdir(real_top) and not os.path.islink(real_top):
        for dirpath, dirnames, filenames in os.walk(real_top):
            shown_dir = dirpath[len(root) :] if root else dirpath
            keep = []
            for d in sorted(dirnames):
                shown = f"{shown_dir}/{d}"
                if excluded(shown, patterns):
                    continue
                out.append(entry(os.path.join(dirpath, d), shown))
                if not os.path.islink(os.path.join(dirpath, d)):
                    keep.append(d)
            dirnames[:] = keep
            for name in sorted(filenames):
                shown = f"{shown_dir}/{name}"
                if not excluded(shown, patterns):
                    out.append(entry(os.path.join(dirpath, name), shown))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()
    lines: list[str] = []
    for p in args.paths:
        lines += walk(args.root.rstrip("/"), p.rstrip("/"), args.exclude)
    sys.stdout.write("".join(f"{line}\n" for line in sorted(lines)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
