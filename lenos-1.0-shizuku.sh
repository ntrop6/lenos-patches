#!/usr/bin/env bash
# lenOS 1.0.0-shizuku — product driver for Nothing Phone (3a) `asteroids`.
#
# This is the 1.0 entry point. It does not reimplement Soong/repo/signing.
# The 2.8.1 wizard remains the compiler. This script:
#   - never repo syncs
#   - applies patches only through vendor/lenos/tools/lenos-patch.py (strict
#     `git apply`, no fuzz; refuses to patch a project that is not pristine)
#   - never flashes the phone
#   - never locks
#   - never re-signs firmware (abl/xbl/bluetooth VBMeta magic)
#   - packages --rootless only (prepatched does not boot this unit)
#
# Subcommands: doctor | apply | build | package | extract | flash-plan | lock-gates
# (`hardwire` is kept as an alias of `apply` for the older scripts/manuals)
set -euo pipefail
umask 077

readonly LENOS_VERSION="1.0.0-shizuku"
readonly CODENAME="shizuku"

err()  { printf '[lenOS %s] ERROR: %s\n' "$LENOS_VERSION" "$*" >&2; }
die()  { err "$*"; exit 1; }
info() { printf '[lenOS %s] %s\n' "$LENOS_VERSION" "$*" >&2; }

SELF_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
WS="${LENOS_WORKSPACE:-$HOME/lenos-workspace}"
SRC="${LENOS_SOURCE:-$WS/lineage}"
KEYS="${LENOS_KEYDIR:-$HOME/secure-keys/asteroids}"
AVBROOT="${AVBROOT:-$WS/tools/avbroot}"
WIZARD="${LENOS_WIZARD:-$HOME/lenOS-2.8.1-ReSukiSU-single.sh}"
VENDOR="${LENOS_VENDOR:-}"
if [[ -z "$VENDOR" ]]; then
  if [[ -d "$SELF_DIR/vendor-lenos" ]]; then VENDOR="$SELF_DIR/vendor-lenos"
  elif [[ -d "$HOME/vendor-lenos" ]]; then VENDOR="$HOME/vendor-lenos"
  else VENDOR="$SELF_DIR/vendor-lenos"
  fi
fi
OUT="$WS/lenos-asteroids-rootless.zip"
EXTRACT_DIR="$WS/extracted-rootless"

# Qualcomm firmware / bootloader images. avbroot --re-sign of these aborts
# with "Invalid VBMeta header magic" (bluetooth/abl/xbl). OS AVB only.
readonly -a FIRMWARE_DENY=(
  abl aop aop_config bluetooth cpucp cpucp_dtb devcfg dsp featenabler
  hyp imagefv keymaster modem multiimgoem multiimgqti qupfw shrm soccp
  tz uefi uefisecapp vm-bootsys xbl xbl_config xbl_ramdump
  xbl_sc xbl_ramdump_config
)

usage() {
  cat <<EOF
lenOS $LENOS_VERSION  (asteroids / Nothing Phone 3a)

  $0 doctor         VM / keys / wizard / avbroot / patchkit
  $0 apply          reset-hardening, install vendor/lenos, apply the patch series
  $0 build          apply + 8–17h  mka  --rootless --hardening full
  $0 package        avbroot OTA, OS images only, --rootless --clear-vbmeta-flags
  $0 extract        avbroot ota extract --fastboot --all + sanitize flash plan
  $0 flash-plan     print laptop commands. does not talk to the phone
  $0 lock-gates     print lock checklist. always exits 1 (this script will not lock)

Never: repo sync, git apply, flash, lock, firmware --re-sign, prepatched.
EOF
}

need_file() { [[ -s "$1" ]] || die "missing $1"; }
need_exec() { [[ -x "$1" ]] || die "missing executable $1"; }

is_firmware() {
  local p="$1" x
  p="${p##*/}"
  p="${p%%.*}"
  p="${p%_a}"; p="${p%_b}"
  for x in "${FIRMWARE_DENY[@]}"; do
    [[ "$p" == "$x" ]] && return 0
  done
  return 1
}

