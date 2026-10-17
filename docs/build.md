# Building lenOS (asteroids)

The binding rules for building, flashing and locking this device live in
`/home/otoka/lenos-drop/BUILD-FLASH-LOCK.md` (plus `LENOS-1.0-BUILD-FLASH-LOCK.md`
in this repo as historical context). Read them before touching the device.
Summary of the rules that must never be broken:

* **No `repo sync`** on the pinned tree — revisions come from the device
  manifest; sync only to fix a broken tree, then re-pin.
* **Patches only through the patchkit** (`tools/lenos-patch.py`), never
  `git apply` of hand-edited piles or "hardwired" file edits.
* **No firmware `--re-sign`** — it breaks the VBMeta magic.
* **Never flash partitions individually**; use the built zip.
* **Do not lock the bootloader** until the freshly built zip has booted
  unlocked and `getprop ro.boot.veritymode` reports `enforcing`.
* **Never print, commit or upload signing keys.** Key handling stays on the
  build machine.

## 1. Local: produce a patch-applied tree

The workspace tree is kept pristine; patches are the transport format.

```bash
WS="/mnt/sda/AI WORKSPACE/lenos-workspace"
PY=/tmp/opencode/lenv/bin/python

# confirm the series applies to the pinned checkouts
$PY vendor/lenos/tools/lenos-patch.py --tree "$WS" --check

# run the test suite (needs a pristine tree)
LENOS_WORKSPACE="$WS" LENOS_PYTHON=$PY bash vendor/lenos/tests/run-tests.sh

# apply everything
$PY vendor/lenos/tools/lenos-patch.py --tree "$WS" --apply
$PY vendor/lenos/tools/lenos-patch.py --tree "$WS" --status
```

After a build attempt, `--reverse` (or `mkpatch.sh`, which restores the tree it
diffed) returns the tree to the pinned state. Never leave a tree that is
partially patched.

## 2. Build machine (GCP "lenos-build")

The build runs on the VM with the local manifest and the lenOS signing keys.
The older driver script (`~/lenOS-2.8.1-ReSukiSU-single.sh`) did a "hardwire"
step from the previous pipeline; replace that step with the patchkit:

```bash
# on the VM, in the sync'd tree
python3 ~/vendor-lenos/tools/lenos-patch.py --tree ~/lenos-workspace/lineage --check
python3 ~/vendor-lenos/tools/lenos-patch.py --tree ~/lenos-workspace/lineage --apply
python3 ~/vendor-lenos/tools/lenos-patch.py --tree ~/lenos-workspace/lineage --status
```

Then run the VM's normal reset/build steps (rootless + hardening profile as
before). Keys and the avbroot step stay exactly as the VM script does them.

Transfer the patchkit to the VM with:

```bash
gcloud compute scp --tunnel-through-iap --recurse vendor/lenos cesurmali76@lenos-build:~/vendor-lenos
```

## 3. Flash (only with explicit user approval)

Per the rules: flash the whole zip, boot it **unlocked**, verify, and only
then consider locking. Verify at least:

```bash
adb shell cmd overlay list --user 0 | grep -i lenos          # [x] for all three
adb shell settings get global private_dns_mode               # hostname
adb shell settings get global private_dns_specifier          # dns.quad9.net
adb shell settings get global ntp_server                     # pool.ntp.org
adb shell settings get global captive_portal_mode            # 1
adb shell getprop ro.lenos.version                           # 1.0.0
adb shell getprop ro.boot.veritymode                         # enforcing (before locking)
adb logcat -d -s NetworkMonitor | grep cp.cloudflare.com     # checks use Cloudflare
```

The Wi-Fi hostname toggle (lenOS security app) writes
`Settings.Global.lenos_wifi_send_dhcp_hostname_restriction`; check with
`adb shell settings get global lenos_wifi_send_dhcp_hostname_restriction`
(`null` before the first change means the effective default, 3 = blocked
everywhere).

## 4. What "verified" means for a feature

A feature counts as verified only after the checklist above passes on a
booted device and the result is recorded in `PROGRESS.md`. Until then it is
"source-complete", and `docs/features.md` says so.
