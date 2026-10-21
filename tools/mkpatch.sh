#!/usr/bin/env bash
# mkpatch — turn the current edits in a pinned project into a lenOS patch file.
#
# Usage:  mkpatch.sh <project-path> <patch-name>
#   e.g.  mkpatch.sh frameworks/base 0001-ssaid-rotate-on-reinstall
#
# Assumes the workspace tree is otherwise pristine: it diffs the project and
# then restores it, so the tree stays a clean copy of the pinned upstream and
# every change is carried by the patch series (reproducible, reviewable,
# reversible).
set -euo pipefail

WS="${WS:-$HOME/lineage}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="${1:?project path, e.g. frameworks/base}"
NAME="${2:?patch name, e.g. 0001-ssaid-rotate-on-reinstall}"

ALIAS="$PROJECT"
for p in frameworks/base frameworks/opt/telephony packages/apps/Settings \
         packages/apps/Updater packages/apps/LineageParts \
         packages/apps/CellBroadcastReceiver \
         packages/modules/Connectivity packages/modules/Permission \
         packages/modules/Wifi packages/modules/NetworkStack \
         system/netd system/vold system/core \
         system/ca-certificates system/extras \
         packages/services/Telephony lineage-sdk vendor/lineage \
         device/nothing/asteroids kernel/nothing/sm7635; do
  if [[ "$p" == "$PROJECT" ]]; then ALIAS="$(echo "$p" | tr '/' '_')"; fi
done
# projects whose patch directory alias differs from tr '/' '_'
[[ "$PROJECT" == "lineage-sdk" ]] && ALIAS="lineage_sdk"
[[ "$PROJECT" == "vendor/lineage" ]] && ALIAS="vendor_lineage"
OUT="$HERE/patches/$ALIAS"
mkdir -p "$OUT"

cd "$WS/$PROJECT"
if ! git diff --quiet; then :; else
  echo "ERROR: no changes in $PROJECT" >&2
  exit 1
fi

git diff --stat
git diff >"$OUT/$NAME.patch"
git checkout -- .
echo "wrote $OUT/$NAME.patch"
echo "add it to $OUT/series if it should be applied"
