import re
from pathlib import Path

from _common import read

TITLE = "vault.yml.example lists every vault_* key the code uses"

IGNORED = {"vault_pass", "vault_password_file", "vault_headers"}


def check() -> list[str]:
    used: set[str] = set()
    for f in Path("ansible").rglob("*"):
        if f.is_file():
            try:
                used |= set(re.findall(r"vault_[a-z0-9_]+", read(f)))
            except UnicodeDecodeError:
                continue
    example = read(Path("examples/vault.yml.example"))
    defined = set(re.findall(r"^(vault_[a-z0-9_]+)", example, re.MULTILINE))
    return [
        f"missing from vault.yml.example: {k}" for k in sorted(used - defined - IGNORED)
    ]
