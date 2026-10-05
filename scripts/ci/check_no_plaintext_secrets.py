import subprocess

TITLE = "No plaintext vault, vault password or inventory is tracked by git"

NEVER_TRACKED = (".vault_pass", "ansible/inventory.ini")


def check() -> list[str]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout.split("\0")

    problems = [
        f"{f}: must never be committed" for f in tracked if f.endswith(NEVER_TRACKED)
    ]
    for f in tracked:
        name = f.rsplit("/", 1)[-1]
        if f.startswith("examples/") or not (
            name.startswith("vault") and name.endswith((".yml", ".yaml"))
        ):
            continue
        with open(f, encoding="utf-8", errors="replace") as fh:
            if not fh.readline().startswith("$ANSIBLE_VAULT;"):
                problems.append(f"{f}: tracked vault file is not encrypted")
    return problems
