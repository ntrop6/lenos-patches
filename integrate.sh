#!/usr/bin/env bash
# Install vendor/lenos and hardwire OPSEC into the Lineage sources.
# No git apply. No repo sync. No lock. Codename shizuku. DNS Quad9.
set -euo pipefail
SRC="${1:-$HOME/lenos-workspace/lineage}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DEVICE="$SRC/device/nothing/asteroids"
SETTINGS="$SRC/packages/apps/Settings"

[[ -f "$DEVICE/lineage_asteroids.mk" ]] || { echo "ERROR: not an asteroids tree: $SRC" >&2; exit 1; }
[[ -d "$SETTINGS" ]] || { echo "ERROR: missing packages/apps/Settings" >&2; exit 1; }

echo "[lenOS 1.0-shizuku] install vendor/lenos -> $SRC/vendor/lenos"
rm -rf "$SRC/vendor/lenos"
mkdir -p "$SRC/vendor"
cp -a "$HERE" "$SRC/vendor/lenos"
rm -f "$SRC/vendor/lenos/integrate.sh"

python3 "$HERE/config/hardwire.py" "$SRC"

echo
echo "Verify:"
echo "  grep lenos.version $DEVICE/system_ext.prop"
echo "  grep PRIVATE_DNS $SRC/frameworks/base/packages/SettingsProvider -r | head"
echo "  grep gps.supl_host $DEVICE/rro_overlays/CarrierConfigResCommon_Vendor/res/xml/vendor.xml"
echo
echo "Order: reset hardening FIRST (git reset), then this, then build."
echo "  export LENOS_ALLOW_LOW_MEMORY=1 LENOS_BUILD_JOBS=4"
echo "  ~/lenOS-2.8.1-ReSukiSU-single.sh reset hardening"
echo "  bash $HERE/integrate.sh $SRC"
echo "  ~/lenOS-2.8.1-ReSukiSU-single.sh reset build"
echo "  ~/lenOS-2.8.1-ReSukiSU-single.sh build --rootless --hardening full"
echo "Do not repo sync. Do not lock. DNS is Quad9 DoT (dns.quad9.net)."