cmd_doctor() {
  info "doctor"
  [[ "$(uname -s)" == Linux ]] || die "Linux host only"
  need_exec "$WIZARD"
  need_exec "$AVBROOT"
  info "wizard:  $WIZARD"
  info "avbroot: $($AVBROOT --version 2>/dev/null || echo unknown)"
  [[ -f "$SRC/device/nothing/asteroids/lineage_asteroids.mk" ]] \
    || die "not an asteroids tree: $SRC"
  [[ -d "$VENDOR" && -f "$VENDOR/tools/lenos-patch.py" \
     && -f "$VENDOR/tools/lenos_projects.py" ]] \
    || die "vendor/lenos patchkit not next to this script and not at $VENDOR"
  need_file "$KEYS/avb.key"
  need_file "$KEYS/ota.key"
  need_file "$KEYS/ota.crt"
  need_file "$KEYS/avb_pkmd.bin"
  command -v python3 >/dev/null || die "python3 required"
  command -v git >/dev/null || die "git required"
  command -v sha256sum >/dev/null || die "sha256sum required"
  info "tree:    $SRC"
  info "keys:    $KEYS"
  info "vendor:  $VENDOR"
  info "OK. do not repo sync. do not lock."
}

# Projects touched by the patch series (unique), read from the patchkit.
series_projects() {
  python3 "$VENDOR/tools/lenos-patch.py" --list | cut -f1 | sort -u
}

# Refuse to patch a project that still has tracked modifications: the
# patchkit assumes pinned sources, and a stale change from an older pipeline
# could otherwise survive next to a patch that applies cleanly.
require_pristine() {
  local projects proj changes dirty=0
  projects="$(series_projects)" || die "cannot list the patch series projects"
  [[ -n "$projects" ]] || die "patch series is empty - refusing to patch"
  while IFS= read -r proj; do
    [[ -n "$proj" ]] || continue
    if [[ -d "$SRC/$proj/.git" || -f "$SRC/$proj/.git" ]]; then
      changes="$(git -C "$SRC/$proj" status --porcelain --untracked-files=no)"
      if [[ -n "$changes" ]]; then
        err "project not pristine: $proj"
        printf '%s\n' "$changes" | sed 's/^/    /' >&2
        dirty=1
      fi
    else
      die "no git checkout at $SRC/$proj (fix with repo sync only, then re-pin)"
    fi
  done <<< "$projects"
  if [[ "$dirty" -ne 0 ]]; then
    die "tree is not pinned. reset first: '$WIZARD reset hardening', then
    'git -C \$SRC/<project> checkout -- .' for anything still listed"
  fi
}

# Build inputs only (config/, app/, rro/). The patchkit, tests and docs stay
# in $VENDOR outside the tree; nothing else is compiled.
install_vendor_lenos() {
  local part
  info "install vendor/lenos build inputs -> $SRC/vendor/lenos"
  rm -rf "$SRC/vendor/lenos"
  mkdir -p "$SRC/vendor/lenos"
  for part in config app rro; do
    cp -a "$VENDOR/$part" "$SRC/vendor/lenos/"
  done
  need_file "$SRC/vendor/lenos/config/lenos.mk"
  need_file "$SRC/vendor/lenos/config/privapp-permissions-org.lenos.security.xml"
}

