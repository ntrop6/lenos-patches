# lenOS experimental implementations (imported, opt-in)

Source-complete implementations for lenOS that **cannot be built or validated in the current
environment**. They are imported into the main `vendor/lenos` repository but remain a separate,
opt-in patch series for the Nothing Phone (3a)/(3a) Pro (`asteroids`).

The stable 1.0 series in `patches/` stays the default product and remains independently applicable
to a pristine LineageOS 23.2 tree. Experimental work lives in `patches-experimental/`, the OPSEC
app in `experimental/app/LenosOpsec`, and is selected only with `LENOS_EXPERIMENTAL=1`. Nothing in
this directory is part of the default 1.0 build, is applied by a normal `apply`, or is claimed to
boot.

## Why opt-in

The VM used for lenOS builds is currently unreachable. These changes are therefore **source-only**:

* no `m`/`soong` build has been run for the combined stable + experimental series;
* no image has been flashed;
* no boot-time, install-time, Settings UI, HAL or performance behavior has been observed.

Keeping the series opt-in means a failed experiment cannot make the 1.0 patchkit un-appliable,
while the implementations remain reviewable, testable at the source level, and ready for the first
build window. Every experimental patch is still a strict `git apply` diff against the same pinned
trees, applied **after** the stable series.

## Current contents

| Feature | Patch | State |
|---|---|---|
| **#20** fs-verity enforcement for system-app updates | `frameworks_base/0001-system-app-update-verity.patch` | Implemented; static checks pass; **not built or booted** |
| **#21** reject same/older system-app updates across reboot | same patch (GrapheneOS `PackageVerityExt` pair) | Implemented; static checks pass; **not built or booted** |
| **#25** screenshot sound follows the system sound-effects setting | `frameworks_base/0002-screenshot-sound-settings.patch` | Implemented; static checks pass; **not built or booted** |
| **#22** USB-C data-line control (charging-only / when-locked / AFU) | `frameworks_base/0003-usb-port-security.patch` + `packages_apps_Settings/0002-usb-port-security.patch` | Implemented against the AOSP per-port HAL; **HAL support on `asteroids` unverified** |
| **#17** on-device crash/ANR log viewer | `packages_apps_Settings/0001-crash-log-viewer.patch` | Implemented; local-only; **not built** |
| **#28** Setup Wizard unlocked-bootloader warning | `packages_apps_SetupWizard/0001-bootloader-unlocked-warning.patch` | Implemented; **not built** |
| **#23 partial / ENF-1** global opt-in native-debugging block | `frameworks_base/0005-native-debugging-block.patch` + `packages_apps_Settings/0005-native-debugging-block.patch` | Implemented source-only; **not per-app** and **not built** |
| **#27** Seedvault/GrapheneOS app-id isolation | `packages_apps_Seedvault/0001-grapheneos-app-id-prefix.patch` | Implemented prefix port + GrapheneOS chunker; **restore compatibility unverified** |
| **OPS-1** metadata-scrubbing share target | `experimental/app/LenosOpsec` | Implemented; re-encodes images; **not built** |
| **OPS-2** one-tap Offline radio tile | `experimental/app/LenosOpsec` | Implemented; **not built** |
| **OPS-3** clear clipboard on screen off | `frameworks_base/0004-clipboard-clear-on-screen-off.patch` + `packages_apps_Settings/0003-clipboard-privacy.patch` | Implemented; opt-in; **not built** |
| **OPS-4 / #8 stage 2** per-app clipboard read control | `packages_apps_Settings/0004-clipboard-app-access.patch` | Implemented with AOSP's existing `OP_READ_CLIPBOARD` AppOps policy; **not built** |
| **OPS-5** tracking-parameter scrubber for shared text | `experimental/app/LenosOpsec` | Implemented; local-only link sanitizer; **not built** |

`STATUS.md` tracks the remaining untestable workstreams and the exact reason each is not in this
batch. Do not read the table above as a statement that the rest of the roadmap is done.

The new OPSEC tools are described, with their threat model and limits, in
[`docs/opsec.md`](docs/opsec.md). They are lenOS-only work: GrapheneOS does not ship an equivalent
metadata sanitizer, offline tile, or screen-off clipboard wipe.

## Known limitations

* **#20/#21 require fs-verity on the update APK.** AOSP only sets fs-verity up when the staged APK
  has a v4 signature (`.idsig`). A system-app update installed without one will be rejected; that is
  the intended fail-closed behavior, not a bug. Debuggable builds have the documented escape
  properties for recovery. Do not weaken this on a user build to make an ad-hoc update install.
