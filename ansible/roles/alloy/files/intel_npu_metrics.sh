#!/usr/bin/env bash
#
# Intel NPU (intel_vpu driver, /dev/accel/accel*) -> Prometheus textfile, one write per interval.
# intel_gpu_top doesn't see the NPU, so this reads the driver's sysfs directly.
#
# Everything it touches:
#   reads   /sys/class/accel/accel*/device/{driver,npu_busy_time_us,npu_memory_utilization}
#           and the clock from freq/{current_freq,hw_max_freq,hw_min_freq,hw_efficient_freq} (kernel >= 7.2)
#           or npu_{current,max}_frequency_mhz (older)
#   writes  <output.prom>.<pid>, renamed to <output.prom>
#
# Usage: intel_npu_metrics.sh <interval_seconds> <output.prom>

set -uo pipefail

INTERVAL="${1:?interval seconds}"
OUT="${2:?output .prom path}"
ACCEL_GLOB="${ACCEL_GLOB:-/sys/class/accel/accel*/device}"

log() { echo "[$1] $2" >&2; }

read_num() {
    local v
    [ -r "$1" ] || return 0
    v="$(tr -d '[:space:]' <"$1" 2>/dev/null)" || return 0
    [[ "$v" =~ ^[0-9]+$ ]] && printf '%s' "$v"
}

sample() {
    local busy="" mem="" cur="" max="" min="" eff="" l_busy="" l_mem="" l_freq="" dev npu driver found=0
    for dev in $ACCEL_GLOB; do
        [ -d "$dev" ] || continue
        driver="$(basename "$(readlink -f "$dev/driver" 2>/dev/null)" 2>/dev/null)"
        [ "$driver" = "intel_vpu" ] || continue
        npu="$(basename "$(dirname "$dev")")"
        found=1
        busy="$(read_num "$dev/npu_busy_time_us")"
        mem="$(read_num "$dev/npu_memory_utilization")"
        cur="$(read_num "$dev/freq/current_freq")"
        [ -n "$cur" ] || cur="$(read_num "$dev/npu_current_frequency_mhz")"
        max="$(read_num "$dev/freq/hw_max_freq")"
        [ -n "$max" ] || max="$(read_num "$dev/npu_max_frequency_mhz")"
        min="$(read_num "$dev/freq/hw_min_freq")"
        eff="$(read_num "$dev/freq/hw_efficient_freq")"
        [ -n "$busy" ] && l_busy+="intel_npu_busy_seconds_total{npu=\"${npu}\"} $(awk -v u="$busy" 'BEGIN{printf "%.6f", u/1e6}')"$'\n'
        [ -n "$mem" ] && l_mem+="intel_npu_memory_bytes{npu=\"${npu}\"} ${mem}"$'\n'
        [ -n "$cur" ] && l_freq+="intel_npu_frequency_mhz{npu=\"${npu}\",type=\"current\"} ${cur}"$'\n'
        [ -n "$max" ] && l_freq+="intel_npu_frequency_mhz{npu=\"${npu}\",type=\"max\"} ${max}"$'\n'
        [ -n "$min" ] && l_freq+="intel_npu_frequency_mhz{npu=\"${npu}\",type=\"min\"} ${min}"$'\n'
        [ -n "$eff" ] && l_freq+="intel_npu_frequency_mhz{npu=\"${npu}\",type=\"efficient\"} ${eff}"$'\n'
    done

    local success=0
    if [ "$found" -eq 0 ]; then
        log ERROR "no intel_vpu device under ${ACCEL_GLOB}"
    elif [ -z "$busy" ]; then
        log ERROR "npu_busy_time_us is missing or unreadable (kernel too old, or permissions)"
    else
        success=1
    fi

    {
        echo "# HELP intel_npu_busy_seconds_total Time the NPU spent busy (rate() = utilisation, 0-1)"
        echo "# TYPE intel_npu_busy_seconds_total counter"
        printf '%s' "$l_busy"
        echo "# HELP intel_npu_memory_bytes Resident buffer objects allocated for the NPU"
        echo "# TYPE intel_npu_memory_bytes gauge"
        printf '%s' "$l_mem"
        echo "# HELP intel_npu_frequency_mhz NPU clock (current is 0 while idle)"
        echo "# TYPE intel_npu_frequency_mhz gauge"
        printf '%s' "$l_freq"
        echo "# HELP intel_npu_collector_success Whether the last sample read the NPU counters (1) or not (0)"
        echo "# TYPE intel_npu_collector_success gauge"
        echo "intel_npu_collector_success ${success}"
        echo "# HELP intel_npu_collector_last_sample_timestamp_seconds When this file was written"
        echo "# TYPE intel_npu_collector_last_sample_timestamp_seconds gauge"
        echo "intel_npu_collector_last_sample_timestamp_seconds $(date +%s)"
    } >"${OUT}.$$" || { log ERROR "cannot write ${OUT}.$$"; return; }
    chmod 0644 "${OUT}.$$"
    mv -f "${OUT}.$$" "$OUT" || log ERROR "cannot replace ${OUT}"
}

log INFO "sampling the NPU every ${INTERVAL}s -> ${OUT}"
while true; do
    sample
    sleep "$INTERVAL"
done
