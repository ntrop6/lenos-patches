#!/usr/bin/env bash
#
# Post-build artifact checks for an experimental lenOS build.
#
# This script is read-only. It does NOT build, flash, wipe, relock, reboot or
# change any device setting. It only checks that the expected APKs and
# framework artifacts exist in an output directory.
#
# Usage:
#   OUT=/path/to/out/target/product/asteroids tools/verify-build.sh
#
set -u

OUT="${OUT:-out/target/product/asteroids}"
fail=0

check_file() {
    local label="$1"
    local path="$2"
    if [ -f "$path" ]; then
        printf 'ok   %-28s %s\n' "$label" "$path"
    else
        printf 'MISS %-28s %s\n' "$label" "$path"
        fail=1
    fi
}

check_any() {
    local label="$1"
    shift
    local path
    for path in "$@"; do
        if [ -f "$path" ]; then
            printf 'ok   %-28s %s\n' "$label" "$path"
            return
        fi
    done
    printf 'MISS %-28s %s\n' "$label" "$*"
    fail=1
}

printf 'lenOS experimental post-build artifact check\n'
printf 'output: %s\n\n' "$OUT"

check_file "framework" "$OUT/system/framework/framework.jar"
check_file "Settings" "$OUT/system/priv-app/Settings/Settings.apk"
check_any "Seedvault" \
    "$OUT/system/app/Seedvault/Seedvault.apk" \
    "$OUT/system/priv-app/Seedvault/Seedvault.apk" \
    "$OUT/system_ext/app/Seedvault/Seedvault.apk" \
    "$OUT/system_ext/priv-app/Seedvault/Seedvault.apk"
check_any "LenosOpsec" \
    "$OUT/system/app/LenosOpsec/LenosOpsec.apk" \
    "$OUT/system/priv-app/LenosOpsec/LenosOpsec.apk" \
    "$OUT/system_ext/app/LenosOpsec/LenosOpsec.apk"
check_file "system image" "$OUT/system.img"
check_file "build.prop" "$OUT/system/build.prop"

if [ -f "$OUT/system/build.prop" ]; then
    printf '\nlenOS build properties:\n'
    grep -E '^(ro\.build\.type|ro\.build\.version\.release|ro\.lenos\.)' \
        "$OUT/system/build.prop" || true
fi

printf '\n'
if [ "$fail" -ne 0 ]; then
    printf 'FAIL: one or more expected artifacts are missing.\n' >&2
    exit 1
fi
printf 'PASS: all expected artifacts are present (build/boot still unverified).\n'
