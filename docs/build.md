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

After a build attempt, `--reset` (or `--reverse`, or `mkpatch.sh`, which
restores the tree it diffed) returns the tree to the pinned state. `--reset`
also removes files the series *created* — plain `git checkout` leaves those
(untracked) behind and then `--check` can never pass again. Never leave a tree
that is partially patched.

## 2. Build machine (GCP "lenos-build")

The build runs on the VM with the local manifest and the lenOS signing keys.
The VM driver `~/lenos-1.0-shizuku.sh apply` now does the whole tree
preparation and replaces the old "hardwire" step of the previous pipeline:

```bash
# on the VM (tmux), with ~/vendor-lenos being this repo
~/lenos-1.0-shizuku.sh apply     # reset hardening -> reset -> install build
                                 # inputs -> patchkit --check/--apply/--status
~/lenos-1.0-shizuku.sh build     # apply + wizard reset build + mka (8-17h)
```

Equivalent manual steps, if the driver is not used:

```bash
SRC=~/lenos-workspace/lineage
python3 ~/vendor-lenos/tools/lenos-patch.py --tree "$SRC" --reset   # pinned state
python3 ~/vendor-lenos/tools/lenos-patch.py --tree "$SRC" --check   # must pass
python3 ~/vendor-lenos/tools/lenos-patch.py --tree "$SRC" --apply
python3 ~/vendor-lenos/tools/lenos-patch.py --tree "$SRC" --status
```

`apply` resets the series' projects to their pinned revisions (printing any
tracked edits it discards), installs only the build inputs (`config/`, `app/`,
`rro/`) into `$SRC/vendor/lenos`, and dies if any patch or marker of the
series is missing — a half-patched tree never builds.

Then run the VM's normal reset/build steps (rootless + hardening profile as
before). Keys and the avbroot step stay exactly as the driver does them.

Transfer the driver + patchkit to the VM with:

```bash
gcloud compute scp --tunnel-through-iap --recurse \
  vendor/lenos lenos-1.0-shizuku.sh cesurmali76@lenos-build:~/
# then on the VM: mv vendor/lenos ~/vendor-lenos   (driver looks for it there)
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
adb shell 'zcat /proc/config.gz | grep -E "CONFIG_(INIT_ON_FREE_DEFAULT_ON|RANDOM_KMALLOC_CACHES|RANDOMIZE_KSTACK_OFFSET_DEFAULT|SECURITY_DMESG_RESTRICT|ZERO_CALL_USED_REGS)=y"'  # all five
adb shell cat /proc/sys/kernel/dmesg_restrict                # 1
```

The Wi-Fi hostname toggle (lenOS security app) writes
`Settings.Global.lenos_wifi_send_dhcp_hostname_restriction`; check with
`adb shell settings get global lenos_wifi_send_dhcp_hostname_restriction`
(`null` before the first change means the effective default, 3 = blocked
everywhere).

The kernel hardening fragment (`vendor/lenos_hardening.config`, Tier 3 #32)
is merged last by `TARGET_KERNEL_CONFIG`. `init_on_free` is the only option
with a material cost (3–5% typical); record boot time, idle memory and a few
workload timings. The pinned GKI defconfig is debug-heavy (`KASAN`/`UBSAN`),
so do not present those debug features as production hardening results — a
debug-option review is a separate decision.

## 4. What "verified" means for a feature

A feature counts as verified only after the checklist above passes on a
booted device and the result is recorded in `PROGRESS.md`. Until then it is
"source-complete", and `docs/features.md` says so.