cmd_apply() {
  cmd_doctor
  export LENOS_ALLOW_LOW_MEMORY="${LENOS_ALLOW_LOW_MEMORY:-1}"
  export LENOS_BUILD_JOBS="${LENOS_BUILD_JOBS:-4}"
  info "wizard reset hardening (git reset of patched projects)"
  "$WIZARD" reset hardening

  info "patchkit --reset (pinned state; also removes files the series created)"
  python3 "$VENDOR/tools/lenos-patch.py" --tree "$SRC" --reset \
    || die "patchkit --reset failed"
  require_pristine
  install_vendor_lenos

  info "patchkit --check (strict, must pass before anything is written)"
  python3 "$VENDOR/tools/lenos-patch.py" --tree "$SRC" --check \
    || die "patchkit --check failed: tree does not match the pinned revisions"

  info "patchkit --apply"
  python3 "$VENDOR/tools/lenos-patch.py" --tree "$SRC" --apply \
    || die "patchkit --apply failed"

  local status
  status="$(python3 "$VENDOR/tools/lenos-patch.py" --tree "$SRC" --status)"
  printf '%s\n' "$status" >&2
  if grep -q 'missing' <<< "$status"; then
    die "patches missing after apply. do not build a half-patched tree."
  fi

  # Markers of this series, independent of the patchkit's own reporting.
  grep -q '>dns.quad9.net<' \
    "$SRC/vendor/lenos/rro/LenosSettingsProviderOverlay/res/values/defaults.xml" \
    || die "Quad9 DoT default missing from the settings RRO"
  grep -q 'def_lenos_private_dns_specifier' \
    "$SRC/frameworks/base/packages/SettingsProvider/res/values/defaults.xml" \
    || die "first-boot default resources missing from SettingsProvider"
  grep -q 'ro.lenos.version' "$SRC/vendor/lenos/config/lenos.mk" \
    || die "lenOS version prop missing from config/lenos.mk"
  grep -q 'SendDhcpHostname2' \
    "$SRC/packages/modules/Wifi/service/java/com/android/server/wifi/util/XmlUtil.java" \
    || die "Wi-Fi DHCP-hostname privacy default missing from the Wi-Fi module"
  grep -q 'RANDOMIZATION_ALWAYS' \
    "$SRC/packages/modules/Wifi/framework/java/android/net/wifi/WifiConfiguration.java" \
    || die "Wi-Fi MAC randomization default missing from the Wi-Fi module"
  grep -q 'setupPinScrambling' \
    "$SRC/frameworks/base/packages/SystemUI/src/com/android/keyguard/KeyguardPinBasedInputView.java" \
    || die "keyguard PIN scrambling missing from SystemUI"
  grep -q 'scramble_pin_layout' \
    "$SRC/packages/apps/Settings/src/com/android/settings/security/screenlock/PinScramblingPrefController.java" \
    || die "keyguard PIN scrambling UI missing from Settings"
  grep -q 'MAX_FAILED_ATTEMPTS_LOCKOUT_PERMANENT = 5' \
    "$SRC/frameworks/base/services/core/java/com/android/server/biometrics/sensors/fingerprint/hidl/LockoutFrameworkImpl.java" \
    || die "fingerprint permanent-lockout hardening missing"
  grep -q 'MAX_PASSWORD_LENGTH = 128' \
    "$SRC/frameworks/base/core/java/android/app/admin/DevicePolicyManager.java" \
    || die "password-length hardening missing"
  grep -q 'SYSTEM_CLOCK_PARANOIA_THRESHOLD_MILLIS = 250' \
    "$SRC/frameworks/base/services/core/java/com/android/server/timedetector/TimeDetectorStrategyImpl.java" \
    || die "clock-drift warning hardening missing"
  grep -q 'checkPendingIntent2' \
    "$SRC/frameworks/base/core/java/android/app/PendingIntent.java" \
    || die "PendingIntent immutability warp missing"
  grep -q 'def_lock_screen_allow_private_notifications">false<' \
    "$SRC/frameworks/base/packages/SettingsProvider/res/values/defaults.xml" \
    || die "lockscreen notification-content privacy default missing"
  grep -q 'config_multiuserMaximumUsers">32<' \
    "$SRC/device/nothing/asteroids/rro_overlays/FrameworksResCommon_Vendor/res/values/config.xml" \
    || die "multiuser limit hardening missing"
  grep -q 'ExtSettings.SCREENSHOT_TIMESTAMP_EXIF.get(resolver.getContext())' \
    "$SRC/frameworks/base/packages/SystemUI/src/com/android/systemui/screenshot/ImageExporter.java" \
    || die "screenshot EXIF privacy gate missing from SystemUI"
  grep -q 'privacy_screenshot_timestamp_exif' \
    "$SRC/packages/apps/Settings/res/xml/more_security_privacy_settings.xml" \
    || die "screenshot EXIF setting row missing from Settings"
  for ca in 53a1b57a.0 60afe812.0 9d6523ce.0; do
    [[ ! -e "$SRC/system/ca-certificates/files/$ca" ]] \
      || die "distrusted CA $ca is still shipped"
  done
  grep -q 'options->flags |= FSCRYPT_POLICY_FLAGS_PAD_32;' \
    "$SRC/system/extras/libfscrypt/fscrypt.cpp" \
    || die "FBE filename padding not hardened"
  grep -q 'KEY_ENABLE_CMAS_PRESIDENTIAL_ALERTS, true' \
    "$SRC/packages/apps/CellBroadcastReceiver/src/com/android/cellbroadcastreceiver/CellBroadcastAlertService.java" \
    || die "wireless alerts not made optional"
  grep -q 'show_presidential_alerts_settings">true<' \
    "$SRC/packages/apps/CellBroadcastReceiver/res/values/config.xml" \
    || die "presidential alert settings row not enabled"
  grep -q 'public static boolean isAllowButton' \
    "$SRC/packages/modules/Permission/PermissionController/src/com/android/permissioncontroller/permission/ui/GrantPermissionsActivity.java" \
    || die "permission dialog Allow buttons not delayed"
  grep -q 'accidental Allow button tap' \
    "$SRC/frameworks/base/packages/SystemUI/src/com/android/systemui/usb/UsbDebuggingActivity.java" \
    || die "USB debugging Allow button not delayed"
  info "apply OK - tree carries the lenOS patch series"
}

