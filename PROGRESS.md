# lenOS progress log

One entry per working session. "Verified" = seen working on a booted device
(see `docs/build.md` checklist); everything else is source-complete only.

## 2026-10-21 (twentieth session) — experimental work imported behind a build flag

The VM is still unreachable. No build, flash, wipe or lock was performed. The
experimental implementations are now in the main patchkit, but remain a
separate opt-in series; the default 1.0 product is unchanged.

* **Imported series:** `patches-experimental/` carries 12 patches against
  `frameworks/base`, `packages/apps/Settings`, `packages/apps/SetupWizard` and
  `packages/apps/Seedvault`. The former `vendor_lenos/0001` app patch became
  `experimental/app/LenosOpsec` so the patchkit never patches its own checkout.
  `config/lenos-experimental.mk` adds `LenosOpsec` and
  `ro.lenos.experimental=1`.
* **Build gate:** `LENOS_EXPERIMENTAL=1` makes
  `lenos-1.0-shizuku.sh apply/build` reset any prior experimental series, apply
  the stable series first, then run `lenos-patch.py --experimental
  --check/--apply`, install the app source, and export the flag for the product
  makefile. Without it, the app is neither installed nor built, and the stable
  path is unchanged.
* **Apply-order fix:** experimental `frameworks_base/0004` (screen-off
  clipboard wipe) now carries the stable Secure Paste import context
  (`ApplicationInfo`) in its `ClipboardService` hunk. All 12 patches apply
  individually and in series order after the stable series.
* **Reset/applied gate:** `--experimental --reset` removes renamed/created
  files and empty directories; the driver detects an applied experimental
  series before the stable reset and removes it first. The new
  `--require-applied` reverse-replays the whole series in a throwaway copy, so
  overlapping patches cannot produce a false `missing`; the driver gates both
  series on it before building.
* **Tests/docs:** main suite gains 14 experimental gate tests and 4 read-only
  verification-script tests (366 total, stable series still 53 patches / 348
  original tests green). `experimental/tests/` carries 79 feature/integration tests; every
  sandbox rebuilds the stable base before applying an experimental patch. Added
  `docs/experimental.md`, `tools/verify-build.sh`, `tools/verify-device.sh`, and
  updated the README, feature matrix, build guide and porting guide.
* **Still unvalidated:** combined experimental build/boot, #22 USB HAL behavior,
  #27 restore migration, ENF-1 seccomp/prctl behavior, #20/#21 fs-verity update
  paths, #28 verified-boot states, and all OPSEC UI/share flows. Experimental
  work stays out of the 1.0 release until a build window and device tests pass.

## 2026-10-20 (nineteenth session) — experimental repository + anti-persistence pair

