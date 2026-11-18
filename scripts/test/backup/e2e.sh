#!/usr/bin/env bash
#
# End-to-end test of the nightly backup, from snapshot to restore.
#
# Renders the backup role's real scripts, runs them with real restic and rclone against a temp
# directory ("B2" is a plain local folder), then restores with the real restore_nova.yml and
# compares every restored file with its source (content, mode, size). systemctl, podman and
# mountpoint are stand-ins from shims/: nothing on the machine running the test is touched.
#
#   scripts/test/backup/e2e.sh            # needs restic, rclone, jq, flock, ansible-playbook
#   E2E_KEEP=1 scripts/test/backup/e2e.sh # keep the work directory for a look afterwards
#
# Exit 0 when every check passes. Each check prints one `ok` / `FAIL` line.

set -Eeuo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/backup-e2e.XXXXXX")
export E2E_WORK="$WORK"

PASS=0
FAIL=0
AS_ROOT=()
MOUNTED=0

cleanup() {
    local log
    if [ "$FAIL" -gt 0 ] && [ "${GITHUB_ACTIONS:-}" = "true" ]; then
        for log in "$WORK"/*.log "$WORK"/diff.txt; do
            [ -f "$log" ] || continue
            echo "::group::$(basename "$log")"
            tail -n 120 "$log"
            echo "::endgroup::"
        done
    fi
    [ "$MOUNTED" -eq 1 ] && "${AS_ROOT[@]}" umount "$WORK/mnt"
    if [ "${E2E_KEEP:-0}" = "1" ] || [ "$FAIL" -gt 0 ]; then
        echo "# work directory kept: $WORK"
    else
        "${AS_ROOT[@]}" rm -rf "$WORK"
    fi
}
trap cleanup EXIT

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
ok()   { PASS=$((PASS + 1)); echo "ok   $*"; }
bad()  { FAIL=$((FAIL + 1)); echo "FAIL $*"; }
check() { local what="$1"; shift; if "$@"; then ok "$what"; else bad "$what"; fi; }
section() { echo; echo "# $*"; }

# metric NAME [FILE]: the value of an unlabelled metric in a .prom file.
metric() {
    awk -v m="$1" '$1 == m { print $2 }' "${2:-$WORK/metrics/homelab_backup.prom}"
}

# Runs ansible-playbook from the work directory (no repo ansible.cfg: no vault, no inventory).
playbook() {
    (cd "$WORK" && ANSIBLE_ROLES_PATH="$ROOT/ansible/roles" ANSIBLE_STDOUT_CALLBACK=default \
        ANSIBLE_LOCALHOST_WARNING=false ANSIBLE_INVENTORY_UNPARSED_WARNING=false \
        ansible-playbook -i "$WORK/inventory" -e "work=$WORK" -e "@$HERE/vars.yml" "$@")
}

render() {
    playbook "$HERE/render.yml" "$@" > "$WORK/render.log" 2>&1 \
        || { cat "$WORK/render.log"; echo "render failed"; exit 1; }
}

# backup LOG: one nightly run; its exit code is left in RC.
backup() {
    RC=0
    "$WORK/bin/homelab-backup.sh" > "$WORK/$1" 2>&1 || RC=$?
}

verify() {
    RC=0
    "$WORK/bin/homelab-verify-backup.sh" > "$WORK/$1" 2>&1 || RC=$?
}

snapshots() { restic -r "$WORK/repo" snapshots --json 2>/dev/null | jq length; }

# restore_and_compare REPO TARGETS PATH...: make restore_nova (TARGETS empty = all), then compare
# what came back with the source PATHs; every other target path must not have come back.
restore_and_compare() {
    local repo="$1" targets="$2" before dest label p
    shift 2
    label="restore ${targets:-all} from $repo"
    sleep 1 # restore folders are named by the second
    before=$("${AS_ROOT[@]}" find "$WORK/mnt/restore" -mindepth 1 -maxdepth 1 | wc -l)
    if [ "${#AS_ROOT[@]}" -eq 0 ]; then
        echo "skip $label (restore_nova needs root: run as root or with passwordless sudo)"
        return
    fi
    playbook "$ROOT/ansible/playbooks/restore_nova.yml" -e "ansible_become=$BECOME" \
        -e "restore_repo=$repo" -e "restore_targets=$targets" > "$WORK/restore-$repo.log" 2>&1 \
        || { bad "$label ran (see restore-$repo.log)"; return; }
    ok "$label ran"
    check "$label made one new folder" \
        test "$("${AS_ROOT[@]}" find "$WORK/mnt/restore" -mindepth 1 -maxdepth 1 | wc -l)" -eq $((before + 1))
    dest=$("${AS_ROOT[@]}" find "$WORK/mnt/restore" -mindepth 1 -maxdepth 1 | sort | tail -n 1)
    python3 "$HERE/tree_digest.py" "${EXCLUDES[@]}" "$@" > "$WORK/expected.txt"
    "${AS_ROOT[@]}" python3 "$HERE/tree_digest.py" --root "$dest" "${EXCLUDES[@]}" "$@" > "$WORK/restored.txt"
    if diff -u "$WORK/expected.txt" "$WORK/restored.txt" > "$WORK/diff.txt"; then
        ok "$label: every file identical to its source (content, size, mode)"
    else
        bad "$label differs from the source (diff.txt)"
        head -20 "$WORK/diff.txt"
    fi
    for p in "${PATHS[@]}"; do
        case " $* " in *" $p "*) continue ;; esac
        check "$label: $(basename "$p") (not asked for) is absent" "${AS_ROOT[@]}" test ! -e "$dest$p"
    done
    for p in "${EXCLUDED_SAMPLES[@]}"; do
        case "$p" in "$D/homeassistant/"*) [[ " $* " == *" $D/homeassistant "* ]] || continue ;;
                     "$D/vaultwarden/"*) [[ " $* " == *" $D/vaultwarden "* ]] || continue ;; esac
        check "$label: excluded ${p#"$D"/} is absent" "${AS_ROOT[@]}" test ! -e "$dest$p"
    done
    check "$label: RESTORE-INFO.txt written" "${AS_ROOT[@]}" test -s "$dest/RESTORE-INFO.txt"
}

# ------------------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------------------
# The restore runs as root (as on Nova: restore_nova.yml keeps owners and makes the folder root-only).
# Root: directly. Otherwise passwordless sudo, or the restore steps are skipped.
if [ "$(id -u)" -eq 0 ]; then
    AS_ROOT=(env)
    BECOME=false
elif sudo -n true 2>/dev/null; then
    AS_ROOT=(sudo -n)
    BECOME=true
else
    AS_ROOT=()
    BECOME=false
fi

for tool in restic rclone jq flock python3 ansible-playbook; do
    command -v "$tool" > /dev/null || { echo "missing: $tool"; exit 2; }
done
echo "# restic $(restic version | awk '{print $2}'), rclone $(rclone version | awk 'NR==1 {print $2}')"
echo "# work: $WORK"

mkdir -p "$WORK"/{bin,run,metrics,backups,config,mnt/restore,b2,devices}
cp "$HERE"/shims/* "$WORK/bin/"
chmod +x "$WORK"/bin/*
export PATH="$WORK/bin:$PATH"
export XDG_RUNTIME_DIR="$WORK/run"

if [ "${#AS_ROOT[@]}" -gt 0 ] && "${AS_ROOT[@]}" mount --bind "$WORK/mnt" "$WORK/mnt" 2>/dev/null; then
    MOUNTED=1
fi
printf 'localhost ansible_connection=local ansible_python_interpreter=%s\nnova ansible_connection=local ansible_python_interpreter=%s\n' \
    "$(command -v python3)" "$(command -v python3)" > "$WORK/inventory"

# Data: the shapes a real backup meets (nested dirs, spaces, unicode, a symlink, an empty dir,
# modes, a binary file, files that must be excluded).
D="$WORK/data"
mkdir -p "$D/homeassistant/.storage" "$D/homeassistant/.cache" "$D/vaultwarden/icon_cache" \
    "$D/vaultwarden/attachments/empty dir" "$D/immich/library/2026/11" "$D/immich/backups" "$D/git/nova.git"
echo '{"version": 1}' > "$D/homeassistant/.storage/core.config_entries"
echo "automation: !include automations.yaml" > "$D/homeassistant/configuration.yaml"
echo "log line" > "$D/homeassistant/home-assistant.log"
echo "old log" > "$D/homeassistant/home-assistant.log.1"
echo "cache" > "$D/homeassistant/.cache/blob"
head -c 300000 /dev/urandom > "$D/vaultwarden/db.sqlite3"
chmod 600 "$D/vaultwarden/db.sqlite3"
echo "icon" > "$D/vaultwarden/icon_cache/x.png"
echo "attachment" > "$D/vaultwarden/attachments/file with spaces.txt"
head -c 2000000 /dev/urandom > "$D/immich/library/2026/11/IMG_0001.jpg"
echo "zdjęcie" > "$D/immich/library/2026/11/żółw ąę.txt"
ln -s IMG_0001.jpg "$D/immich/library/2026/11/latest.jpg"
echo "SELECT 1;" | gzip > "$D/immich/backups/immich-db-backup-1.sql.gz"
echo "ref: refs/heads/main" > "$D/git/nova.git/HEAD"
chmod 750 "$D/git/nova.git"

PATHS=("$D/homeassistant" "$D/vaultwarden" "$D/immich/library" "$D/immich/backups" "$D/git")
EXCLUDES=(--exclude "$D/homeassistant/home-assistant.log*" --exclude "$D/homeassistant/.cache"
    --exclude "$D/vaultwarden/icon_cache")
EXCLUDED_SAMPLES=("$D/homeassistant/home-assistant.log" "$D/homeassistant/home-assistant.log.1"
    "$D/homeassistant/.cache/blob" "$D/vaultwarden/icon_cache/x.png")

# Same password restore_nova.yml writes from vault_backup_restic_password (vars.yml).
echo "e2e-not-a-secret" > "$WORK/restic.pass"
chmod 600 "$WORK/restic.pass"
export RESTIC_PASSWORD_FILE="$WORK/restic.pass"
restic init -q -r "$WORK/repo"
mkdir -p "$WORK/devices/alice/cloud" "$WORK/devices/alice/local"
restic init -q -r "$WORK/devices/alice/cloud/pc"
restic init -q -r "$WORK/devices/alice/local/pc"

render

# ------------------------------------------------------------------------------
section "1. A normal night"
# ------------------------------------------------------------------------------
backup run1.log
check "backup exits 0" test "$RC" -eq 0
check "metric homelab_backup_success = 1" test "$(metric homelab_backup_success)" = 1
check "metric homelab_backup_cloud_sync_success = 1" test "$(metric homelab_backup_cloud_sync_success)" = 1
check "metric homelab_backup_services_down = 0" test "$(metric homelab_backup_services_down)" = 0
check "one snapshot in the local repository" test "$(snapshots)" -eq 1
check "B2 holds the same repository (config byte-equal)" cmp -s "$WORK/repo/config" "$WORK/b2/homelab/config"
check "B2 holds the cloud-tier device repo" test -f "$WORK/b2/devices/alice/cloud/pc/config"
check "B2 does not hold the local-tier device repo" test ! -e "$WORK/b2/devices/alice/local"
check "the snapshot contains canary.txt" bash -c "restic -r '$WORK/repo' ls latest | grep -qx '$WORK/backups/canary.txt'"
check "the snapshot contains versions.txt" bash -c "restic -r '$WORK/repo' ls latest | grep -qx '$WORK/backups/versions.txt'"
check "the snapshot leaves out the excludes" bash -c "! restic -r '$WORK/repo' ls latest | grep -qE 'home-assistant.log|/.cache|icon_cache'"
check "the canary in the snapshot is this run's start time" \
    test "$(restic -r "$WORK/repo" dump latest "$WORK/backups/canary.txt")" = "$(cat "$WORK/backups/canary.txt")"

# Both stop: true services stopped before the snapshot and started after it.
SNAP_TIME=$(restic -r "$WORK/repo" snapshots --json latest | jq -r '.[0].time' | xargs -I{} date -d {} +%s.%N)
LAST_STOP=$(awk '/ stop /{t=$1} END{print t}' "$WORK/systemctl.log")
FIRST_START=$(awk '/ start /{print $1; exit}' "$WORK/systemctl.log")
check "homeassistant and vaultwarden were stopped" \
    bash -c "grep -q 'stop homeassistant.service' '$WORK/systemctl.log' && grep -q 'stop vaultwarden.service' '$WORK/systemctl.log'"
check "both were started again" \
    bash -c "grep -q 'start homeassistant.service' '$WORK/systemctl.log' && grep -q 'start vaultwarden.service' '$WORK/systemctl.log'"
check "the snapshot was taken after the last stop and before the first start" \
    python3 -c "import sys; s,a,b=map(float,sys.argv[1:]); sys.exit(0 if a < s < b else 1)" "$SNAP_TIME" "$LAST_STOP" "$FIRST_START"

verify verify1.log
check "verify exits 0 (canary read back from B2, fresh)" test "$RC" -eq 0
check "metric homelab_backup_verify_success = 1" \
    test "$(metric homelab_backup_verify_success "$WORK/metrics/homelab_backup_verify.prom")" = 1

restore_and_compare local "" "${PATHS[@]}"
restore_and_compare b2 "" "${PATHS[@]}"

# ------------------------------------------------------------------------------
section "2. A second night with changes"
# ------------------------------------------------------------------------------
echo "changed" >> "$D/homeassistant/configuration.yaml"
head -c 500000 /dev/urandom > "$D/immich/library/2026/11/IMG_0002.jpg"
rm "$D/vaultwarden/attachments/file with spaces.txt"
sleep 1
backup run2.log
check "backup exits 0" test "$RC" -eq 0
check "B2 identity guard passed (no 'DIFFERENT repository')" bash -c "! grep -q DIFFERENT '$WORK/run2.log'"
check "B2 copy has the same snapshots as the local repo" \
    test "$(restic -r "rclone:$WORK/b2/homelab" snapshots --json 2>/dev/null | jq length)" -eq "$(snapshots)"
restore_and_compare b2 "" "${PATHS[@]}"
restore_and_compare local "vaultwarden" "$D/vaultwarden"
restore_and_compare b2 "immich,restic" "$D/immich/library" "$D/immich/backups" "$D/git"

# ------------------------------------------------------------------------------
section "3. A service refuses to stop"
# ------------------------------------------------------------------------------
: > "$WORK/systemctl.log"
COUNT=$(snapshots)
E2E_FAIL_STOP=vaultwarden.service backup run3.log
check "backup exits non-zero" test "$RC" -ne 0
check "metric homelab_backup_success = 0" test "$(metric homelab_backup_success)" = 0
check "no snapshot was taken with a service still running" test "$(snapshots)" -eq "$COUNT"
check "homeassistant (already stopped) was started again" grep -q 'start homeassistant.service' "$WORK/systemctl.log"
check "metric homelab_backup_services_down = 0" test "$(metric homelab_backup_services_down)" = 0

# ------------------------------------------------------------------------------
section "4. A service that was already stopped stays stopped"
# ------------------------------------------------------------------------------
: > "$WORK/systemctl.log"
E2E_INACTIVE=vaultwarden.service backup run4.log
check "backup exits 0" test "$RC" -eq 0
check "vaultwarden was neither stopped nor started" bash -c "! grep -qE '(stop|start) vaultwarden.service' '$WORK/systemctl.log'"

# ------------------------------------------------------------------------------
section "5. B2 holds a different repository"
# ------------------------------------------------------------------------------
mv "$WORK/b2/homelab" "$WORK/b2/homelab.real"
restic init -q -r "$WORK/b2/homelab"
cp -r "$WORK/b2/homelab" "$WORK/b2-other.before"
backup run5.log
check "backup exits non-zero" test "$RC" -ne 0
check "metric homelab_backup_b2_repo_mismatch = 1" test "$(metric homelab_backup_b2_repo_mismatch)" = 1
check "the other repository on B2 was not touched" diff -r -q "$WORK/b2-other.before" "$WORK/b2/homelab"
rm -rf "$WORK/b2/homelab" "$WORK/b2-other.before"
mv "$WORK/b2/homelab.real" "$WORK/b2/homelab"

# ------------------------------------------------------------------------------
section "6. Over the B2 quota"
# ------------------------------------------------------------------------------
render -e backup_b2_quota_bytes=1000
backup run6.log
check "backup exits non-zero" test "$RC" -ne 0
check "metric homelab_backup_quota_exceeded = 1" test "$(metric homelab_backup_quota_exceeded)" = 1
check "the local snapshot was still taken" grep -q "snapshot .* saved" "$WORK/run6.log"
check "nothing was synced" bash -c "! grep -q 'Syncing external device' '$WORK/run6.log'"
render

# ------------------------------------------------------------------------------
section "7. An unreadable file"
# ------------------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
    echo "skip (running as root: every file is readable)"
else
    echo "secret" > "$D/vaultwarden/unreadable"
    chmod 000 "$D/vaultwarden/unreadable"
    backup run7.log
    check "backup exits 0 (snapshot saved, file skipped)" test "$RC" -eq 0
    check "metric homelab_backup_incomplete = 1" test "$(metric homelab_backup_incomplete)" = 1
    rm -f "$D/vaultwarden/unreadable"
fi

# ------------------------------------------------------------------------------
section "8. Verify notices a stale offsite copy"
# ------------------------------------------------------------------------------
render -e backup_canary_max_age=1
sleep 2
verify verify8.log
check "verify exits non-zero" test "$RC" -ne 0
check "metric homelab_backup_verify_success = 0" \
    test "$(metric homelab_backup_verify_success "$WORK/metrics/homelab_backup_verify.prom")" = 0
render

# ------------------------------------------------------------------------------
section "9. A second run while one holds the lock"
# ------------------------------------------------------------------------------
exec 8> "$WORK/run/homelab-backup.lock"
flock -n 8
backup run9.log
check "exits 0 without doing anything" bash -c "[ $RC -eq 0 ] && grep -q 'holds the lock' '$WORK/run9.log'"
exec 8>&-

# ------------------------------------------------------------------------------
echo
echo "# $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