* **The verifier keeps the system-image package in memory for the boot.** It is intentionally not
  invalidated when an update is installed: the next install must still be compared against the
  immutable package, not against the previous `/data` update.
* **#25 uses the existing system sound-effects setting.** There is no new lenOS-only screenshot
  sound switch; turning off touch sounds also silences the non-forced screenshot sound. Forced
  shutter regions still obey `MediaActionSound.mustPlayShutterSound()`.
* **#22 needs a USB HAL that implements `enableUsbData`.** It deliberately does not use
  GrapheneOS's vendor `sys.port_security_mode` / `security.deny_new_usb2` hooks. If the `asteroids`
  HAL does not implement the standard operation, the policy is a no-op and the Settings screen
  correctly reports unsupported. Modes 0 and 1 both block the data lines because the portable HAL
  operation does not expose a safe VBUS-off operation. The default on user builds is
  `MODE_CHARGING_ONLY_WHEN_LOCKED`; debug builds default to enabled so adb remains usable during
  bring-up. The persistent key is GrapheneOS's `persist.security.usb_mode`.
* **#17 reads DropBox, not a full crash-reporting service.** It shows crash/ANR/Java/watchdog
  entries already present in DropBox, has no upload path and no automatic sharing. Settings needs
  `READ_LOGS`; entries are bounded. It is a log viewer, not GrapheneOS's crash-reporting app.
* **#27 preserves `com.stevesoltys.seedvault` as the application id.** Only the internal
  GrapheneOS package prefix, permission names and chunker are ported. Existing LineageOS Seedvault
  backups may not restore across the prefix change; test migration before relying on them.
* **#28 is a warning, not a lock.** It appears on the Setup Wizard welcome page when
  `ro.boot.verifiedbootstate` is not `green`; it does not block setup and does not encourage
  re-locking an unsigned build.
* **ENF-1 is only a global approximation of #23.** It is not GrapheneOS's per-app native-debugging
  policy: it has no `GosPackageState` state, no per-app allow/deny UI, no SELinux package domain and
  no denial notification. When enabled, newly started non-system, non-debuggable, non-profileable
  app processes clear their dumpable bit; existing processes and system apps are unchanged. Root
  or any process with `CAP_SYS_PTRACE` (including the crash dumper) is not blocked. An app that
  deliberately calls `prctl(PR_SET_DUMPABLE, 1)` can undo its own bit. The setting is off by
  default and must be built and boot-tested before it can be trusted.
* **OPSEC tools are not cryptographic wipes.** Image re-encoding removes metadata from the output,
  but the source app, thumbnails and filesystem caches may retain the original. The Offline tile
  turns off airplane-mode radios but cannot prove the baseband is powered down; it does not cover
  NFC. Clipboard wiping removes the system clipboard and URI grants, not copies kept inside apps,
  IME history or autofill storage.
* **OPS-4 lists only user-installed apps and does not override the global Secure Paste policy.**
  It sets the existing `android:read_clipboard` AppOp to ignored for selected packages; system
  apps, enabled keyboards and shared-UID packages are excluded or warned about in the UI. If the 1.0
  global Secure Paste setting is off, a per-app allow cannot re-enable reads. The screen has no
  search-index provider yet, and the AppOps mode is not a cryptographic capability boundary.
* **OPS-5 removes only known tracking parameters, not all query strings.** It deliberately keeps
  functional parameters (for example `source` or a search query) and does not follow, resolve or
  preview links. A shortener or a site that echoes tracking data in the path/fragment still leaks;
  the user must inspect the cleaned text before sharing. The cleanup is not a URL reputation or
  phishing check.
* **No runtime evidence exists yet.** The tests are source-level only. See
  `docs/verification.md` for the checks that must pass after the first build.

## Apply / check

The experimental patches target the pinned workspace used by the main repository
(`/mnt/sda/AI WORKSPACE/lenos-workspace` by default). They are applied **after** the stable 1.0
series; they are not standalone against a pristine tree.

```bash
WS="/mnt/sda/AI WORKSPACE/lenos-workspace"
PY=/tmp/opencode/lenv/bin/python

# stable first
$PY tools/lenos-patch.py --tree "$WS" --check
$PY tools/lenos-patch.py --tree "$WS" --apply

# then the opt-in experimental series
$PY tools/lenos-patch.py --tree "$WS" --require-applied
$PY tools/lenos-patch.py --tree "$WS" --experimental --check
$PY tools/lenos-patch.py --tree "$WS" --experimental --apply
$PY tools/lenos-patch.py --tree "$WS" --experimental --require-applied
```