* **New sister repository:** [`ntrop6/lenos-experimental`](https://github.com/ntrop6/lenos-experimental).
  It is the staging area for source-complete implementations that cannot be
  built or device-validated while the VM is unavailable. It is deliberately
  separate from the 1.0 patchkit: none of its patches are in this repository's
  `series`, none are applied by `tools/lenos-patch.py`, and the main driver
  does not copy them to the VM. The README and `docs/features.md` link to it
  and mark it experimental.
* **Implemented there (first batch):**
  * **#20/#21 — system-app update verification.** New
    `PackageVerityExt.java` (GrapheneOS port) plus two `InstallPackageHelper`
    hooks. At boot, immutable packages are recorded before `/data` packages are
    scanned; a `/data` update is rejected if its versionCode is the same as
    (static shared libs) or not greater than (normal packages) the system
    image, if any split lacks fs-verity, or if the signing certificate does not
    have `INSTALLED_DATA`/`ROLLBACK` capability. At install time, fs-verity and
    same-versionCode checks fail before commit. Debug-only escape properties
    are retained for debuggable builds. Two hunks of GrapheneOS's
    `AndroidPackageUtils` original-package exception are **not** ported (lenOS
    ships neither Vanadium nor the GrapheneOS PDF viewer; an empty allowlist
    would only weaken the check).
  * **#25 — screenshot sound.** SystemUI now gates the non-forced screenshot
    sound on `Settings.System.SOUND_EFFECTS_ENABLED`; the
    `screenshotForceShutterSound` aconfig guard is gone, camera-availability
    tracking is registered unconditionally, and the forced-shutter path
    (`MediaActionSound.mustPlayShutterSound()` with the camera open) is
    evaluated first, so a mandatory shutter is not silenced by the
    touch-sounds setting. The existing `multivalentTests` are updated for the
    new constructor/suspend API and cover the forced and sound-effects-off
    paths.
* **Verification:** the experimental repo has its own copy of the strict
  patchkit (`--check`, `--apply`, `--status`, `--reset`), a minimal project
  map, and 19 source-level tests (Java tree-sitter parse, hook order, fs-verity
  loop, versionCode/signature checks, debug guards, Kotlin patch scope,
  apply/reverse). Apply → status → reset was exercised on the real
  `frameworks/base` tree; it restored the tree and removed the created file.
  The main series is still 53 patches; `--check` is clean and the main 348
  tests stay green (only README/feature-matrix/progress/porting docs changed).
* **Honest scope:** #22 (USB-C port control) needs the vendor HAL and keyguard
  port-security path; #23 (ptrace) needs the `GosPackageState`/SELinux-flags
  core; #27 (Seedvault) needs an app fork/update; #28 (Setup Wizard) needs a
  product spec; #30/#31 are XL PackageManager/lock-domain ports; #33–#35 are
  runtime, SELinux, and browser workstreams. Those are listed in the
  experimental repo's `STATUS.md`; they are not claimed as implemented.
* **No build, no flash.** The VM is still unreachable. The first build window
  should apply the experimental series only after the 1.0 tree is validated,
  and run `docs/verification.md` in the experimental repo.

## 2026-10-20 (eighteenth session) — Tier 3 starts: kernel hardening (#32)

* **Tier 3 is open, with #32 first.** #30 (Storage/Contact Scopes) needs the
  `GosPackageState` package-state core (64 framework files plus PackageManager
  persistence), #31 (2FA fingerprint) is an XL `LockDomain` backport, and
  #33/#34/#35 are runtime/SELinux/browser workstreams. Those need a build
  (and mostly a device) to land safely; the kernel tree is checked out and its
  config is statically verifiable, so the kernel workstream is the one Tier 3
  item that can start now.
* **What shipped:**
  * `kernel_nothing_sm7635/0001` — new
    `arch/arm64/configs/vendor/lenos_hardening.config`, an additive 6.6 GKI
    fragment: `INIT_ON_FREE_DEFAULT_ON`, `RANDOM_KMALLOC_CACHES`,
    `RANDOMIZE_KSTACK_OFFSET_DEFAULT`, `SECURITY_DMESG_RESTRICT`,
    `ZERO_CALL_USED_REGS`.
  * `device_nothing_asteroids/0008` — merges the fragment last in
    `TARGET_KERNEL_CONFIG` (after GKI and the two vendor fragments), so it can
    only enable protections.
  * `tests/test_kernel_hardening.py` — 11 checks: exact option set, no
    disable/debug lines, every symbol exists in the pinned 6.6.114 Kconfig,
    none already on in the baseline, the upstream `INIT_STACK_ALL_ZERO`
    default is not double-claimed, BoardConfig ordering, series registration
    and the project registry.
  * Docs: `graphene-porting.md` §19 (what/why/cost/remaining/verification),
    the §14.4 and §17 rows, and the §18 audit (now 53 patches);
    `features.md` kernel row, honest limit and first-flash checks;
    `build.md` kernel checks; `tools/lenos_projects.py` + `tools/mkpatch.sh`
    know the new project.
* **Already on in the baseline:** zero-on-alloc, SLUB freelist
  randomisation/hardening, page-allocator shuffling, hardened usercopy,
  FORTIFY_SOURCE, CFI, ShadowCallStack, BUG_ON_DATA_CORRUPTION/
  LIST_HARDENED, KFENCE, RANDOMIZE_BASE, strict RWX and VMAP_STACK;
  `INIT_STACK_ALL_ZERO` is the upstream 6.6 default with the GKI Clang.
* **Not attempted (documented in §19):** 48-bit VA/4-level page tables,
  forced module signing/lockdown (vendor modules cannot be re-signed), LTS
  point-release cadence, custom allocator canaries/MTE.
* **Caveat:** the pinned `gki_defconfig` is debug-heavy (KASAN/UBSAN/KFENCE);
  the fragment does not change debug options. `init_on_free` costs 3–5%
  typically, so the first build must measure boot time and memory.
* **Verification:** 53 patches `--check` clean; **348 tests green**. Kernel
  hardening is source-complete, not device-verified (the VM is still
  unreachable).
* Next when the VM returns: build and run the kernel checks in `docs/build.md`,
  then continue #20/#21 (fs-verity/versionCode) and the first device-verified
  Tier 2 features; #30/#31 remain large workstreams.

## 2026-10-20 (seventeenth session) — location privacy indicator (Tier 2 #16)

* **The location indicator is in** — Tier 2 #16, and the first lenOS feature
  that needs an aconfig flag flipped. Two halves:
  * `frameworks_base/0027` — `AppOpsPrivacyItemMonitor` now watches
    `OP_COARSE_LOCATION` next to `OP_FINE_LOCATION` (op array, item filter,
    privacy-type mapping and the display check — GrapheneOS's exact four-hunk
    delta), so an app holding only approximate location lights the status-bar
    privacy chip. GrapheneOS's `LocationAccumulatedLogger` and the A17
    `getUidImportance` refactor in the same file are separate features and stay
    unported.
  * `vendor/lenos/release/` — **new mechanism, first use.** The feature was
    dark for a non-obvious reason: `PrivacyConfig.locationAvailable` reads
    `android.location.flags.location_indicators_enabled`, and AOSP's `bp4a`
    release config (the one LineageOS 23.2 selects through
    `vendor/lineage/vars/aosp_target_release`) ships **no** value file for that
    flag, i.e. it defaults to disabled — stock LineageOS 23.2 shows only
    camera/mic indicators. lenOS now ships a release-config map
    (`vendor/lenos/release/release_config_map.textproto`, discovered by
    build/make's `vendor/*/release/` wildcard), a `bp4a` declaration that adds
    `aconfig_value_set-lenos-bp4a`, and one value
    (`location_indicators_enabled`, `ENABLED`, `READ_ONLY`). Release config
    names may appear in several maps (AOSP, `vendor/lineage`, lenOS) and are
    merged, so no AOSP or LineageOS file is patched. Future Tier 2/3 flags can
    be flipped the same way; `docs/graphene-porting.md` §18 carries the audit
    row.
* Evidence trail: `platform/build/release` on `android16-qpr2-release` — the
  location flag directory for `bp4a`/`bp3a`/`bp2a` has no
  `location_indicators_enabled` file, while `trunk_staging` has it
  (`ENABLED`/`READ_WRITE`). The A16 SystemUI gate and the
  `TIME_TO_HOLD_INDICATORS_FOR_LOCATION` hold time are stock code, so enabling
  the flag is sufficient.
* Tests: `tests/test_location_indicator.py` (13 checks: patch content, no
  fine-only filters left, release-config plumbing shape, and the flag name
  cross-checked against `frameworks/base`'s `location.aconfig` through the git
  object store when the sparse checkout lacks the file). Suite 310 green; all
  48 patches `--check` clean against pristine; driver markers added to
  `lenos-1.0-shizuku.sh` (coarse op + flag value).
* Docs: features.md gained a "Privacy indicators" section and a checklist line;
  §14.1 marks the item done; §18 is now a 48-patch audit (39 faithful).
* **#14 loose end closed** — the DHCP-state-reuse half of the Wi-Fi privacy
  row had no port. GrapheneOS's `62d70edb46` ("avoid reusing DHCP state for
  full MAC randomization", 2021, still shipped on their branch 17) was missing
  from LineageOS 23.2: `DhcpClient` renews the lease cached in `IpMemoryStore`
  for the same L2 network even when the MAC changed, so under lenOS's default
  per-connection randomization the DHCP server could still recognize the
  device. The new `packages_modules_NetworkStack/0001` adds
  `shouldAvoidStateReuse()` (asks Wi-Fi for the connected network's
  `macRandomizationSetting`; any lookup failure conservatively starts from
  DISCOVER). The project was already in the tree, so no repo sync was needed;
  the `NETWORK_STACK` UID holds the scan-results bypass, so the lookup works
  without location permission.
* Tests: `tests/test_dhcp_state_reuse.py` (7 checks); suite 317 green; all 49
  patches `--check` clean; driver marker for the DHCP hunk. §14.5's Wi-Fi
  privacy row is now verified in-tree (EUI64 `ClientModeImpl:8417`, netd
  `InterfaceController:73,203-213,287`) and marked done; §18 is a 49-patch
  audit (40 faithful).
* **#18 is in** — the lock-screen "End session" (logout) button is gone.
  GrapheneOS's only change to `KeyguardIndicationController` is the
  short-circuited guard `if (false && …)`, so anyone holding the locked device
  can no longer terminate the session (closing every app) without
  credentials. The power-menu End session action stays stock A16 (same
  `UserLogoutInteractor` gate) and the disabled builder is kept for fidelity;
  GrapheneOS's A17 DevicePolicyManager logout split
  (`isPolicyManagerLogoutEnabled`) is an A17-only refactor. `fwb/0028`, driver
  marker, `tests/test_lock_screen_logout.py` (5 checks).
* Suite is now 322 green; all 50 patches `--check` clean; §18 is a 50-patch
  audit (41 faithful); §14.3's end session row is marked done.
* **#19 is in** — per-user app installation policy. GrapheneOS's
  `UserAppsInstallSettings` screen (enabled / first-party sources only /
  disabled) is behind a new "App installs and updates" row in user details and
  writes the standard `DISALLOW_INSTALL_APPS` / `DISALLOW_INSTALL_UNKNOWN_SOURCES`
  restrictions; the guest's choice goes through the guest-default bundle.
  A16 needs no framework patch (both restrictions are already enforced in
  `PackageInstallerService`/`InstallPackageHelper`). Deltas documented:
  `SettingsEnums.PAGE_UNKNOWN` instead of the absent `METRICS_CATEGORY_UNKNOWN`,
  a new `strings_lenos_users.xml`, and a trimmed `UserRestrictions` helper
  (GrapheneOS's private-space inheritance stays out). `packages_apps_Settings/0003`,
  driver marker, `tests/test_user_app_installs.py` (9 checks).
* Suite is now 331 green; all 51 patches `--check` clean; §18 is a 51-patch
  audit (42 faithful); §14.3's install row is marked done.
* Not done: on-device verification (VM still unavailable), and the DHCP fix
  stays unexercised until the first build (it is a runtime path, not a build
  input). No Settings change for the indicator (it has no toggle — matches
  GrapheneOS).
* **#24 is in** — uncompressed APEXes. LineageOS 23.2's build defaults
  `PRODUCT_COMPRESSED_APEX` to true (`build/make/core/product_config.mk`);
  `vendor/lenos/config/lenos.mk` is inherited after
  `generic_system.mk`/`updatable_apex.mk` and sets it false, so
  `core/soong_config.mk` exports `CompressedApex=false` to Soong and the
  build carries `apexd.config.compressed_apex=false`. Config-only change (no
  patch, no upstream file touched); driver marker added and
  `tests/test_product_config.py` extended. Next is #20 (fs-verity for
  out-of-band updates), which is rated L (design work) — it waits for the VM
  to return so it can be iterated against a real build.
* **#26 resolved by the LineageOS baseline** — no patch. LineageOS's Dialer
  already records calls unconditionally (`call_recording_enabled=true`, no
  region/carrier gate), plays no tone, writes to `Recordings/Call recordings`
  through MediaStore, and holds `CAPTURE_AUDIO_OUTPUT` as a privileged app.
  GrapheneOS's Dialer adds an auto-recording-by-contact subsystem (preference
  store, contact modes, stale-contact cleanup jobs); that larger fork is not
  part of 1.0. `tests/test_call_recording.py` pins the baseline (5 checks).
* Final state this session: **337 tests green**; all 51 patches `--check`
  clean; §18 remains a 51-patch audit (42 faithful).
* Tier 2 scoping (manifest check including `snippets/lineage.xml`): Seedvault
  and SetupWizard *are* shipped (`packages/apps/...`), but neither is a quick
  port. GrapheneOS's Seedvault fork is a newer 16.x upstream plus a prebuilt
  `seedvault-chunker` jar (the source is `GrapheneOS/seedvault-chunker`), so
  #27 is an app update and a build-system decision, not a fix cherry-pick.
  GrapheneOS's SetupWizard fork is a LineageOS wizard with no
  bootloader/OEM-unlock code at all, so #28 needs a specification before any
  patch. #20/#21 (fs-verity + versionCode downgrade), #22 (USB-C data-line
  control, vendor USB HAL) and #23 (ptrace block, GrapheneOS sepolicy) remain
  blocked on the VM/build or on hardware.

## 2026-10-20 (sixteenth session) — sensors permission (OTHER_SENSORS)

