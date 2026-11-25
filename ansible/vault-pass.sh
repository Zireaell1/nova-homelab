#!/usr/bin/env bash
#
# Prints the Ansible Vault password on stdout.
#
# ==============================================================================
# Commands used in this script:
#
# * security find-generic-password -a <user> -s nova-ansible-vault -w
#                         : Reads the password from the macOS login Keychain (-w = print only the password).
# * cat ansible/.vault_pass
#                         : Fallback when there is no Keychain item.
#
# One-time setup on a Mac (prompts for the password):
#   security add-generic-password -a "$USER" -s nova-ansible-vault -w
# Change it later: same command with -U. Remove: security delete-generic-password -a "$USER" -s nova-ansible-vault
# ==============================================================================

set -euo pipefail

SERVICE="nova-ansible-vault"
ACCOUNT="${USER:-$(id -un)}"
FALLBACK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.vault_pass"

if command -v security >/dev/null 2>&1 \
    && security find-generic-password -a "$ACCOUNT" -s "$SERVICE" -w 2>/dev/null; then
    exit 0
fi

if [ -r "$FALLBACK" ]; then
    cat "$FALLBACK"
    exit 0
fi

echo >&2 "No vault password: add it to the Keychain (security add-generic-password -a \"\$USER\" -s ${SERVICE} -w) or write it to ${FALLBACK}"
exit 1
