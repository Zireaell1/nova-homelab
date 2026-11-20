#!/usr/bin/env bash
#
# One-line status values for fastfetch's `command` modules.
# Reads only local files and local tools.
#
#   fastfetch-status.sh storage           / 41% · immich 41% · backup 17%
#   fastfetch-status.sh backup DIR        ok, 6h ago · offsite ok
#   fastfetch-status.sh ups NAME          online · 100% · 42 min
#   fastfetch-status.sh updates DIR       3 pending (1 security) · reboot needed
#
# DIR is the Alloy textfile directory (*.prom). Missing data prints "unknown", never an error.
#
# ==============================================================================
# Commands used in this script:
#
# * df --output=target,pcent           : Usage of every real filesystem (tmpfs, overlays, /boot left out).
# * awk on *.prom                      : Reads single metric values written by the backup and updates collectors.
# * upsc NAME ups.status ...           : NUT's read-only client: on line / on battery, charge, runtime.
# ==============================================================================

set -u

RED=$'\e[91m'
YELLOW=$'\e[93m'
RESET=$'\e[0m'

# metric FILE NAME [LABELS]: value of a metric line, empty if missing.
metric() {
    [ -r "$1" ] || return 0
    awk -v m="$2${3:-}" '$1 == m { print $2; exit }' "$1"
}

# ago EPOCH: "6h ago" / "35m ago" / "2d ago".
ago() {
    local s=$(($(date +%s) - ${1%.*}))
    if [ "$s" -lt 3600 ]; then
        echo "$((s / 60))m ago"
    elif [ "$s" -lt 172800 ]; then
        echo "$((s / 3600))h ago"
    else
        echo "$((s / 86400))d ago"
    fi
}

storage() {
    df -x tmpfs -x devtmpfs -x efivarfs -x overlay -x squashfs --output=target,pcent 2>/dev/null |
        awk -v red="$RED" -v yellow="$YELLOW" -v reset="$RESET" '
            NR > 1 && $1 !~ "^/boot" {
                name = $1; sub(".*/", "", name); if (name == "") name = "/"
                pct = $2 + 0
                col = pct >= 95 ? red : (pct >= 80 ? yellow : "")
                printf "%s%s %s%s%s", (n++ ? " · " : ""), name, col, $2, (col ? reset : "")
            }
            END { print "" }'
}

backup() {
    local dir=$1 ok last sync verify out
    ok=$(metric "$dir/homelab_backup.prom" homelab_backup_success)
    last=$(metric "$dir/homelab_backup.prom" homelab_backup_last_run_timestamp_seconds)
    sync=$(metric "$dir/homelab_backup.prom" homelab_backup_cloud_sync_success)
    verify=$(metric "$dir/homelab_backup_verify.prom" homelab_backup_verify_success)
    if [ -z "$ok" ] || [ -z "$last" ]; then
        echo "unknown"
        return
    fi
    if [ "$ok" = "1" ]; then out="ok, $(ago "$last")"; else out="${RED}FAILED${RESET}, $(ago "$last")"; fi
    if [ "$sync" = "0" ]; then
        out+=" · ${RED}B2 sync failed${RESET}"
    elif [ "$verify" = "1" ]; then
        out+=" · offsite ok"
    elif [ "$verify" = "0" ]; then
        out+=" · ${YELLOW}offsite stale${RESET}"
    fi
    echo "$out"
}

ups() {
    local status charge runtime out
    if ! command -v upsc >/dev/null 2>&1; then
        echo "unknown"
        return
    fi
    status=$(upsc "$1" ups.status 2>/dev/null)
    charge=$(upsc "$1" battery.charge 2>/dev/null)
    runtime=$(upsc "$1" battery.runtime 2>/dev/null)
    case "$status" in
        "") echo "unknown"; return ;;
        *OB*) out="${RED}on battery${RESET}" ;;
        *OL*) out="online" ;;
        *) out="$status" ;;
    esac
    [ -n "$charge" ] && out+=" · ${charge%.*}%"
    [ -n "$runtime" ] && out+=" · $((${runtime%.*} / 60)) min"
    echo "$out"
}

updates() {
    local file="$1/homelab_updates.prom" all sec reboot out
    all=$(metric "$file" homelab_updates_pending '{severity="all"}')
    sec=$(metric "$file" homelab_updates_pending '{severity="security"}')
    reboot=$(metric "$file" homelab_updates_reboot_required)
    if [ -z "$all" ]; then
        echo "unknown"
        return
    fi
    if [ "$all" = "0" ]; then out="up to date"; else out="$all pending"; fi
    [ -n "$sec" ] && [ "$sec" != "0" ] && out+=" (${YELLOW}$sec security${RESET})"
    [ "$reboot" = "1" ] && out+=" · ${YELLOW}reboot needed${RESET}"
    echo "$out"
}

case "${1:-}" in
    storage) storage ;;
    backup) backup "${2:?textfile dir}" ;;
    ups) ups "${2:?ups name}" ;;
    updates) updates "${2:?textfile dir}" ;;
    *) echo "usage: $0 storage | backup DIR | ups NAME | updates DIR" >&2; exit 2 ;;
esac