* **The sensors permission is in** — Tier 1 #2, closing the Tier 1 set. It
  reuses the SRT mechanism the network permission shipped; two framework
  patches plus the first `frameworks/native` patch:
  * `frameworks_base/0025` was *extended* (not forked) with the shared half:
    the SRT registry now contains both permissions, `shouldAutoGrant` carries
    GrapheneOS's `ExtSettings.AUTO_GRANT_OTHER_SENSORS_PERMISSION` path
    (per-user, default on, work profiles read the parent profile), and the
    manifest declares `android.permission-group.OTHER_SENSORS` ("Sensors")
    plus `android.permission.OTHER_SENSORS` (`dangerous`).
    * **Build-breaking fix found while doing this:** the earlier network port
      had assumed `Manifest.permission_group` is empty in the API files — it
      is not. `core/api/current.txt` now carries `permission_group.NETWORK`,
      `permission_group.OTHER_SENSORS` and `permission.OTHER_SENSORS`;
      without them the API check fails the build.
  * `frameworks_base/0026` — the notification stack: `MISSING_PERMISSION`
    notification channel, proto id `NOTE_MISSING_PERMISSION_OTHER_SENSORS =
    500` (inserted with a trailing-context-only hunk so it co-applies with
    `fwb/0023`'s 400 at the same spot), `PackageManagerNative
    .onDeniedSpecialRuntimePermissionOp` (SYSTEM_UID-guarded), and the ported
    `MissingSpecialRuntimePermissionNotification` (30 s per-app rate limit,
    suppressed once the app is USER_SET, tap opens the grant dialog, "Don't
    show again" sets USER_SET), `IntentReceiver` and `SseUtils` helpers.
  * `frameworks/native/0001` — enforcement: `libs/sensor/Sensor.cpp` tags
    every HAL sensor without a more specific permission with `OTHER_SENSORS`;
    `SensorService::canAccessSensor` denies app UIDs that do not hold it and
    reports the denial through the new
    `IPackageManagerNative.onDeniedSpecialRuntimePermissionOp`. UIDs below
    `AID_APP_START` (the closed-source `gpsd`) keep access; pre-Q apps that
    used the step counter without `ACTIVITY_RECOGNITION` get `OTHER_SENSORS`
    enforced instead of the upstream unconditional allow (GrapheneOS logic,
    adapted to the A16 function shape).
  * `packages_modules_Permission/0002` (extended) maps the "Sensors" group.
* New project: `frameworks/native` is now part of the patchkit (alias added to
  `lenos_projects.py`, patch `frameworks_native/0001`).
* Tests: new `tests/test_sensors_permission.py` (16 checks across the three
  projects: manifest/strings/channel/proto, SRT auto-grant path, notification
  rate limit + action, native enforcement, AIDL). Full suite **297 tests
  green**; `--check` verifies all **47** patches against pristine and a full
  `--apply`/`--reset` round-trip passed. Driver markers added for the native
  tag, the enforcement, the notification hook and the proto id.
* Docs: features.md row + limits bullet + checklist steps; `graphene-porting.md`
  §0/§6/§15/§18 (47 patches: 38 faithful / 5 deliberate / 2 original /
  2 plumbing).
* Not verified on a device (VM still unavailable). On first boot: revoke
  "Sensors" from a compass/level app → readings stop (no events, no fake
  values) while the app stays alive; the blocked access posts the "… tried to
  access sensors" notification; grant it back → readings resume; a system app
  (camera) and body-sensor apps keep working throughout.
* Next: Tier 2 (#16–29) per the approved roadmap.

## 2026-10-20 (fifteenth session) — network (INTERNET) permission

* **The network permission is in** — Tier 1 #1, the last big Tier 1 item
  besides sensors. Ported as GrapheneOS's *"special runtime permissions"*
  (SRT) mechanism, not as a bare `dangerous` flip: revoking `INTERNET` puts a
  user app into **internet-compat mode**, where the OS pretends there is no
  network instead of throwing permission errors at apps that were written
  when INTERNET could not be revoked. Three patches:
  * `frameworks_base/0025-lenos-network-permission.patch` (19 files) — the
    framework:
    * Manifest: `INTERNET` → `dangerous|instant`
      (`permissionGroup=UNDEFINED`) plus the new
      `android.permission-group.NETWORK` group (GrapheneOS's "Network" /
      "access the network" strings verbatim; the `perm_group_network` icon
      already ships in the framework).
    * `SrtPermissions` (`@hide` per-process flags, `FLAG_INTERNET_COMPAT_ENABLED`,
      `shouldSpoofSelfCheck()`), `SpecialRuntimePermAppUtils`
      (`@SystemApi`, `isInternetCompatEnabled()`/`enableInternetCompat()`),
      `AppPermissionUtils` (`@hide`, SRT-only), `AppBindArgs`.
    * Bind plumbing so the server tells each app process whether it is in
      compat mode: `IApplicationThread.bindApplication(in Bundle extraArgs, …)`,
      `ActivityThread`, `ActivityManagerService` (flags computed by the new
      `com.android.server.ext.PackageManagerHooks`), `NativeApplicationThreadWrapper`.
      GOS's `ActivityThreadHooks` indirection is inlined, null-guarded.
    * Server policy: `SpecialRuntimePermUtils` (INTERNET as the only member —
      auto-grant, the system-app "always granted unless user-set" evaluation
      path, GOS's `INTERNET.mode=runtime` metadata escape hatch for system
      apps, and `shouldEnableInternetCompat` = user-installed only).
    * Self-check spoofing in both `PermissionManager` sites
      (`checkPermissionUncached`, `checkPackageNamePermissionUncached`) and
      the four `DownloadManager` gates (invalid id / empty cursor).
    * Permission service (Kotlin): auto-grant **only on a new install**.
      A16 lacks A17's `PackageInstalledParams.isNewlyInstalledInUserId()`, so
      it was added (same name/semantics) and is populated from
      `InstallPackageHelper`'s new-install *and* install-existing paths — an
      app update can never re-grant a revoked INTERNET. Legacy pre-M handling
      and legacy review skip SRT; `resetRuntimePermissions` skips SRT;
      implicit-split inheritance forwards SRT grants.
  * `packages_modules_Connectivity/0002` — all 32 `ConnectivityManager` gates
    return the "network down" answers (`null`/empty/`false`, callbacks
    suppressed) and `NsdManager` uses a stubbed `INsdServiceConnector`
    (registration/discovery/resolve fail with `FAILURE_INTERNAL_ERROR`) so
    NSD can't be used as an ORB; the stub is adapted to the A16 AIDL (A17-only
    methods dropped, 2-arg `connect()`).
  * `packages_modules_Permission/0002` — PermissionController: "Network" group
    mapping, grant/revoke treats SRT as runtime for any targetSdk,
    `isGrantedIncludingAppOp` ignores `reviewRequired` for SRT,
    `AppPermissionGroup` handles legacy apps, and the permission-usage /
    hibernation / auto-revoke screens never classify SRT as unused/revocable.
* Enforcement needs **no new firewall**: revoking drives the already-shipped
  AOSP machinery (`PermissionMonitor` → netd per-UID
  `TRAFFIC_PERMISSION_INTERNET` BPF map; the stock
  `NETWORK_BLOCKED_WITHOUT_INTERNET_PERMISSION` gate is already unconditional
  for every target SDK on Android 16).
* Verified in GrapheneOS's tree before documenting: their branch-17
  `PackageInstaller` has **no** SRT/INTERNET references, so the install-time
  toggle assumed in the original analysis does not exist there either —
  installs auto-grant and app info is the toggle; no installer patch.
  `MissingSpecialRuntimePermissionNotification` / `PackageManagerNative` /
  `IPackageManagerNative` stay deferred with the sensors permission (§6):
  their only caller is the `SensorService.cpp` path.
* Tests: new `tests/test_network_permission.py` (20 checks: manifest + group,
  flag spoofing, both self-check sites, the four DownloadManager gates, bind
  plumbing, server flag computation, auto-grant-on-new-install-only,
  system-app evaluation, the 32 ConnectivityManager gates, the NSD stub,
  XML well-formedness, Java parse, Kotlin balance). Full suite **281 tests
  green**; `--check` applies all **45** patches cleanly from pristine.
  Driver markers added for the SRT flags file, the ConnectivityManager gates,
  the permission-UI mapping and the new-install gate.
* Docs: features.md row + honest-limits bullet (per-UID enforcement,
  compat-mode best-effort, system-app reality) + checklist steps (revoke →
  offline behavior, grant → recovery, update must not re-grant);
  `graphene-porting.md` §0/§5/§6/§15/§18 (45 patches: 36 faithful / 5
  deliberate / 2 original / 2 plumbing) and the §6 infrastructure note.
* Not verified on a device (VM still unavailable). On first boot, the
  round-trip is: revoke INTERNET from a user app → it stays running but all
  network fails as if offline (`dumpsys package <app> | grep INTERNET` shows
  `granted=false` + `USER_SET`); grant → network returns; revoke → update the
  app (`adb install -r`) → must stay revoked.
* Next: sensors permission (§6, Tier 2) reuses this SRT infrastructure —
  extend the server set + manifest, add the `frameworks/native`
  `SensorService.cpp` gate and the notification helper, map it in
  PermissionController, wire `AUTO_GRANT_OTHER_SENSORS_PERMISSION`.

## 2026-10-19 (fourteenth session) — prototype/EVT warning, firmware visibility, memory hygiene, user-app disabling

* **User-installed apps can be disabled** (`packages_apps_Settings/0002`;
  ports GrapheneOS's `AppDisableButton.kt`, closing the last Tier 1 item
  besides the network/sensors permission toggles):
  * The SPA app info screen offers "Disable" for every installed app
    (`!app.installed` gate instead of `!app.isSystemApp`), so a user app can
    be fully prevented from running while keeping its data — strictly
    stronger than Force stop, which lets other apps restart it.
  * `canBeDisabled()` gains GrapheneOS's `!isSystemApp ->
    appButtonRepository.isAllowUninstallOrArchive(context, this)` branch, so
    the uninstall/archive restrictions (device policy, provisioning package,
    home-app handling) still apply.
  * Clicking Disable on a user app disables it directly (authentication is
    still required); the confirmation dialog stays for system apps, where
    disabling downgrades to the system version and destroys data.
  * No framework change needed, verified: `PackageManagerService
    .setEnabledSettings` accepts `COMPONENT_ENABLED_STATE_DISABLED_USER` for
    any package and Settings shares `android.uid.system` (holds
    `CHANGE_COMPONENT_ENABLED_STATE`). `tests/test_disable_user_apps.py` pins
    that invariant.
  * Documented deviations: the legacy `AppButtonsPreferenceController`
    screen is unmodified (GrapheneOS leaves it unmodified too; the SPA screen
    is the default app-info screen), and A17's HSU dialog title/message has
    no A16 counterpart (user apps skip the dialog entirely).
* **Memory hygiene on lock** (`frameworks_base/0024`; ports GrapheneOS's
  lock-time full compacting GC):
  * SystemUI: `KeyguardViewMediator.handleShowInner` runs
    `System.gc(); System.runFinalization(); System.gc();` right before
    `mShowKeyguardWakeLock.release()` — line-level port of GrapheneOS
    (`KeyguardViewMediator.java:3297`).
  * system_server: GrapheneOS triggers it from
    `KeyguardServiceDelegate.onShowingStateChanged` via A17's
    `IKeyguardStateCallback`; Android 16 has no such callback (SystemUI
    reports through `IActivityTaskManager.setLockScreenShown`), so the same
    three calls run on the `setLockScreenShown` binder thread, gated on the
    false→true transition (`mKeyguardShown != keyguardShowing`) and after the
    `mGlobalLock` block — same process, same moment, no WMS lock held
    (documented adaptation).
* **Prototype/EVT device warning** (`frameworks_base/0023`; ports GrapheneOS's
  AMS prototype check):
  * `ActivityManagerService.isPrototypeDevice()` — the GrapheneOS Pixel logic
    verbatim: brand `google`, `ro.revision` must contain `MP`, and
    `ro.boot.secure_boot` must be `PRODUCTION`; anything else posts a
    persistent "Device is an engineering prototype / Device security may be
    affected." notification (the `DEVELOPER` channel, public visibility) from
    the boot-complete path, next to the existing console/MTE notices.
  * Non-Pixel extension (documented deviation): `isPrototypeDeviceNonPixel()`
    treats only an explicit `EVT`/`PVT`/`DVT` marker in `ro.boot.hwlevel` /
    `ro.boot.hardware.revision` / `ro.boot.device_release` as a prototype, so
    a retail Nothing unit — whose bootloader may not report secure-boot state
    at all — can never get a false warning. GrapheneOS returns early for
    every non-Google brand, which would make the feature dead code on
    asteroids.
  * `SystemMessage.NOTE_PROTOTYPE_DETECTED = 400` added to
    `proto/src/system_messages.proto` (same value as GrapheneOS, registered
    before the legacy-ID boundary) plus the two `prototype_device_notification_*`
    strings.
  * AOSP's serial-console notification already exists in LineageOS and is
    untouched; no Pixel `console=null` cmdline heuristic is added (it would be
    unverifiable on Nothing bootloaders).
* **Bootloader version field** (`packages_apps_Settings/0001`, regenerated;
  ports GrapheneOS's `BootloaderVersionPreferenceController`):
  * Settings → About phone → Firmware version now lists "Bootloader version"
    (`ro.bootloader`, "unknown" fallback) between Baseband and Kernel, so the
    persistent firmware state is visible.
  * The pre-Treble `ro.build.expect.bootloader`/`expect.baseband` checks
    GrapheneOS re-enabled in 2017 were reduced to the VINTF check upstream
    (`Build.isBuildConsistent()` + the
    `ActivityTaskManagerService.showSystemReadyErrorDialogsIfNeeded()`
    mismatch dialog), which LineageOS already ships — nothing to port there.
* Tests: new `tests/test_firmware_visibility.py` (12 checks),
  `tests/test_memory_hygiene.py` (4 checks) and
  `tests/test_disable_user_apps.py` (7 checks, incl. the pinned framework
  invariant). Full suite **261 tests green**; `--check` applies all 42
  patches cleanly from pristine. Driver markers added for the prototype
  notification call, the proto id, the bootloader row, both lock-time GC
  sites and the user-app disable gate (plus the previously missing
  feature-flag marker for `fwb/0022`).
* Docs: features.md rows + checklist steps (incl. the ART GC-log check and
  the disable/enable round-trip), the §14.1 directory-listing row closed (was
  stale after the MediaProvider patch), §14.2/§14.3/§14.5 rows closed, §18
  row/counts (33 faithful / 5 deliberate / 2 original / 2 plumbing) and
  watch-list item 8, this log.
* Not verified on a device (VM still unavailable). On first boot check: no
  prototype notification on a retail unit
  (`dumpsys notification --noredact | grep -i "engineering prototype"` is
  empty), About phone → Firmware version shows the real `getprop ro.bootloader`
  value, record what `ro.boot.hwlevel` / `ro.boot.hardware.revision` /
  `ro.boot.device_release` report on this unit, and with
  `setprop log.tag.art VERBOSE` a lock produces "concurrent copying GC" lines
  from both `system_server` and `com.android.systemui` (without repeating on
  unrelated lock-state re-broadcasts).

## 2026-10-19 (thirteenth session) — preserved disabled state + MediaProvider directory listing

* **Package updates preserve enabled state** (`frameworks_base/0022`, exact port of
  GrapheneOS `bff727d`):
  * `InstallPackageHelper.updateSettingsInternalLI` no longer re-enables a
    package on update: the three implicit
    `ps.setEnabled(COMPONENT_ENABLED_STATE_DEFAULT, …)` blocks (system
    packages, the installing user, other users with the package installed)
    are removed, together with the `InstallRequest.isApplicationEnabledSettingPersistent()`
    getter. An app the user disabled — or a system app disabled by default —
    stays disabled across updates.
  * `SystemConfig` advertises GrapheneOS's
    `grapheneos.package_update_preserves_package_enabled_setting` feature
    name verbatim, so apps probing for it behave as on GrapheneOS.
  * The `setApplicationEnabledSettingPersistent` session API/flag and the
    `PackageInstallerSession`/`InstallArgs`/metrics plumbing stay in place,
    matching the GrapheneOS commit; only the update path stops consulting
    them.
* **MediaProvider directory-listing restriction**
  (`packages_providers_MediaProvider/0001`; ports the directory-listing part
  of GrapheneOS `72492da1c`, Storage Scopes):
  * `MediaProvider.getFilesInDirectoryForFuse` now returns the visible file
    names, then an empty-string separator, then the subdirectories that
    contain files the caller can see; callers with
    `READ_MEDIA_AUDIO/IMAGES/VIDEO` and the `Android/` directory keep the
    upstream behavior.
  * `jni/MediaProviderWrapper.cpp` marks entries after the separator as
    directories and skips appending lower-filesystem directory names, so an
    app with no storage permission can no longer enumerate all user-created
    directories (GrapheneOS's metadata-leak fix).
  * New `StorageScopesHooks` keeps GrapheneOS's class name and shape; the
    Storage Scopes themselves (`GosPackageState`, `StorageScope`, scopes UI
    and the `LocalCallingIdentity` scope hooks) are **not** ported yet and are
    listed in the porting inventory's watch list.
  * New project alias `packages/providers/MediaProvider` in the patchkit; the
    workspace has a fresh checkout of the project (Lineage branch
    `lineage-23.2`).
* Tests: new `tests/test_preserve_enabled_state.py` (5 checks) and
  `tests/test_media_no_dir_listing.py` (7 checks). Full suite **238 tests
  green**; patchkit `--check` applies all 39 patches cleanly from pristine.
  Driver markers added for both features.
* Docs: features.md rows + honest limit for Storage Scopes, §14.4 rows, §18
  rows and counts (30 faithful / 5 deliberate / 2 original / 2 plumbing) and
  this log updated.
* Not verified on a device (VM still unavailable). On first boot check:
  `pm disable-user` an app, update it (or `pm install -r`), confirm it stays
  disabled and `pm list features` shows the GrapheneOS feature flag; and a
  file-manager-style app without media permissions creating a file in a new
  folder, then confirming other folders are not listed.

## 2026-10-19 (twelfth session) — LTE-only mode + GNSS network-assistance privacy

* **Settings — LTE-only / 5G-only** (`packages_apps_Settings/0001`, regenerated;
  ports GrapheneOS `5310142ccc` + `8d37b32db6`):
  * `EnabledNetworkModePreferenceController`: adds the "LTE only" entry
    (before the stock entries, skipping the CDMA/no-LTE/except-LTE configs)
    and, when the carrier config exposes NR and NR is currently allowed,
    "5G or LTE only" plus "5G only" (the latter only when the carrier config
    advertises NR standalone). Selection writes the normal
    `ALLOWED_NETWORK_TYPES_REASON_USER` bitmask, so the modem drops 2G/3G (or
    LTE) from its allowed RATs.
  * `PreferredNetworkModePreferenceController` (world-mode path) gets the
    matching LTE-only summary string; new strings in `strings_ext.xml`.
  * Deliberate deviation: GrapheneOS's commit also flips the row availability
    guard (`== EnabledNetworkMode` → `!= PreferredNetworkMode`), which exposes
    the row when the carrier hides network settings (`None`); lenOS keeps the
    stock guard (documented in §18). GrapheneOS's non-world-mode
    `NETWORK_MODE_LTE_GSM_WCDMA` summary fallthrough is kept verbatim.
* **GNSS SUPL/PSDS privacy** (`frameworks_base/0021-lenos-gnss-network-assistance`
  + `packages_apps_Settings/0001`; ports GrapheneOS `GnssSettings`,
  `GnssConfiguration.applyConfigOverrides` and the `GnssLocationProvider`
  observers/gate):
  * New `android.ext.settings.GnssSettings`; keys and numeric values match
    GrapheneOS (`force_disable_supl` = 0 standard / 1 disabled, `psds_server`
    = 1 standard / 2 disabled). GrapheneOS's own proxy modes are not offered
    (lenOS has no proxy infrastructure) and both settings default to
    **disabled** — the privacy-preserving default without a proxy.
  * Overrides are applied after carrier config and debug properties, so
    neither can silently re-enable assistance: SUPL mode 0 + host/port removal;
    PSDS server properties removed + periodic download off. Runtime setting
    changes reload the GNSS configuration; PSDS downloads are additionally
    gated by `isPsdsEnabled()`.
  * Settings: "Network assistance" category on the Location screen with SUPL
    and PSDS rows (Off / Standard server), using a plain `ListPreference`
    controller (GrapheneOS uses a radio-button sub-screen; documented
    substitution). Rows are system-user-only and GPS-feature-gated.
  * Deleted the superseded `device/0003-disable-supl-network-assistance`
    patch: blanking `gps.supl_host` at the device level would have made the
    new "Standard server" choice a no-op. The framework default (off) keeps
    the previous privacy behavior; a user who opts into "Standard server"
    now gets the carrier/device-configured server.
* Tests: new `tests/test_lte_only_mode.py` (9 checks) and
  `tests/test_gnss_privacy.py` (14 checks); `test_device_config.py` updated
  for the removed SUPL patch. Full suite **226 tests green**, all 37 patches
  apply cleanly from pristine. Driver markers added for the LTE entries and
  the GNSS overrides/settings rows.
* Docs: features.md (LTE/5G row, SUPL/PSDS row, limits), §14.2, §15, §18
  (device/0003 row replaced by `fwb/0021` + Settings LTE row; counts 28
  faithful / 5 deliberate) and this log updated.
* Not verified on a device (VM still unavailable). On first boot check: the
  LTE-only row appears and selecting it keeps the modem off 2G/3G; the
  Location → Network assistance rows show "Off" by default and switching to
  "Standard server" survives a reboot; a `dumpsys location` GNSS config dump
  shows no SUPL host while off.

## 2026-10-19 (eleventh session) — radio auto-off timers

* **framework** (`frameworks_base/0020-lenos-radio-auto-off`): ports
  GrapheneOS's `DelayedConditionalAction`, `WifiAutoOff` and `BluetoothAutoOff`
  plus a trimmed `SystemServerExt` (the full GrapheneOS class also bootstraps
  AppCompatConf and dev-build diagnostics, which are not ported yet). The hook
  sits in `SystemServer#startOtherServices` just before
  `mActivityManagerService.systemReady` returns, exactly where GrapheneOS
  calls it. Wi-Fi turns off after the configured timeout when enabled but not
  connected; Bluetooth when the adapter is on with no device connected,
  including LE/GATT.
* **Settings** (`packages_apps_Settings/0001`, regenerated): two list rows
  (`wifi_auto_off`, `bluetooth_auto_off`) in More security & privacy with
  GrapheneOS's `AutoOffSetting` choices (Never / 15 s … 8 h, milliseconds).
  GrapheneOS puts these on its Exploit protection screen with a
  radio-button sub-screen; lenOS uses a plain `ListPreference` (documented
  substitution). New `AutoOffSetting` + `AutoOffPrefController`.
* Driver markers + `tests/test_auto_off.py` (10 checks); features.md rows,
  §14.1/§15/§18 audit and the progress log updated. NFC auto-off stays
  unported (needs the Nfc app side).
* Not verified on a device (VM still unavailable) — on first boot check that
  the two rows appear, a 15 s Wi-Fi timeout turns Wi-Fi off when it is not
  connected, and Bluetooth with no connected device turns off likewise.

## 2026-10-19 (tenth session) — no implicit browser location grant

* **framework** (`frameworks_base/0019-lenos-no-browser-location-grant`):
  the first-boot default-grant pass no longer gives the browser role holder
  (or the `CATEGORY_APP_BROWSER` system handler) foreground location. The
  block simply does not exist in GrapheneOS's `DefaultPermissionGrantPolicy`;
  a one-line lenOS comment marks the removal. Browsers now need an explicit
  user grant like any other app. The unrelated `BrowserUtils` helper from
  the original inventory is not needed (it backs GrapheneOS SELinux handling).
* Driver marker + `tests/test_browser_location.py` (3 checks); §14 row,
  §15 runners-up, §18 audit and the feature matrix updated.
* Not verified on a device (VM still unavailable) — check on first boot that
  a freshly installed system browser shows location as "not granted" before
  the user allows it.

## 2026-10-19 (ninth session) — VPN leak blocking / lockdown hardening

Second Tier 1 batch: the GrapheneOS "improved VPN leak blocking" set (§12).
All pieces target the always-on VPN + "Block connections without VPN" mode.

* **netd** (`system_netd/0001-lenos-vpn-leak-blocking`):
  * DNS lockdown leak (GrapheneOS `82da9204`): `getNetworkForDnsLocked()` now
    derives the fwmark from `canProtectLocked()` / `getPermissionForUserLocked()`
    instead of unconditionally claiming a system, VPN-protected query, so a
    device with every VPN down cannot fall back to the default network's DNS.
  * Multicast firewall (GrapheneOS `dcef5ccb` + `d57ea8dc`): new
    `MulticastFirewallController` drops multicast, IGMP and MLD in/out/through
    `tun+` interfaces (cross-profile VPN side channel), while keeping inbound
    router advertisements and the router-solicitation compatibility rule.
    Wired into `Controllers` in GrapheneOS's chain order; unit tests added and
    `ControllersTest` expectations updated.
  * The SockDiag IP-address log fix (`40c47da2`) is already in LineageOS 23.2.
  * The DnsResolver `.local` transport filter is AOSP commit `a17ba5aee1`
    (2022) and already present upstream — no patch.
* **Connectivity** (`packages_modules_Connectivity/0001-lenos-nsd-lockdown`):
  `NsdService.connect()` refuses regular apps while an always-on VPN with
  lockdown is active, so system NSD discovery cannot bypass the tunnel. The
  branch-16 `connect()` has no package-name argument, so the GrapheneOS
  `enforcePackageNameMatchesUid` call is not part of the port.
* **frameworks/base**:
  * `0017-lenos-connectivity-util`: GrapheneOS `android.ext.ConnectivityUtil`
    (`isSystem`, `isRegularAppWithLockdownVpnEnabled`) exported as a
    module-lib `@SystemApi`; `core/api/module-lib-current.txt` updated.
  * `0018-lenos-vpn-always-on-survival`: `Vpn.startAlwaysOnVpn()` no longer
    clears an always-on VPN whose package is temporarily unsupported; the
    lockdown fail-safe survives safe mode/disabled apps and retries later.
* Patch plumbing: `system/netd` added to the alias maps; new patch directories
  have their own `series`.
* Tests: new `tests/test_vpn_hardening.py` (netd rules/wiring, NSD gate,
  ConnectivityUtil + module-lib API, always-on survival); full suite green.
* Not verified on a device (VM still unavailable). The netd changes affect the
  firewall/eBPF path: first flash should exercise tethering, IPv6 RAs,
  multicast/mDNS apps and Wi-Fi reconnect before daily use.

## 2026-10-19 (eighth session) — Tier 1 start: clipboard privacy

First batch of the approved GrapheneOS Tier 1–3 roadmap (Tier 4 deferred).
Two clipboard leaks closed end-to-end; both are opt-in, matching GrapheneOS's
defaults.

* **Secure Paste, stage 1** (`frameworks_base/0015-lenos-secure-paste`):
  `ClipboardService` reads the GrapheneOS `ALLOW_CLIPBOARD_READ_BY_DEFAULT`
  ExtSetting (already seeded by `frameworks_base/0006`, default `true`). When
  the user enables "Secure paste", a package may only read content it owns;
  the default IME and system apps keep access; `getPrimaryClipDescription`
  returns mime types without the label; `hasClipboardText` keeps the
  existence signal so paste affordances survive (both GrapheneOS behaviours).
  Not ported yet: the per-app `GosPackageState` switch, denial notification
  and the SystemUI/text-selection paste toolbar (stage 2).
* **Cross-profile shared clipboard** (`frameworks_base/0016-lenos-cross-profile-clipboard`):
  GrapheneOS `CrossProfileClipboardAccessSettings` ported verbatim (key
  `cross_profile_clipboard_access`, per-user Secure setting; four policies).
  Enforced on export in `setPrimaryClipInternalLocked`, on import per related
  profile, and on cross-profile drag-and-drop (`DragState`). `Settings.java`
  gains the GrapheneOS constant via the regenerated `frameworks_base/0006`.
* **Settings UI** (`packages_apps_Settings/0001` regenerated): "Secure paste"
  switch and "Cross-profile shared clipboard" list row in Security & privacy →
  More security & privacy, with new `SecurePastePrefController` and
  `CrossProfileClipboardPrefController`; GOS strings reused for the four
  policies. Explicit registration because lenOS does not port GrapheneOS's
  `settings:boolSettingField` auto-wiring.
* Patch hygiene: the two features share `ClipboardService.java`, so the diff
  was split by hunk into independent patches; each is `git apply --check`
  clean against the pristine tree and the test classes apply them separately.
* Tests: new `tests/test_clipboard_privacy.py` (framework gates, policy class,
  drag-and-drop, Settings rows/controllers); full series re-applies.
* Not verified on a device (VM still unavailable).

## 2026-10-18 (seventh session) — GrapheneOS fidelity redos: Wi-Fi privacy + PIN scrambling

Audit-driven redo of the two features that were approximating GrapheneOS
instead of porting it. Both now carry GrapheneOS's own design; every
remaining deviation is deliberate and documented.

* **Wi-Fi privacy defaults redone** (`packages_modules_Wifi/0001-privacy-mac-and-dhcp-defaults`,
  replacing `0001-privacy-dhcp-hostname-default`):
  * `RANDOMIZATION_ALWAYS (=100)` + IntDef entry; new networks default to
    per-connection randomized MACs; `shouldUseNonPersistentRandomization`
    returns true early for it, so any other per-network strategy the user
    picks still wins.
  * DHCP hostname off by default; XML tag renamed `SendDhcpHostname` →
    `SendDhcpHostname2` so values written by stock Android are ignored
    after upgrade; secure-only legacy backfill removed.
  * Retired the old approximation: `Settings.Global` force-flag seeding
    (`frameworks_base/0002` regenerated), RRO bool, app toggle.
* **PIN scrambling redone** (GrapheneOS implementation replaces Lineage's):
  * `frameworks_base/0008`: `setupPinScrambling` on the shared base view
    (SecureRandom shuffle + digit→view remap, hardware keys follow the map),
    wired for the keyguard (PRIMARY key) and SIM PIN/PUK (SIM key, inherits
    by default).
  * `packages_apps_Settings/0001`: ported `com.android.settings.ext`
    controller infra + `PinScramblingPrefController` (adapted for A16's
    single credential domain — no LockDomain), lock-picker switch, SIM-lock
    switch, string.
  * lenOS deviation: primary default **on** (GrapheneOS ships it off),
    commented in `frameworks_base/0006`.
  * Deleted the Lineage remnants: `PinScramblePreferenceController` + its
    picker entry, `device_nothing_asteroids/0005`, the whole `lineage_sdk`
    series.
* **App fixed for both redos**: the global Wi-Fi hostname switch and its
  `NETWORK_SETTINGS` permission are gone (least privilege; control is per
  network now); the PIN-scramble switch reads/writes the `Settings.Secure`
  key SystemUI reads (root fallback via `settings put secure`).
* **Docs**: `docs/graphene-porting.md` (the 875-line portability inventory)
  added to the repo with the §18 deviations audit updated for both redos;
  `docs/features.md` brought in line (scramble row, reworded Wi-Fi rows,
  honest-limits and verification-check updates).
* Tests: `test_wifi_privacy.py` replaces `test_wifi_dhcp_hostname.py`;
  `test_pin_scramble.py` rewritten for the ported feature; first-boot and
  product-config tests updated.
* **Quick-win batch 1** (§16 of the portability doc; six line-level ports):
  * `fwb/0009`: fingerprint permanent lockout 20 → 5, maximum password
    length 64 → 128 (GrapheneOS values).
  * `fwb/0010`: clock-drift warning threshold 2 s → 250 ms.
  * `fwb/0011`: PendingIntent immutability warp — missing mutability flags
    log and force `FLAG_IMMUTABLE` instead of throwing; all four creation
    paths use the returned flags; passing both flags still throws.
  * `fwb/0012`: lockscreen notification content hidden by default
    (`def_lock_screen_allow_private_notifications` false, seeded exactly
    like GrapheneOS for new installs/users).
  * `device/0007`: `config_multiuserMaximumUsers` 4 → 32.
  * Driver markers for all six; new `tests/test_parity_hardening.py` (4
    classes) plus a multiuser test in `test_device_config.py`.
* **Screenshot metadata privacy** (GrapheneOS port, §14/§15/§16 of the
  porting doc):
  * `fwb/0013-lenos-screenshot-exif-privacy`: `ImageExporter.writeExif` nulls
    `captureTime` when `ExtSettings.SCREENSHOT_TIMESTAMP_EXIF` is off
    (default off), `updateExifAttributes` is `@Nullable` and early-returns
    before the date/timezone tags, and LineageOS's `TAG_SOFTWARE = "Android "
    + Build.DISPLAY` line (plus its `Build` import) is removed — GrapheneOS
    and AOSP write no build string into screenshots.
  * Settings toggle "Save screenshot timestamp to EXIF" (Settings → Security
    & privacy → More security & privacy) with the GrapheneOS key, row and
    strings, registered explicitly in `MoreSecurityPrivacyFragment` (no
    `boolSettingField` XML auto-wiring). `packages_apps_Settings/0001` was
    renamed to `0001-lenos-ext-settings-ui` — it already carried the
    ext-controller infrastructure.
  * Driver markers for both; new `tests/test_screenshot_exif.py` (2 classes).
* **Distrusted CA removal** (`system_ca-certificates/0001`, GrapheneOS commit
  `14ad6bb`): Chunghwa Telecom (HiPKI Root CA - G1, ePKI Root CA) and
  NetLock Arany (Class Gold) deleted from the system trust store. The
  `android-16.0.0_r4` snapshot LineageOS pins (there is no Lineage fork for
  `system/ca-certificates`) still ships all three, so this is a real
  removal; `Android.bp` globs `files/*`, so no build edit is needed.
  Driver file-absence markers; new `tests/test_ca_certificates.py`;
  `system/ca-certificates` added to both patchkit alias maps
  (`tools/lenos_projects.py`, `tools/mkpatch.sh`).
* **FBE filename padding 32 bytes** (`system_extras/0001`, GrapheneOS
  "pad filenames to 32 bytes instead of 16 or 4 bytes"): every new
  encryption policy requests `FSCRYPT_POLICY_FLAGS_PAD_32` (AOSP: 16, and 4
  on unreachable pre-R v1 policies); the stale in-tree `fscrypt_test`
  expectations were updated to match (GrapheneOS's fork changed only the
  code, leaving its test copy contradicting it — no behavior delta).
  Driver marker; new `tests/test_fbe_padding.py`; `system/extras` added to
  both patchkit alias maps.
* **Wireless alerts optional** (`packages_apps_CellBroadcastReceiver/0001`,
  GrapheneOS "allow toggling presidential alerts" + "always allow disabling
  extreme alerts"): the presidential toggle is visible, runs the config
  service and is read by the alert path; the `mAlwaysOn` channel flag is
  inert; the CDMA category mapping covers the presidential category;
  Brazil's forced-on extreme-alert override is removed. Every alert type
  stays enabled by default. Driver markers; new
  `tests/test_wireless_alerts.py` (7 tests);
  `packages/apps/CellBroadcastReceiver` added to both patchkit alias maps.
* **Delayed Allow buttons** (`packages_modules_Permission/0001` +
  `frameworks_base/0014`, GrapheneOS "delay activation of Allow button(s) in
  runtime permission dialog" + "delay activation of the Allow button in USB
  ADB confirmation dialog"): every allow variant in the runtime permission
  dialog and the USB-debugging prompt's Allow button activate one second
  after they appear; Deny/Cancel stay immediate. Driver markers; new
  `tests/test_delayed_allow.py` (5 tests). The permission-handler debug log
  omits the app package (no longer a field on this branch) — documented.
* **29 patches, 162 tests green** (`run-tests.sh`, `lenos-patch.py --check`).

## 2026-10-17 (sixth session) — duress eSIM wipe (EuiccWipe port)

Closes the last known gap of the duress backend: a duress wipe now erases the
eSIM profiles too, exactly like GrapheneOS.

* New `frameworks_base/0007-lenos-esim-duress-wipe`:
  * `com.android.internal.telephony.euicc.EuiccWipe` (GrapheneOS file):
    enumerates `TelephonyManager#getUiccSlotsInfo`, resets every eUICC slot
    through `EuiccCardManager#resetMemory` with
    `RESET_OPTION_DELETE_OPERATIONAL_PROFILES |
    RESET_OPTION_DELETE_FIELD_LOADED_TEST_PROFILES`, waits for every callback
    and reports success only when all resets return `RESULT_OK`.
  * `EuiccCardManager`: @hide 5-arg `resetMemory(..., int flags)` overload +
    `RESET_FLAG_IS_FOR_DURESS_WIPE = 1`; the public 4-arg API delegates with
    `flags = 0`.
  * `IEuiccCardController.aidl`: the `resetMemory` transaction carries the
    flags argument.
* New project `frameworks_opt_telephony/0001-lenos-esim-duress-wipe`:
  `EuiccCardController.resetMemory` accepts the flags; only `SYSTEM_UID` may
  use them (everyone else gets a SecurityException and the usual package
  check), and a duress-flagged reset skips `updateEmbeddedSubscriptions()`
  so the carrier does not receive an eSIM-removal notification while the
  device is being wiped.
* `frameworks_base/0005` regenerated: `DuressWipe.run(Context)` starts the
  eSIM wipe on a side thread *before* `deleteSecrets()`, waits at most three
  seconds, then powers off (GrapheneOS's ordering);
  `DuressPasswordHelper` passes `mLockSettingsService.getContext()`.
* Tests: new `test_duress_esim.py` (helper contract, flags plumbing,
  SYSTEM_UID gate, carrier-notification suppression, wipe ordering);
  `test_duress.py` updated (the "eSIM not ported" assertions are gone). The
  app's duress text now tells the user eSIM profiles are erased too.
* **18 patches, 110 tests, all green**; `--check` clean on all pristine
  trees. Still source-complete only — no device verification yet.

### Next (as of this session)

1. VM build (blocked locally: fix `gcloud` project/access, then scp — see
   `docs/build.md` section 2), flash with approval, run the checklist.
2. On-device verification: `getprop sys.auto_reboot_ctl` while
   locked/unlocked, lock-screen tile tap opens the bouncer, Wi-Fi hostname
   toggle persists, `veritymode=enforcing` (unlocked), and — last, because
   destructive — the duress wipe, including an empty profile list afterwards
   and no carrier "profile removed" notification.
3. Port backlog from the GrapheneOS inventory artifact (being updated):
   sensor permission, Secure Paste, delayed allow buttons, network
   permission, FBE filename padding, auto-off timers, screenshot EXIF strip.

## 2026-10-17 (fifth session) — GrapheneOS fidelity audit: init auto-reboot, QS gate, android.ext.settings

Session goal: stop approximating where GrapheneOS has a proven design; redo
the approximations as faithful ports and lay shared infrastructure.

* New `frameworks_base/0006-lenos-ext-settings`: port of GrapheneOS's
  `android.ext.settings` package (`Setting`/`BoolSetting`/`IntSetting`/
  `StringSetting` plus the system-property variants) and `ExtSettings` with
  the GrapheneOS key literals added to `Settings.Global`/`Settings.Secure`
  and defaults in `core/res/res/values/config_ext.xml`. Entries whose
  enforcement code is not ported yet are inert; they exist so later ports
  drop in without redefining storage.
* Auto reboot redone (`frameworks_base/0003` rewritten, new
  `system_core/0001-lenos-auto-reboot-init`): `LenosAutoRebootService` is
  gone. init owns a `CLOCK_BOOTTIME_ALARM` timer special-cased on the
  `sys.auto_reboot_ctl` property (timeout seconds /
  `on_device_unlocked`), ignores requests until the first unlock, never
  restarts a running timer, clamps sub-20s durations and reboots through
  `HandlePowerctlMessage`. `AutoReboot.java` (keyguard package) forwards
  keyguard showing-state for the current user from `KeyguardStateMonitor`;
  the timeout is `Settings.Global.settings_reboot_after_timeout`
  (GrapheneOS key, 18h default via ExtSettings). The SettingsProvider seed,
  the RRO integer and the old app key are removed; app, product prop
  (`auto_bfu=init`), tests and docs updated. Deviations recorded in
  `docs/features.md`: generic `system_prop` SELinux context (GrapheneOS
  uses a dedicated `auto_reboot_ctl_prop` type — needs a
  `system/sepolicy` project), and no call-in-progress deferral (GrapheneOS
  parity: the timer only arms after the first unlock, so BFU is never
  interrupted).
* QS gating redone (`frameworks_base/0004` rewritten): the toast approach
  is replaced by GrapheneOS's design — every tile action routes through
  `QSTileImpl#handleAction`, tiles opt in with `isAllowedWhenLocked`
  (default: not allowed), and a blocked action posts through
  `postQSRunnableDismissingKeyguard`, so the keyguard bouncer is shown and
  the action runs only after a successful unlock. `QSHost`/`QSHostAdapter`
  expose the keyguard state; the allow-list is GrapheneOS's 11 tiles
  (flashlight, both variants; QR scanner; color inversion/correction; Night
  Light; reduce bright colors; dark theme; rotation lock; battery saver;
  device controls); the camera toggle is no longer a lock-screen
  exception.
* Tests: `test_auto_reboot.py` and `test_qs_unlock_gating.py` rewritten
  around the new contracts (property protocol, BFU gate, clamp, restart
  suppression, unlock-prompt gate, allow-list, no toast leftovers);
  `test_first_boot_defaults.py` trimmed of the removed seed.
  **16 patches, 101 tests, all green**; `lenos-patch.py --check` ok on all
  pristine trees.
* Research: full GrapheneOS→lenOS portability inventory is being collected
  as a separate artifact; duress eSIM erasure (`EuiccWipe`) remains the
  known duress gap until that lands.

### Next (as of this session)

1. VM build (blocked locally: fix `gcloud` project/access, then scp — see
   `docs/build.md` section 2), flash with approval, run the checklist.
2. On-device verification of the redo: `getprop sys.auto_reboot_ctl` while
   locked/unlocked, timeout value read/written by the app, lock-screen tile
   tap opening the bouncer without a state change.
3. Duress eSIM erasure port once the inventory artifact lands.
4. Backlog candidates from the inventory: sensor permission, Secure Paste,
   delayed allow buttons, LTE-only toggle, 2nd PIN, FBE filename padding,
   Wi-Fi/BT/NFC auto-off timers, screenshot EXIF strip, network permission.

## 2026-10-17 (fourth session) — framework: duress credential backend

* New framework patch `frameworks_base/0005-lenos-duress-credentials`: a port
  of GrapheneOS's duress implementation into `LockSettingsService`, making the
  `LenosSecurity` app's existing duress UI work end-to-end.
  * Four new classes under
    `services/core/java/com/android/server/locksettings/`: `DuressCredential`
    (scrypt-stretched hash of one credential via the synthetic-password
    `stretchLskf`, the same stretching the real lock credential uses),
    `DuressCredentials` (PIN+password pair serialized as hex into the system
    user's lock settings storage), `DuressPasswordHelper` (verification hook,
    background thread), `DuressWipe` (destroys storage keys + Secretkeeper,
    powers off).
  * Integration: `LockSettingsService.doVerifyCredential` is now a thin
    wrapper around `doVerifyCredentialInner` that checks the duress pair in a
    `finally` — only on failure/mismatch and only for typed PIN/password
    credentials, so a correct credential can never trigger the wipe. New
    binder methods `setDuressCredentials`/`hasDuressCredentials` plus
    `LockPatternUtils` client methods match the app's reflection contract
    (`LockBridge`); `RecoverySystemService.deleteSecrets()` made public as
    the wipe entry point; two methods added to `ILockSettings.aidl`.
  * Owner gating: set/check/delete all verify the current lock credential
    (`checkOwnerCredential`); min 4 digits/chars at LOW complexity
    (`validateDuressCredential`); `checkWritePermission` /
    `checkPasswordHavePermission` on the binder methods; stored form is a
    stretched hash, never the credential.
  * Shell workflow for on-device verification:
    `cmd lock_settings set-duress-credentials --old <cred> --duress-pin 1234
    --duress-password '' [--sleep-5s-before-poweroff]`.
  * Limitation vs GrapheneOS: eSIM profile erasure (`EuiccWipe`) is not
    ported; documented in the class and the feature matrix.
* App: duress copy updated (no eSIM promise); header/`LockBridge` comments
  refreshed; `config/lenos.mk` sets `ro.lenos.security.duress=framework` so
  the status card shows a real backend.
* Tests: `tests/test_duress.py` (15 checks: app↔framework method-name
  contract, failure-only check, typed-credential gate, owner gating,
  stretched-hash storage, wipe actions, the eSIM limitation pin, shell
  workflow). **14 patches, 98 tests, all green**; trees pristine
  (`lenos-patch.py --check` ok).
* `docs/features.md`: duress moved out of "Experimental" into a real row in
  "Lock, data and recovery", with honest limits and a destructive
  verification-checklist step; the old experimental section is now the
  "Not in the 1.0 series" list.

## 2026-10-17 (third session) — framework: auto reboot to BFU + QS unlock gating

* New framework patch `frameworks_base/0003-lenos-auto-reboot`: a
  `LenosAutoRebootService` system service (started next to AlarmManager in
  `SystemServer`) reboots a secured device back to the before-first-unlock
  state when it has stayed locked longer than
  `Settings.Global.lenos_auto_reboot_timeout_ms`.
  * Countdown arms at screen off and resets on every unlock, so it measures
    time since last use; exact `ELAPSED_REALTIME_WAKEUP` alarm with a private,
    immutable PendingIntent; a content observer re-arms when the value
    changes.
  * Safety: skipped when no secure lock is set, deferred (10 min retry) while
    a call is in progress; `0` disables; out-of-range values fall back to the
    18h ROM default. Emergency calling keeps working after reboot.
* `frameworks_base/0002` extended: first boot seeds
  `lenos_auto_reboot_timeout_ms` from `def_lenos_auto_reboot_timeout_ms`
  (stock value 0); the product RRO ships the hardened 18h value
  (`rro/LenosSettingsProviderOverlay`).
* `config/lenos.mk`: `ro.lenos.security.auto_bfu=framework`, so the app's
  status card reports a real backend instead of `?`. No app change needed —
  the BFU spinner already reads/writes the same int setting.
* New framework patch `frameworks_base/0004-lenos-qs-unlock-gating`: while a
  secure lock screen is up, `QSTileImpl` blocks primary/secondary/long clicks
  on every tile and shows an "Unlock the device to use quick settings" toast;
  a locked device can no longer toggle radios (airplane mode as an anti-theft
  hole). Flashlight and camera-toggle tiles stay usable; policy-disabled tiles
  still open the admin dialog first; metrics only log allowed clicks.
* Tests: `tests/test_auto_reboot.py` (15 checks: setting-key/default equality
  across service + provider + app + RRO, SystemServer ordering, lock/call
  guards, alarm privacy, observer); `test_first_boot_defaults.py` extended for
  the new seed; `tests/test_qs_unlock_gating.py` (9 checks). **13 patches,
  83 tests, all green**; trees pristine
  (`lenos-patch.py --check` ok; `frameworks/base` `services/java/` was added
  to the workspace sparse-checkout so `SystemServer.java` is editable).
* `docs/features.md`: new "Lock, data and recovery" section, app matrix,
  experimental list, honest limits and verification checklist updated.

## 2026-10-17 (second session) — committed, VM driver on the patchkit

* All of the previous entry committed on branch `lenos-1.0` as ten small
  commits (baseline `223b79f` → `ea130a7`): pycache/.gitignore, patch
  reorganization, RROs, config, app, tools, tests, docs, `--reset`, VM driver.
* `tools/lenos-patch.py --reset`: returns the series' projects to the pinned
  revision. Restores tracked files, deletes files the series created (plain
  `git checkout` leaves those behind, after which `--check` can never pass),
  prints what it discards, refuses to delete a tracked file, and verifies the
  result. Covered by `tests/test_patchkit_reset.py` (4 tests).
* `lenos-1.0-shizuku.sh`: `apply` replaces the old `hardwire` step
  (`hardwire` kept as alias). Flow: wizard reset → patchkit `--reset` → verify
  pinned → install build inputs (`config/`, `app/`, `rro/`) into
  `$SRC/vendor/lenos` → `--check`/`--apply`/`--status` → series markers; dies
  on any missing patch. `doctor` now checks the patchkit (not `hardwire.py`);
  flash-plan/lock-gates expect `ro.lenos.version=1.0.0`.
* VM driver validated end-to-end on a scratch copy of the five patched
  projects with stub wizard/keys/avbroot: clean apply, dirt warning + discard,
  created-file removal, repeated reset→apply cycles, hard stop on drift.
* **11 patches, 59 tests, all green**; workspace trees pristine
  (`lenos-patch.py --check` ok).
* Note: this laptop's `gcloud` config points at a non-existent project
  (`project-10f47b24-…`), so the VM was not reachable this session — the
  driver is ready to scp (see `docs/build.md` section 2).

## 2026-10-17 — product config, RROs, Wi-Fi DHCP hostname

* `config/lenos.mk` rewritten: ships `LenosSecurity` + three input RROs, the
  privapp allowlist, and documented product properties (branding, tracer off,
  radio/modem logging off, small radio log buffer). Dropped dead
  `PRODUCT_PACKAGES_REMOVE`/`net.hostname` and the duplicate `ExactCalculator`.
* Replaced the old build-time `overlay/` directory (which the device tree's
  `PRODUCT_ENFORCE_RRO_TARGETS := *` converts to implicit RROs anyway) with
  three explicit static RROs under `rro/`:
  * `LenosFrameworksOverlay` — `config_ntpServers` = `ntp://pool.ntp.org`;
  * `LenosSettingsProviderOverlay` — hardened `def_lenos_*` + privacy defaults
    (Bluetooth/wakeup scanning off, location 0, USB storage off, no lock-screen
    QR scanner);
  * `LenosNetworkStackOverlay` — connectivity checks via
    `cp.cloudflare.com/generate_204` (string + array resources, so the Google
    defaults can never kick in).
* New device patch `0006-privacy-device-name`: both Nothing SettingsProvider
  overlays default the device name to `Android` (Bluetooth/Wi-Fi Direct name)
  instead of the commercial model.
* New Wi-Fi module patch `packages_modules_Wifi/0001-privacy-dhcp-hostname-default`:
  DHCP hostname restriction defaults to "block on all network types"
  (fail-closed) and now persists in
  `Settings.Global.lenos_wifi_send_dhcp_hostname_restriction`; the stock
  permission model (NETWORK_SETTINGS / SetupWizard / device owner) is kept.
* `LenosSecurity`: fixed the Soong `platform_apis`/`sdk_version` conflict,
  version strings to 1.0.0, added `NETWORK_SETTINGS` to the allowlist, and a
  new Wi-Fi DHCP hostname toggle (Wi-Fi API first, persisted setting fallback,
  root last).
* Docs: `README.md` and `docs/build.md` rewritten for the patch-based
  pipeline, `docs/features.md` (matrix + honest limits) added.
* Tests: `test_product_config.py`, `test_wifi_dhcp_hostname.py` added,
  `test_device_config.py` extended. **11 patches, 55 tests, all green**
  (`run-tests.sh`, `lenos-patch.py --check`).

## Earlier sessions (pre-restructure, same tree)

* Patchkit hardened: shared project aliases, strict apply with drift failure,
  sandbox test harness, `mkpatch.sh` workflow. Baseline commit `223b79f`.
* `frameworks/base/0001` SSAID rotation on reinstall; `0002` first-boot
  defaults (MAC randomization force, strict DoT, NTP, captive portal).
* `lineage-sdk/0001` + device `0005`: PIN scramble on by default.
* Device `0001`–`0004`: lenOS product, insecure enterprise Wi-Fi off, generic
  tether SSID, SUPL off, no-2G default network mode.
* `vendor/lineage/0001`: `LENOS_STRIP_PACKAGES` filtering; Gallery2 stripped.
* Legacy 1.0.0-shizuku patches moved to `legacy-patches/` (provenance).

## Next (in order)

1. VM build: fix the laptop's `gcloud` project/access, scp
   `vendor/lenos` + `lenos-1.0-shizuku.sh` (see `docs/build.md` section 2),
   run `./lenos-1.0-shizuku.sh apply` then `build` on the VM (8–17h), then
   flash the zip **only with explicit approval**; run the verification
   checklist on the booted device and record results here.
2. Wi-Fi hostname toggle: verify end-to-end (settings value, DHCP capture).
3. RRO enablement check (`cmd overlay list`); if an RRO is not enabled or the
   target policy rejects it, adjust the partition/priority flags.
4. Auto reboot to BFU: verify on device (`settings get global
   lenos_auto_reboot_timeout_ms` = 64800000, spinner writes, prove the reboot
   with the 10 minute choice, confirm call deferral).
5. Quick settings gating: verify on the lock screen (tile tap → toast, no
   state change; flashlight works; unlocked device unaffected).
6. Cromite/WebView decision (Jelly replacement), OTA/updater hardening,
   signed-update reporting.
7. Framework work still out of the series: network permission, sensor
   permission, 2nd PIN
   (auto reboot to BFU, QS-tile gating, duress, LTE-only, the GNSS toggles,
   preserved disabled state, the MediaProvider listing restriction, the
   prototype/EVT warning + firmware visibility, the lock-time memory
   hygiene and user-installed app disabling are done).
8. First-boot checks for the new rows and notifications: LTE-only entry
   order/selection, Network assistance defaults = Off, SUPL/PSDS switch
   survives reboot, `dumpsys location` shows no SUPL/PSDS servers while off,
   `pm list features` shows the GrapheneOS enabled-state flag, directory
   listing without media permissions only shows folders with the app's own
   files, no "engineering prototype" notification on a retail unit (and
   record the `ro.boot.hwlevel` / `ro.boot.hardware.revision` /
   `ro.boot.device_release` values for the phase-prop list), the
   Firmware version screen shows the real `ro.bootloader` value, and locking
   with `log.tag.art` set to `VERBOSE` produces compacting-GC lines from both
   `system_server` and SystemUI.

## 2026-10-20 — experimental batch 2 (source-only; no build, flash or lock)

The VM is still unreachable. Work moved to `ntrop6/lenos-experimental`; the main 1.0 series is
unchanged and remains 53 patches / 348 tests.

* **#22 USB-C data-line control:** `frameworks_base/0003` + `packages_apps_Settings/0002`.
  Uses AOSP 16 per-port `UsbPortManager.enableUsbData` rather than GrapheneOS's vendor sysprops;
  preserves the five mode constants and `persist.security.usb_mode`, applies on boot/keyguard/first
  unlock, rejects ordinary re-enables while blocking, and exposes the Settings row. Modes 0 and 1
  are equivalent because the portable HAL only cuts data lines; `asteroids` HAL support is
  unverified, so this stays experimental.
* **#17 crash/ANR viewer:** `packages_apps_Settings/0001`. Local DropBox reader, bounded entries,
  explicit sharing only, no network permission or upload path. Not GrapheneOS's crash service.
* **#28 Setup Wizard warning:** `packages_apps_SetupWizard/0001`. Non-blocking welcome-page warning
  when `ro.boot.verifiedbootstate` is not green; wording explicitly does not tell users to re-lock
  an unsigned build.
* **#27 Seedvault prefix:** `packages_apps_Seedvault/0001`. GrapheneOS internal `app.grapheneos`
  prefix + prebuilt chunker, keeping `com.stevesoltys.seedvault` and `BASE_SPLIT`. Old backups may
  not restore; migration is unverified.
* **OPSEC additions (lenOS-original):** `vendor_lenos/0001` builds `LenosOpsec` with a
  metadata-scrubbing image share target (OPS-1) and an Offline Quick Settings tile (OPS-2);
  `frameworks_base/0004` + `packages_apps_Settings/0003` add the opt-in, per-user screen-off
  clipboard wipe (OPS-3). OPS-4 / Secure Paste stage 2 (`packages_apps_Settings/0004`) exposes the
  existing AOSP `OP_READ_CLIPBOARD` AppOp per user-installed app, with no framework patch or new
  permission. OPS-5 adds a text-share target that strips known tracking parameters without opening
  or resolving links. No network code; no new trust anchors.
* **#23 partial / ENF-1:** `frameworks_base/0005` + `packages_apps_Settings/0005` add an opt-in
  global native-debugging block. It clears `PR_SET_DUMPABLE` for newly started non-system,
  non-debuggable, non-profileable app processes. It is not the per-app `GosPackageState`/SELinux
  policy; there is no denial UI and root remains exempt. Off by default; unbuilt.
* Experimental repo: 13 patches, 79 source-level tests, all strict `git apply --check` clean.
  `STATUS.md`, `docs/opsec.md`, provenance and verification were updated. Nothing promoted to 1.0.
* Remaining blockers: full per-app #23 (GosPackageState/sepolicy), #30/#31 (XL
  PackageManager/credential-domain ports), #33/#34 (runtime/SELinux workstreams), #35 (browser
  product decision). No flash, wipe or lock was performed.