cmd_build() {
  cmd_apply
  export LENOS_ALLOW_LOW_MEMORY="${LENOS_ALLOW_LOW_MEMORY:-1}"
  export LENOS_BUILD_JOBS="${LENOS_BUILD_JOBS:-4}"
  info "wizard reset build (clears out/, not the tree)"
  "$WIZARD" reset build
  info "compile --rootless --hardening full  (8–17h, tmux this)"
  "$WIZARD" build --rootless --hardening full
  info "compile finished. next: $0 package"
}

collect_os_resign() {
  python3 - "$WS" "$KEYS" <<'PY'
import glob, json, os, sys
ws = sys.argv[1]
deny = {
    "abl","aop","aop_config","bluetooth","cpucp","cpucp_dtb","devcfg","dsp",
    "featenabler","hyp","imagefv","keymaster","modem","multiimgoem","multiimgqti",
    "qupfw","shrm","soccp","tz","uefi","uefisecapp","vm-bootsys","xbl",
    "xbl_config","xbl_ramdump","xbl_sc","xbl_ramdump_config",
}
parts = []
plan = os.path.join(ws, "signing-plan.json")
if os.path.isfile(plan) and os.path.getsize(plan) > 0:
    try:
        data = json.load(open(plan, encoding="utf-8"))
        parts = list(data.get("resign_partitions") or [])
    except Exception:
        parts = []
if not parts:
    helpers = glob.glob(os.path.expanduser("~/.cache/lenos-single/*/tools/signing_metadata.py"))
    helpers += glob.glob(os.path.expanduser("~/.cache/lenos-single/*/runtime/tools/signing_metadata.py"))
    helpers += [os.path.join(ws, "tools/signing_metadata.py")]
    helper = next((h for h in helpers if os.path.isfile(h)), None)
    if helper and os.path.isfile(plan):
        import subprocess
        r = subprocess.run(["python3", helper, "emit", plan, "resign-partitions"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            parts = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
# Do NOT slurp avbroot_patch.log (tr/mapfile of the whole file kills SSH).
seen, out = set(), []
dropped = []
for p in parts:
    name = p.split("/")[-1].split(".")[0]
    name = name[:-2] if name.endswith("_a") or name.endswith("_b") else name
    if name in deny:
        dropped.append(p)
        continue
    if p and p not in seen and p != "--re-sign":
        seen.add(p)
        out.append(p)
if dropped:
    print("dropped firmware (do not --re-sign): " + " ".join(dropped), file=sys.stderr)
if not out:
    sys.exit(1)
print("\n".join(out))
PY
}

cmd_package() {
  cmd_doctor
  local input=""
  for c in "$WS/base-signed-ota.zip" "$WS/out/target/product/asteroids"/*.zip; do
    [[ -s "$c" ]] || continue
    input="$c"
  done
  # Prefer the unsigned/test-key OTA the wizard just produced.
  if [[ -s "$WS/base-signed-ota.zip" ]]; then
    input="$WS/base-signed-ota.zip"
  fi
  [[ -s "$input" ]] || die "no input OTA. expected $WS/base-signed-ota.zip after build"
  info "input OTA: $input"

  mapfile -t PARTS < <(collect_os_resign) \
    || die "no OS --re-sign list (need signing-plan.json or signing_metadata.py). do not parse the whole avbroot log."
  info "OS re-sign (${#PARTS[@]}): ${PARTS[*]}"

  local args=()
  local p
  for p in "${PARTS[@]}"; do
    args+=(--re-sign "$p")
  done

  rm -f "$OUT.tmp"
  "$AVBROOT" ota patch \
    --input "$input" \
    --key-avb "$KEYS/avb.key" \
    --key-ota "$KEYS/ota.key" \
    --cert-ota "$KEYS/ota.crt" \
    --clear-vbmeta-flags \
    --rootless \
    --zip-mode seekable \
    --output "$OUT.tmp" \
    "${args[@]}"

  mv -f "$OUT.tmp" "$OUT"
  chmod 644 "$OUT"
  "$AVBROOT" ota verify \
    --input "$OUT" \
    --cert-ota "$KEYS/ota.crt" \
    --public-key-avb "$KEYS/avb_pkmd.bin"
  sha256sum "$OUT" | tee "$OUT.sha256"
  info "packaged $OUT"
  info "next: $0 extract   then copy zip + sha256 + avb_pkmd.bin off this VM"
}

sanitize_fastboot_info() {
  python3 - "$1" <<'PY'
"""Reorder avbroot fastboot-info.txt so vbmeta cannot land before logicals.
Never invents android-info.txt. Comments firmware lines if avbroot left them live.
"""
from pathlib import Path
import sys
p = Path(sys.argv[1])
lines = p.read_text(encoding="utf-8", errors="replace").splitlines(True)
firmware = (
    "abl","aop","bluetooth","cpucp","devcfg","dsp","featenabler","hyp","imagefv",
    "keymaster","modem","qupfw","shrm","tz","uefi","uefisecapp","xbl",
    "xbl_config","xbl_ramdump",
)
logical = ("system","system_ext","product","vendor","vendor_dlkm","system_dlkm","odm","odm_dlkm")
vbmeta = ("vbmeta","vbmeta_system","vbmeta_vendor")

def kind(line: str) -> str:
    s = line.strip()
    if s.startswith("#") or not s:
        return "c"
    parts = s.split()
    if not parts:
        return "c"
    if parts[0] == "reboot" and "fastboot" in parts:
        return "reboot-fastboot"
    if parts[0] in {"flash", "update-super", "wipe", "format", "erase"}:
        name = parts[1] if len(parts) > 1 else ""
        name = name.split(":")[-1]
        base = name[:-2] if name.endswith("_a") or name.endswith("_b") else name
        if base in firmware:
            return "firmware"
        if base in logical or parts[0] == "update-super":
            return "logical"
        if base in vbmeta:
            return "vbmeta"
        return "physical"
    return "other"

out, pending_vbmeta, saw_reboot, saw_logical = [], [], False, False
for line in lines:
    k = kind(line)
    if k == "firmware":
        if not line.lstrip().startswith("#"):
            out.append("# lenOS: firmware not flashed from this OTA (no VBMeta magic)\n# " + line)
        else:
            out.append(line)
        continue
    if k == "vbmeta" and not saw_logical:
        pending_vbmeta.append(line)
        continue
    if k == "reboot-fastboot":
        saw_reboot = True
    if k == "logical":
        saw_logical = True
    out.append(line)
    if saw_logical and pending_vbmeta:
        out.extend(pending_vbmeta)
        pending_vbmeta = []
if pending_vbmeta:
    out.extend(pending_vbmeta)
p.write_text("".join(out), encoding="utf-8")
print(f"sanitized {p} reboot_fastboot={saw_reboot} logicals={saw_logical}")
PY
}

cmd_extract() {
  cmd_doctor
  need_file "$OUT"
  rm -rf "$EXTRACT_DIR"
  mkdir -p "$EXTRACT_DIR"
  "$AVBROOT" ota extract \
    --input "$OUT" \
    --directory "$EXTRACT_DIR" \
    --fastboot \
    --all
  [[ -s "$EXTRACT_DIR/android-info.txt" ]] \
    || die "extract produced no android-info.txt. do not invent one. abort."
  [[ -s "$EXTRACT_DIR/fastboot-info.txt" ]] \
    || die "extract produced no fastboot-info.txt"
  info "android-info.txt:"
  cat "$EXTRACT_DIR/android-info.txt"
  sanitize_fastboot_info "$EXTRACT_DIR/fastboot-info.txt"
  info "fastboot-info.txt (sanitized):"
  cat "$EXTRACT_DIR/fastboot-info.txt"
  info "extract OK. copy $EXTRACT_DIR and $OUT to the laptop with gcloud --tunnel-through-iap"
}

cmd_flash_plan() {
  cat <<'EOF'
# Laptop flash plan — lenOS 1.0.0-shizuku ROOTLESS
# This script will not run these. Phone is not on the VM.
#
# FORBIDDEN
#   flash partitions one-by-one
#   flash vbmeta before logicals
#   invent android-info.txt
#   flash lenos-asteroids-prepatched.zip  (does not boot this unit)
#   flashing lock on the currently booted test-key / 0x3 image
#   re-run a sideload that already returned status 0
#   fastboot boot recovery  (Bad Buffer Size on this unit)
#   --disable-verity --disable-verification with platform-tools 36
#
# 1. Copy (from laptop)
#    gcloud compute scp --tunnel-through-iap \
#      cesurmali76@lenos-build:~/lenos-workspace/lenos-asteroids-rootless.zip ~/lenos/
#    gcloud compute scp --tunnel-through-iap --recurse \
#      cesurmali76@lenos-build:~/lenos-workspace/extracted-rootless ~/lenos/
#    gcloud compute scp --tunnel-through-iap \
#      cesurmali76@lenos-build:~/secure-keys/asteroids/avb_pkmd.bin ~/lenos/
#
# 2. Gates
#    fastboot --version                 # 35+
#    test -s ~/lenos/extracted-rootless/android-info.txt
#    grep -i asteroid ~/lenos/extracted-rootless/android-info.txt
#    # phone must already boot SOME OS (stock or current lenOS). From a brick, use RECOVERY-3A.md first.
#
# 3. From a booting OS → fastbootd (userspace). Bootloader cannot write logicals.
#    adb reboot bootloader
#    fastboot getvar product            # asteroids
#    fastboot getvar unlocked           # yes
#    fastboot reboot fastboot           # MUST end with is-userspace: yes
#    fastboot getvar is-userspace       # yes or STOP
#    fastboot --set-active=a
#
# 4. One command. Do not hand-flash.
#    export ANDROID_PRODUCT_OUT=$HOME/lenos/extracted-rootless
#    fastboot flashall -w --skip-reboot
#    # -w required when leaving Nothing OS. Skip -w only for same-OS update of this zip.
#
# 5. Do NOT flash avb_custom_key yet. Reboot unlocked.
#    fastboot reboot
#
# 6. After it boots (minutes):
#    adb shell getprop ro.lenos.version          # 1.0.0
#    adb shell getprop ro.boot.veritymode        # enforcing
#    adb shell getprop ro.boot.vbmeta.digest     # record this
#    # OEM unlocking ON. Live with it. Then read lock-gates.
EOF
}

cmd_lock_gates() {
  cat <<'EOF'
# LOCK GATES — this script will not run `fastboot flashing lock`.
#
# Rootless has no ReSukiSU, so OEMUnlockOnBoot cannot be installed.
# The 2.8.1 wizard `lock` command refuses rootless for that reason. Correct.
# Locking without that module means: if the phone does not boot after lock,
# OEM unlocking was wiped with /data and you may have no unlock path.
# Slot B now has real _b partitions, which is necessary but not sufficient.
#
# Do not lock unless EVERY line is true:
#   [ ] THIS zip booted UNLOCKED (not the old test-key 0x3 image)
#   [ ] ro.lenos.version = 1.0.0
#   [ ] ro.boot.veritymode = enforcing
#   [ ] ro.boot.vbmeta.digest matches `avbroot ota verify` of THIS zip
#   [ ] fastboot getvar has-slot:init_boot  / vendor_boot / vbmeta  → yes
#   [ ] fastboot getvar slot-unbootable:b → no
#   [ ] OEM unlocking is ON
#   [ ] you have avb.key / ota.key in >= 2 offline places
#   [ ] you accept that a failed boot after lock may be unrecoverable
#
# If all of that is true, ON THE LAPTOP, still unlocked:
#   adb reboot bootloader
#   fastboot getvar unlocked            # yes
#   fastboot erase avb_custom_key
#   fastboot flash avb_custom_key ~/lenos/avb_pkmd.bin
#   # size 0 reported by Nothing fastboot is normal
#   fastboot reboot                     # confirm it still boots, yellow/custom-key later
#   # only then:
#   adb reboot bootloader
#   fastboot flashing lock              # wipes /data; confirm on device
#
# After lock: yellow custom-key warning is expected.
# OEM unlocking ON forever. Never sideload an unpatched OTA.
EOF
  return 1
}

main() {
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
    doctor)      cmd_doctor "$@";;
    apply)       cmd_apply "$@";;
    hardwire)    cmd_apply "$@";;   # legacy name, same strict path
    build)       cmd_build "$@";;
    package)     cmd_package "$@";;
    extract)     cmd_extract "$@";;
    flash-plan)  cmd_flash_plan "$@";;
    lock-gates)  cmd_lock_gates "$@";;
    -h|--help|help|"") usage;;
    lock|flash|sideload)
      die "refusing '$cmd'. this script never talks to the phone. see flash-plan / lock-gates / the guide."
      ;;
    *) die "unknown command: $cmd";;
  esac
}

main "$@"
