import posixpath
import re

from _common import ROLES, load, walk

TITLE = "Every deployed file has a parent directory created by its own role"

FILE_MODULES = (
    "ansible.builtin.template",
    "ansible.builtin.copy",
    "ansible.builtin.get_url",
)
SINGLE_VAR = re.compile(r"^\{\{\s*([a-z0-9_]+)\s*\}\}$")


def created_dirs(tasks: list[dict]) -> set[str]:
    dirs: set[str] = set()
    for t in tasks:
        mod = t.get("ansible.builtin.file")
        if isinstance(mod, dict) and mod.get("state") == "directory":
            path = str(mod.get("path", "")).strip()
            loop = t.get("loop")
            if isinstance(loop, list) and "item" in path:
                for it in loop:
                    if path == "{{ item }}":
                        dirs.add(str(it))
                    elif path == "{{ item.path }}" and isinstance(it, dict):
                        dirs.add(str(it.get("path")))
            else:
                dirs.add(path)
        git = t.get("ansible.builtin.git")
        if isinstance(git, dict):
            dirs.add(str(git.get("dest")))
        inc = t.get("ansible.builtin.include_role")
        if isinstance(inc, dict) and inc.get("name") == "podman_service":
            v = t.get("vars") or {}
            dirs |= {str(d) for d in (v.get("podman_service_dirs") or [])}
            dirs |= {"{{ quadlet_path }}", "{{ user_units_path }}"}
    return dirs


def destinations(tasks: list[dict]) -> list[tuple[str, str]]:
    out = []
    for t in tasks:
        for mod in FILE_MODULES:
            args = t.get(mod)
            if isinstance(args, dict) and args.get("dest"):
                out.append((str(t.get("name")), str(args["dest"])))
        args = t.get("ansible.builtin.unarchive")
        if isinstance(args, dict) and args.get("dest"):
            out.append((str(t.get("name")), str(args["dest"]).rstrip("/") + "/_"))
        inc = t.get("ansible.builtin.include_role")
        if isinstance(inc, dict) and inc.get("name") == "podman_service":
            v = t.get("vars") or {}
            for e in (v.get("podman_service_templates") or []) + (
                v.get("podman_service_secrets") or []
            ):
                out.append((str(t.get("name")), str(e.get("dest"))))
    return out


def check() -> list[str]:
    bad = []
    for role in sorted(p for p in ROLES.iterdir() if p.is_dir()):
        tasks = [t for f in sorted(role.glob("tasks/*.yml")) for t in walk(load(f))]
        defaults = {}
        for f in role.glob("defaults/*.yml"):
            defaults |= load(f) or {}
        dirs = created_dirs(tasks)
        for name, dest in destinations(tasks):
            m = SINGLE_VAR.match(dest)
            if m and isinstance(defaults.get(m.group(1)), str):
                dest = defaults[m.group(1)]
            if not dest.startswith("{{") or "item" in dest:
                continue
            parent = posixpath.dirname(dest)
            if not any(d == parent or d.startswith(parent + "/") for d in dirs):
                bad.append(f"{role.name}: {name}: {dest} (parent {parent} not created)")
    return bad