Use `--require-applied` for the build gate. It reverse-replays the whole series
in a temporary copy, so overlapping patches cannot produce a false `missing`.

The driver does this for you and installs the app source only in experimental mode:

```bash
LENOS_EXPERIMENTAL=1 ./lenos-1.0-shizuku.sh apply
LENOS_EXPERIMENTAL=1 ./lenos-1.0-shizuku.sh build
```

`--experimental --reset` restores tracked files and deletes files these patches created
(`PackageVerityExt.java`, the USB controller, renamed Seedvault files, etc.). Reset it **before**
the stable series when switching back to a normal build; the driver detects this automatically.

Two read-only helpers are included for the first build window:

```bash
# post-build artifact presence (requires an OUT directory)
OUT=/path/to/out/target/product/asteroids tools/verify-build.sh

# read-only device properties/settings/package checks over adb
ANDROID_SERIAL=... tools/verify-device.sh
```

Neither script builds, flashes, wipes, relocks, reboots or writes a setting. Behavioral checks that
require a cable, a lock transition, a ptrace attempt or a reboot remain manual and are listed in
`docs/verification.md`. The source-level threat review and findings are in
[`docs/security-review.md`](docs/security-review.md).

The OPSEC app source is `experimental/app/LenosOpsec`. The vendor product gate is
`config/lenos-experimental.mk`; `config/lenos.mk` inherits it only when
`LENOS_EXPERIMENTAL=1`. The driver copies the app into the build tree only in that mode.

The #23 partial patch touches `core/jni/android_util_Process.cpp` and
`core/java/android/app/ActivityThread.java`. If the framework checkout is sparse, add those paths
before running the patch checker or tests:

```bash
git -C "$WS/frameworks/base" sparse-checkout add core/jni \
    core/java/android/app/ActivityThread.java
```

## Tests

```bash
cd experimental/tests
LENOS_WORKSPACE="/mnt/sda/AI WORKSPACE/lenos-workspace" \
LENOS_PYTHON=/tmp/opencode/lenv/bin/python ./run-tests.sh
```

The suite builds the stable base in a sandbox and proves:

* every experimental patch applies cleanly after the stable series and is listed in `series`;
* new and modified Java files parse with tree-sitter;
* the #20/#21 boot scan, install-time checks, fs-verity loop, versionCode comparison and signing
  capability checks are present and ordered correctly;
* the screenshot-sound patch keeps the forced-shutter path intact;
* #22 exposes the GrapheneOS-compatible mode constants and persistent property, registers the
  keyguard listener, applies the policy through the per-port HAL and rejects ordinary re-enables
  while blocking;
* #17 stays local-only (DropBox tags, explicit share) and #28 is conditional on the verified-boot
  property without blocking setup;
* #27 uses the GrapheneOS prefix while keeping the public application id;
* the OPSEC tools have no `INTERNET` permission or network code, the scrubber re-encodes rather
  than copying EXIF, the Offline tile cuts airplane mode/Wi-Fi/Bluetooth, the screen-off clipboard
  wipe is per-user and off by default, the per-app clipboard screen uses the existing
  `OP_READ_CLIPBOARD` AppOp without adding a framework surface, and the link scrubber keeps only
  known functional query parameters while remaining offline;
* the #23 partial clears `PR_SET_DUMPABLE` only for opted-in, non-system/debuggable/profileable
  app processes and does not pretend to be the GrapheneOS per-app policy;
* the Settings patches are also applied **in series order** in a sandbox, not just one at a time,
  so a second patch cannot silently stop applying after the first one changes the same
  `strings.xml` or preference XML.

These are **not** runtime tests. The real verification list is in `docs/verification.md`.

## Safety

The binding build/flash/lock rules remain
[`BUILD-FLASH-LOCK.md`](https://github.com/ntrop6/lenos-patches/blob/lenos-1.0/LENOS-1.0-BUILD-FLASH-LOCK.md).
No patch here changes verified boot, encryption, SELinux enforcement, emergency calling, or
recovery. Do not flash an experimental build without explicit approval and a recovery plan.

## Provenance

The GrapheneOS-derived implementations record their upstream source revisions, files and lenOS
deviations in `docs/provenance.md`. Original lenOS work (#17, #28 and the OPSEC tools) is marked as
such. New files carry Apache-2.0 headers crediting GrapheneOS where applicable and The lenOS
Project. The repository is licensed under Apache-2.0 (`LICENSE`).
