# GrapheneOS → lenOS feature portability inventory

Scope: every feature on https://grapheneos.org/features, mapped to GrapheneOS branch `17` source (their
Android 17 / QPR-era tree), with portability analysis against lenOS = LineageOS 23.2 / Android 16 on
Nothing Phone (3a)/3a Pro ("asteroids", **Qualcomm SM7635 "Snapdragon 7s Gen 3"**). Corrected 2026-10:
the device is Qualcomm, not MediaTek. Kernel: vendor kernel 6.6 built from source in the lenOS tree
(`device/nothing/asteroids/BoardConfig.mk:129-131`: `BOARD_USES_GENERIC_KERNEL_IMAGE := true`,
`TARGET_KERNEL_SOURCE := kernel/nothing/sm7635`), so kernel patches are *theoretically possible* in a
build, but none of the GrapheneOS kernel hardening is a patch-level port; vendor firmware (modem/ISP,
USB-PD, charger, touch, bootloader/AVB trust root) remains closed and immutable for us. Hardware
judgements below have been re-checked for SM7635 (eSIM: supported; USB-C: vendor Qualcomm USB HAL).

Evidence sources:
- GrapheneOS `platform_frameworks_base` @ branch 17 (blobless clone + full shallow clone in `/tmp/opencode/graphene-repos/fwb-full`).
- GrapheneOS `system_core`, `packages_apps_Settings`, `modules_Permission`, `modules_Connectivity`,
  `opt_telephony`, `system_sepolicy`, `external_seedvault`, `providers_ContactsProvider`,
  `platform_system_extras`, `platform_system_ca-certificates` @ 17
  (clone dirs under `/tmp/opencode/graphene-repos/`).
- lenOS workspace `/mnt/sda/AI WORKSPACE/lenos-workspace` (read-only): partial checkouts + **18 patches**
  in `vendor/lenos/patches/` (5× device_nothing_asteroids, **8× frameworks_base**, system_core,
  frameworks_opt_telephony, packages_modules_Wifi, packages_apps_Settings, vendor_lineage), documented in
  `vendor/lenos/docs/features.md` (kept in sync by the redo; it lists the duress eSIM patches 0007 +
  frameworks_opt_telephony/0001). Status 2026-10 (redo landed): ExtSettings infrastructure
  (frameworks_base/0006), the init-based auto-reboot port (system_core/0001 + frameworks_base/0003), the
  GrapheneOS-design quick-tile unlock gating (frameworks_base/0004), the duress feature incl. eSIM
  wipe (frameworks_base/0005+0007, frameworks_opt_telephony/0001), the GrapheneOS-faithful Wi-Fi privacy
  defaults (packages_modules_Wifi/0001) and the GrapheneOS PIN scrambling port
  (frameworks_base/0008 + packages_apps_Settings/0001) are all **done**; sections 1–3 below
  carry status notes. The counts elsewhere in this document were written against the pre-redo series
  (16 patches); the deviations audit in §18 covers the 18 current patches (device/0005 + lineage_sdk/0001
  were deleted; frameworks_base/0008 and packages_apps_Settings/0001 were added).

Caveat: GrapheneOS is on Android 17; lenOS is Android 16 (LineageOS 23.2). Where a GrapheneOS file uses
APIs only present in 17, that is called out as "API risk". Line numbers/paths are branch-17 paths.

Legend for size: S (<200 LOC), M (200–800 LOC), L (800–3000 LOC), XL (>3000 LOC or new subsystem).

---

## 0. Executive summary of the biggest findings

- **ExtSettings is plain `Settings.Global` / `Settings.Secure` + sysprops.** No custom ContentProvider,
  no database. `ExtSettings.java` is only 120 lines; the whole `android.ext.settings` package is ~1.6k
  lines and is *self-contained infrastructure* that can be ported nearly wholesale. Storage keys are
  added to AOSP's `android.provider.Settings` (a handful of constants), defaults come from
  `core/res/res/values/config_ext.xml` resources. **Status: DONE** — lenOS patch
  `frameworks_base/0006-lenos-ext-settings.patch` ("android.ext.settings" package + ExtSettings subset +
  `config_ext.xml` defaults) has landed; the constants already seeded there include AUTO_REBOOT_TIMEOUT,
  WIFI/BLUETOOTH/NFC_AUTO_OFF, SCREENSHOT_TIMESTAMP_EXIF, AUTO_GRANT_OTHER_SENSORS_PERMISSION,
  ALLOW_CLIPBOARD_READ_BY_DEFAULT, dyn-code-loading and MEMTAG defaults, PIN/SIM-PIN scramble (wired and
  shipped via the redo — see §14) — several of the *other* constants have *no behavior wired behind them
  yet* (see §14).
- **GrapheneOS auto reboot is enforced by `init`** (`system/core/init/property_service.cpp`), not by a
  system_server alarm. **Status: DONE** — lenOS has replaced its AlarmManager service with the faithful
  init-based port: `system_core/0001-lenos-auto-reboot-init.patch` + `frameworks_base/0003-lenos-auto-reboot.patch`
  (`AutoReboot.java`, hooked from `KeyguardStateMonitor.onShowingStateChanged`). Key is the GrapheneOS
  key `Settings.Global.settings_reboot_after_timeout` (default 18 h); the old key/boot-seed/RRO are gone.
  See §2.
- **Duress eSIM wipe** needed a *second* small patch beyond `EuiccWipe.java`: the `flags` parameter in
  `EuiccCardManager.resetMemory()`, the `IEuiccCardController.aidl` signature and
  `EuiccCardController.resetMemory()` (skips the carrier removal notification). **Status: DONE** —
  lenOS landed `frameworks_base/0007` + `frameworks_opt_telephony/0001` (2026 redo); with the backend
  (`frameworks_base/0005`) the duress feature is complete (see §3).
- **Network permission** is enforced in the **Connectivity module + netd eBPF firewall**, with UI in
  Settings/PermissionController and the installer; it is the largest single high-value port (multi-repo,
  M–L — AOSP 16/LineageOS 23.2 already contains most of the underlying eBPF/permission machinery, see §5).
- **USB-C port control** needs the vendor USB HAL and kernel to support disabling the data lines at the
  hardware level. On SM7635 the OS-side piece (mode setting + HAL interception of `IUsb.enableUsbData`)
  is portable *if* Nothing's Qualcomm USB HAL implements AOSP's `enableUsbData`; the hardware data-line
  and alternate-mode (DisplayPort) disable are vendor/kernel features we cannot add → not feasible in
  full today, partial port worth prototyping (see §10).
- **Vanadium** is a whole Chromium product (~2 GB source build or a prebuilt APEX/WebView decision);
  realistically `port later / app-level bundle`, not a patch (see §13).
- **FBE filename padding 16→32 bytes** is a genuine one-line GrapheneOS change in `system/extras`
  (`libfscrypt/fscrypt.cpp:247-248`) — cheapest at-rest privacy win in this inventory (see §11).

---

## 1. ExtSettings subsystem (special investigation #1)

**What it is.** A tiny typed-settings library in `frameworks/base` that wraps three storage scopes and
adds defaults/observers. It is *not* a settings provider.

**Files** (`frameworks/base/core/java/android/ext/settings/`, ~1.6k lines total; sizes in lines):

| File | LOC | Role |
|---|---|---|
| `Setting.java` | 179 | abstract base: Scope = SYSTEM_PROPERTY / GLOBAL (`Settings.Global`) / PER_USER (`Settings.Secure`); get/put raw, ContentObserver registration, sysprop observer deliberately unsupported |
| `BoolSetting.java` / `IntSetting.java` / `StringSetting.java` | 76/111/72 | typed get/put + resource-based defaults |
| `BoolSysProperty.java` / `IntSysProperty.java` / `StringSysProperty.java` | 32/39/22 | sysprop-backed settings |
| `ExtSettings.java` | 120 | the registry of settings (AUTO_REBOOT_TIMEOUT, ALLOW_CLIPBOARD_READ_BY_DEFAULT, SCREENSHOT_TIMESTAMP_EXIF, SCRAMBLE_*, dyn-code-loading defaults, MEMTAG, USB port security, conn checks, etc.) |
| `UsbPortSecurity.java`, `ConnChecksSetting.java`, `GnssSettings.java`, `NetworkLocationSettings.java`, `GeocoderSettings.java`, `RemoteKeyProvisioningSettings.java`, `WidevineProvisioningSettings.java`, `CertTransparencyDownloaderSetting.java`, `CrossProfileClipboardAccessSettings.java`, `AltTouchscreenMode.java` | 17–45 each | domain settings |
| `app/AppSwitch.java` + `app/Asw*.java` (10 files) | 21–178 each | per-app hardening switches (exec spawning, hardened_malloc, memtag, dyn code loading, native debug, Play Integrity) |

**Storage mechanism:**
- Global scope → `android.provider.Settings.Global` (e.g. `settings_reboot_after_timeout`,
  `allow_clipboard_read`, `restrict_memory_dyn_code_exec`, `wifi_off_timeout`).
- Per-user scope → `android.provider.Settings.Secure` (e.g. `screenshot_timestamp_exif`,
  `lockscreen_scramble_pin_layout`, `auto_grant_OTHER_SENSORS_perm`).
- Sysprops for a few defaults (`persist.native_debug`, `persist.security.exec_spawn`).
- No `ExtSettingsProvider`, no multi-user database of its own; multi-user works because PER_USER scope
  uses `getStringForUser`/`putString` against the normal settings provider, and the settings provider
  already handles per-user storage.

**Defaults**: `frameworks/base/core/res/res/values/config_ext.xml` (`setting_default_*` bools/integers/
strings, e.g. `setting_default_allow_clipboard_read=true`,
`setting_default_restrict_memory_dyn_code_loading=false`,
`system_pkgs_allowed_*_by_default` arrays) plus `core/res/res/values/public-ext.xml` for the symbol
export list and `string_ext.xml`.

**Dependents (from grep of their repos):**
- `frameworks/base`: dozens of files under SystemUI/system_server use `ExtSettings.*` (see per-feature
  sections). The comment in `Setting.java` says readability of settings is derived via reflection over
  `Settings`-class members, hence the keys were added to `android.provider.Settings`.
- Settings app: 17 files, incl. a custom XML attribute pipeline:
  `settings:boolSettingField="android.ext.settings.ExtSettings AUTO_REBOOT_TIMEOUT"` parsed by
  `res/values/attrs` → `PreferenceXmlParserUtils` (`R.styleable.Preference_boolSettingField`) →
  `src/com/android/settings/ext/BoolSettingPrefController.java` (reflectively resolves the field).
  Plus per-app screens `AswExploitProtectionFragment`, `AppClipboardRead.kt`, `AppExecSpawning.kt`,
  `AppHardenedMalloc.kt`, `AppMemoryTagging.kt`, `AppNativeDebugging.kt`,
  `AppStorage/Memory/WebViewDynCodeLoading.kt`, `AppManagePlayIntegrityApi.kt`, `AswAdapter.kt`.
- Connectivity module: `networksecurity/service/.../ct/Config.java`, `DownloadHelper.java`,
  `CertificateTransparencyDownloader.java` (certificate transparency downloader toggle),
  `NetworkDiagnostics.java`.

**Port assessment:** The package itself depends only on `android.provider.Settings`, `Context`,
`SystemProperties`, `ContentObserver` — all stable AOSP-16 APIs. Only `Setting.java`'s use of
`Settings.isInSystemServer()` (a GrapheneOS addition to `Settings.java`) is a small dependency; a port can
either bring that helper along (it is ~5 lines) or drop that error-swallowing branch. Porting the *whole*
package costs one frameworks_base patch (~1.6k lines, mostly new files). The Settings-app UI glue is
separate and only needed for screens we choose to ship.
**Recommendation: port the package wholesale now** (it is the cheapest infrastructure win in this
inventory); port only the Setting constants that correspond to features we actually port, to keep the
patch reviewable. Do NOT port their `Settings.java` wholesale — their copy has large unrelated
refactors (caching, validation); add only the new key constants.

---

## 2. Auto reboot (special investigation #2)

**What it does.** Reboots a locked, secure device after N seconds so FBE keys leave RAM (device goes
back to Before First Unlock). Timer starts when keyguard starts showing, is cancelled on unlock. Default
18 h, configurable 10 min – 72 h, or off. Explicitly does NOT apply before first unlock (so a device
that was never unlocked since boot doesn't reboot-loop). Unlocking any profile cancels it.

**GrapheneOS pieces:**

1. Java (their `platform_frameworks_base`):
   - `services/core/java/com/android/server/policy/keyguard/AutoReboot.java` (34 lines): a static
     helper. On keyguard shown: reads `ExtSettings.AUTO_REBOOT_TIMEOUT` (Global key
     `settings_reboot_after_timeout`, ms) and writes `sys.auto_reboot_ctl = <seconds>`. On unlock:
     writes `sys.auto_reboot_ctl = on_device_unlocked`.
   - Caller: `services/core/java/com/android/server/policy/keyguard/KeyguardServiceDelegate.java:227`
     inside `onShowingStateChanged(boolean showing)`, right next to their `UsbPortSecurityHooks` call
     (line 231). The callback comes from the keyguard service
     (`IKeyguardService.onShowingStateChanged`) and fires on lock/unlock and user switches (see their
     comment in AutoReboot).
   - Setting/UI: `Settings/src/com/android/settings/security/AutoRebootPrefController.java` (list of
     durations in values), registered in `exploit_protection_settings.xml` under key `auto_reboot`;
     strings in `strings_ext.xml`.

2. init (`platform_system_core`), the actual enforcement (file `init/property_service.cpp`):
   - Statics at ~line 539: `timer_t auto_reboot_timer; bool device_unlocked_at_least_once;
     bool is_auto_reboot_timer_started;`
   - `auto_reboot_timer_init()` (~551): `timer_create(CLOCK_BOOTTIME_ALARM, SIGEV_THREAD,
     auto_reboot_timer_callback)`. `CLOCK_BOOTTIME_ALARM` ⇒ counts across suspend and can wake the
     device; a plain Java AlarmManager cannot match this in all Doze/idle cases.
   - `auto_reboot_timer_callback` (~543): on expiry `trigger_shutdown("reboot")` — i.e. a **normal
     reboot**, not poweroff (memory zeroing on the normal path + FBE → BFU).
   - `auto_reboot_timer_set(duration_sec)` (~561): enforces a 20 s floor, `timer_settime`.
   - `auto_reboot_handle_property_set(value)` (~580):
     * `"on_device_unlocked"` → `device_unlocked_at_least_once = true`, cancel timer if running;
     * otherwise integer seconds; rejected if ≤0; **ignored if the device was never unlocked since
       boot** (this is the BFU protection — the whole state machine is driven by this one flag);
     * if a timer is already running, the request to restart it is ignored (so re-locking without
       unlocking cannot extend the timer — important: keyguard can show/unshow without an unlock e.g.
       camera launch).
   - Hook: in `HandlePropertySet()` at ~line 657: `if (name == "sys.auto_reboot_ctl") { ... }` —
     placed *after* `CheckPermissions()` and before generic `PropertySet()`, so the prop never really
     lands in the property area and system_server only needs write access to this one property.
   - Init call: `auto_reboot_timer_init()` at ~line 1571, guarded by `if (!IsMicrodroid())`.

3. sepolicy (`platform_system_sepolicy`):
   - `private/property_contexts:29` → `sys.auto_reboot_ctl u:object_r:auto_reboot_ctl_prop:s0`
   - `private/property.te:9` → `system_internal_prop(auto_reboot_ctl_prop)`
   - `private/system_server.te:837` → `set_prop(system_server, auto_reboot_ctl_prop)`

**lenOS status (2026 redo) — DONE.** The faithful port has landed and can be audited directly:

- `system_core/0001-lenos-auto-reboot-init.patch` (134 lines) — same design as GrapheneOS:
  `CLOCK_BOOTTIME_ALARM` `timer_create(SIGEV_THREAD)`, `device_unlocked_at_least_once` BFU guard,
  20 s floor, "ignore restart while running" rule, `sys.auto_reboot_ctl` special-cased in
  `HandlePropertySet()` (after `CheckPermissions()`), `auto_reboot_timer_init()` guarded by
  `!IsMicrodroid()`. Difference: the timer callback calls `HandlePowerctlMessage("reboot")` directly
  (GrapheneOS branch 17 calls `trigger_shutdown("reboot")`; both are normal init reboot paths — equivalent).
- `frameworks_base/0003-lenos-auto-reboot.patch` — `AutoReboot.java` (52-line class writing
  `sys.auto_reboot_ctl`, reading `ExtSettings.AUTO_REBOOT_TIMEOUT`) plus one call added in
  `services/core/java/com/android/server/policy/keyguard/KeyguardStateMonitor.java`
  `onShowingStateChanged(showing, userId)`. Android 16's `KeyguardStateMonitor` already has `userId`, so
  no `KeyguardServiceDelegate` change was required (that was only GrapheneOS 17's call site); the firing
  conditions match GrapheneOS (lock, unlock, user switch).
- Key: `Settings.Global.settings_reboot_after_timeout` (`frameworks_base/0006`, `Settings.java` hunk;
  `AUTO_REBOOT_TIMEOUT` default `TimeUnit.HOURS.toMillis(18)`). The earlier inventory suggestion to keep
  the lenOS key `lenos_auto_reboot_timeout_ms` was **deliberately not taken**; the GrapheneOS key was
  adopted to keep behaviour/documentation aligned with GrapheneOS. The old `LenosAutoRebootService`
  (AlarmManager), the old settings key, the boot-seed and the RRO were removed.
- Remaining deltas vs GrapheneOS (all deliberate/benign): no dedicated `auto_reboot_ctl_prop` SELinux
  type — the property is granted through the generic `system_prop` context in the device sepolicy, so the
  SELinux allow is coarser than GrapheneOS's dedicated type (works; revisit if sepolicy is ever tightened);
  no call-in-progress deferral (neither has GrapheneOS — the old lenOS AlarmManager service's call guard
  is intentionally gone, matching upstream: any lock starts the countdown); and the
  `HandlePowerctlMessage` vs `trigger_shutdown` difference noted above.
- ExtSettings was trimmed to the constants actually needed (here: `AUTO_REBOOT_TIMEOUT`), not the whole
  registry.

**API/version risk:** none — self-contained C++ init code plus AOSP-16-stable Java APIs.

**Verdict: shipped/done in lenOS** (was "port now" when sections 0–3 were first written).
**Size as shipped: S (~190 LOC across 2 repos + 1 settings constant).**

---

## 3. Duress PIN/password + eSIM wipe (special investigation #4) — DONE in lenOS

**What it does.** A second PIN and a second password; entering either at any credential prompt
irrecoverably wipes the device (KeyMint keys → storage keys gone) and powers off, optionally wiping
eSIM profiles too. Set only by the owner credential. The duress PIN is also honoured as the
two-factor fingerprint unlock PIN, but not as the SIM PIN (so far).

**GrapheneOS locksettings pieces** (`frameworks/base/services/core/java/com/android/server/locksettings/`):

| File | LOC | Role |
|---|---|---|
| `DuressCredential.java` | 66 | one duress credential: salt via `SyntheticPasswordManager.PasswordData` + `spm.stretchLskf()`; `validate()` uses `LockPatternUtils.validateDuressCredential()` (no shared-prefix with real credential, min length etc.) |
| `DuressCredentials.java` | 120 | pair (pin+password), serialized hex into `LockSettingsStorage` under key `duress_credentials`, user `USER_SYSTEM` |
| `DuressPasswordHelper.java` | 119 | enrollment (owner cred check), `onVerifyCredentialResult()` hook: on a failed verify, copies the credential to a background HandlerThread and checks it against the duress pair; if matched → `DuressWipe.run()` |
| `DuressWipe.java` | ~74 | thread that calls `EuiccWipe.run(ctx, RESET_FLAG_IS_FOR_DURESS_WIPE)`, then `RecoverySystemService.deleteSecrets()` (deleteAllKeys → storage keys), then `PowerManagerService.lowLevelShutdown(null)` (poweroff, no reboot) |
| `LockSettingsService.java` | hook | calls `DuressPasswordHelper.onVerifyCredentialResult()` on every credential verification failure |
| Settings UI | | `DuressPasswordActivity`, `DuressPasswordMainActivity`, `DuressPasswordSetupActivity` in `Settings/src/com/android/settings/security/` |
| tests | | `frameworks/base/tests/DuressPasswordTest/` |

**Telephony/eSIM pieces (ported in the 2026 redo — kept as the implementation reference):**

| Repo | File | Change |
|---|---|---|
| frameworks/base | `telephony/java/com/android/internal/telephony/euicc/EuiccWipe.java` | new helper (~110 lines): enumerates `TelephonyManager.getUiccSlotsInfo()`, for each `getIsEuicc()` slot calls `EuiccCardManager.resetMemory(cardId, DELETE_OPERATIONAL_PROFILES\|DELETE_FIELD_LOADED_TEST_PROFILES, executor, cb, flags)`, waits for all, returns success (this file is in frameworks_base in branch 17; on 16 it can equally live in `frameworks/opt/telephony`) |
| frameworks/base | `telephony/java/android/telephony/euicc/EuiccCardManager.java` | add `public static final int RESET_FLAG_IS_FOR_DURESS_WIPE = 1;` (**@hide**, not part of the public SDK — safe) + hidden `resetMemory(..., int flags)` overload forwarding to the AIDL |
| frameworks/base | `telephony/java/com/android/internal/telephony/euicc/IEuiccCardController.aidl` | `resetMemory(..., int flags)` — AIDL change, needs the module/impl to be rebuilt together |
| frameworks/opt/telephony | `src/java/com/android/internal/telephony/euicc/EuiccCardController.java` | accept `flags`; throw `SecurityException` if a non-SYSTEM_UID passes flags; **skip `SubscriptionManagerService.updateEmbeddedSubscriptions()`** when `flags & RESET_FLAG_IS_FOR_DURESS_WIPE != 0` (otherwise the LPA sends an eSIM removal notification to the carrier on a duress wipe — exactly what a duress wipe must not do) |
| frameworks/opt/telephony | `EuiccCardController` / `EuiccController` | no other changes needed: `port.resetMemory(options, ...)` exists in LOS 23.2 (`EuiccPort.resetMemory`) |

Verified against LineageOS 23.2 (GitHub `lineage-23.2` branches): the AIDL and `EuiccCardController`
there have **no** `flags` parameter — the GrapheneOS signature is theirs, so all four changes must be
applied. `EuiccCardManager`/`IResetMemoryCallback` are otherwise identical.

**Port surface for lenOS:** `frameworks/base` + `frameworks/opt/telephony` (both already in the lenOS
workspace) + hook `EuiccWipe` into the existing lenOS `DuressWipe.run()` (lenOS already has the
GrapheneOS DuressWipe minus the eSIM thread — see `patches/frameworks_base/0005`).
**API/version risk:** low; only internal AIDL/API changes (hidden). The 3 s wait for the eUICC thread
then poweroff mirrors upstream; if the eSIM wipe takes longer it may be cut short by shutdown — same
trade-off as upstream.
**Verdict: shipped/done in lenOS** (was "port now" at first writing). **Size as shipped: S–M
(~370 LOC across 2 repos).** Value achieved: removes the "carrier still has your number/profile after a
duress wipe" leak — the duress flow is now complete. Caveat: on a physical-SIM device without eSIM the
code paths are inert (asteroids supports eSIM, so it matters).

**lenOS status — DONE (both halves, 2026 redo).**
- Duress backend (`frameworks_base/0005-lenos-duress-credentials.patch`): the same GrapheneOS class set —
  `ILockSettings.aidl`, `LockPatternUtils.java`, `DuressCredential.java`, `DuressCredentials.java`,
  `DuressPasswordHelper.java`, `DuressWipe.java`, `LockSettingsService.java` (verify-result hook),
  `LockSettingsShellCommand.java`, `RecoverySystemService.java`.
- eSIM wipe (`frameworks_base/0007-lenos-esim-duress-wipe.patch` + `frameworks_opt_telephony/0001-lenos-esim-duress-wipe.patch`):
  exactly the four changes tabulated above — `EuiccCardManager` hidden `resetMemory(..., flags)` overload
  + `RESET_FLAG_IS_FOR_DURESS_WIPE`, new `EuiccWipe.java` (~113 lines), `IEuiccCardController.aidl` flags
  parameter, and `EuiccCardController.resetMemory` with the SYSTEM_UID gate and the carrier-notification
  suppression. `DuressWipe` calls `EuiccWipe.run(ctx, RESET_FLAG_IS_FOR_DURESS_WIPE)` before
  `deleteSecrets()` + poweroff.
- `vendor/lenos/docs/features.md` (line 56) now documents the complete flow (3-second eUICC budget,
  system-uid requirement, skipped carrier notification, owner-credential-only enrolment) and references
  the three patches; the earlier "honest limits" claim of an unerased eSIM is gone.

Everything above remains accurate as the porting reference; no open items in this section.

---

## 4. Require unlocking for sensitive quick tiles (special investigation #3) — DONE in lenOS

**What it does.** QS tiles that can change security-relevant state (airplane mode, hotspot, NFC, data,
etc.) cannot be toggled from the lock screen; only a small allow-list of harmless tiles works while
locked. Interacting with a blocked tile instead prompts unlock.

**GrapheneOS implementation** (`packages/SystemUI/src/com/android/systemui/qs/`):
- `QSTileImpl.java` — new default method `public boolean isAllowedWhenLocked(Action action)`
  (default `false`) and the click path in `handleAction()` wraps the action in
  `postQSRunnableDismissingKeyguard()` when the tile is not allowed while locked. All three action kinds
  (click / long-click / secondary click) are gated.
- `QSHost.java` + `QSHostAdapter.kt` — expose
  `com.android.systemui.statusbar.policy.KeyguardStateController` to tiles (append-only interface change).
- 11 tile overrides returning `true` (identical allow-list to what lenOS landed): `BatterySaverTile`,
  `ColorCorrectionTile`, `ColorInversionTile`, `DeviceControlsTile`, `FlashlightTile`,
  `FlashlightTileWithLevel`, `NightDisplayTile`, `QRCodeScannerTile`, `ReduceBrightColorsTile`,
  `RotationLockTile`, `UiModeNightTile`.

**lenOS status — DONE (faithful).** `frameworks_base/0004-lenos-qs-unlock-gating.patch` (287 lines) now
implements exactly this design: `QSTileImpl` hunks (`isAllowedWhenLocked` default + `handleAction` gate,
patch lines ~54/~95), the same 11 tile overrides (patch lines 122–281, incl. the Kotlin
`DeviceControls`/`FlashlightTileWithLevel` overrides) and the `QSHost`/`QSHostAdapter` accessor. The
earlier lenOS mechanism (toast + spec allow-list of {flashlight, camera toggle}) is gone.

**Deviations vs GrapheneOS:** none material found; the tile set matches GrapheneOS's.
`KeyguardStateController` and `postQSRunnableDismissingKeyguard` already exist in LineageOS 23.2's
SystemUI/IActivityStarter. **Size: S** (single module). **API/version risk: none.**
**Verdict: shipped/done.**

---

## 5. Network permission toggle

**What it does.** Turns `INTERNET` into a user-visible runtime permission with a per-profile toggle:
when disabled, the app gets no direct *and no indirect* network access (including access through
same-profile helper apps/OS APIs), `localhost` is also guarded, and the OS *pretends the network is
down* (APIs report a connectivity failure, scheduled jobs avoid running) instead of surfacing
permission errors. Enabled by default; the package installer shows the toggle in the install
confirmation UI.

**GrapheneOS implementation:**
- `core/res/AndroidManifest.xml:2348` — `INTERNET` is `dangerous|instant`
  (LineageOS 23.2 `:2212` still `normal|instant`).
- Kernel/eBPF enforcement: netd's per-UID traffic permission map driven by Connectivity's
  `PermissionMonitor`. **AOSP 16/LineageOS 23.2 already ships this machinery** — verified in
  `packages/modules/Connectivity` on `lineage-23.2`:
  `service/src/com/android/server/connectivity/PermissionMonitor.java:1037-1039`
  (`TRAFFIC_PERMISSION_INTERNET`), `:1290-1296` (`sendAppIdsTrafficPermission`), plus the
  `BpfNetMaps` uid-rule machinery. The stock enforcement is compatibility-gated: the
  `NETWORK_BLOCKED_WITHOUT_INTERNET_PERMISSION` compatibility change (id 333340911) is
  `@EnabledAfter(targetSdkVersion = 36)` in the LineageOS 23.2 tree, while in GrapheneOS branch 17 no
  fwb hit for that change id remains (their release gate has passed — enforcement effectively
  unconditional). GrapheneOS's added value is the *policy* (runtime, user-revocable, enabled by default
  for all apps) plus the UX layers, not a new firewall.
- UI/UX: PermissionController group mapping (`PermissionMapping.kt`, `KotlinUtils.kt:` the NETWORK group
  and per-app toggle), Settings app per-app screen (works automatically once the manifest marks the
  permission dangerous), install-time toggle in the PackageInstaller app (GrapheneOS forks
  `platform_packages_apps_PackageInstaller`; the AOSP app does not set this), and the "pretend the
  network is down" behavior in Connectivity (status/callbacks/job scheduling).
- Second enforcement layer: GrapheneOS also prevents apps without the permission from proxying network
  access through APIs/components that do have it (the binder/TRAFFIC_PERMISSION_INTERNET mapping — the
  stock `PermissionMonitor` already tracks per-appId traffic permissions, so this converges with AOSP).

**Port surface for lenOS.** 4 projects, heavily pre-built by AOSP 16:
1. `frameworks/base` — 1-line manifest change (INTERNET → `dangerous|instant`).
2. `packages/modules/Connectivity` — enable the enforcement for all target SDKs (drop/overify the
   `@EnabledAfter(36)` gate), ensure the "network down" reporting paths; small–moderate.
3. `packages/modules/Permission` (PermissionController) — group/icon/strings and special-casing;
   small.
4. `packages/apps/PackageInstaller` — install-time toggle; small (same app family as §14's
   "preserve disabled state").
netd/eBPF: no work (already in the Android 16 tree). sepolicy: no delta identified in GrapheneOS
branch 17 beyond stock.
**Risks:** shared-UID apps and system components that use INTERNET per UID; instant-permission
semantics; apps that require network for first-run but haven't been granted; jobs/captive portal
testing. Moderate test matrix (Wi-Fi/cellular/tethering, DNS, jobs, installer UI).
**Size: M–L** (multi-repo, but mostly wiring AOSP's existing feature to a visible permission).
**Verdict: port now — top value** alongside the sensors permission (§6); the single most visible
privacy feature after the ones already shipped.

---

## 6. Sensors permission

**What it does.** A new `OTHER_SENSORS` runtime permission covering every sensor not already behind an
existing runtime permission (accelerometer, gyroscope, compass, barometer, thermometer, …). Denied →
the app receives **zeroed data** and no events; a dismissible notification informs the user when an app
tries to use blocked sensors. Enabled by default (compat); an ExtSettings default can turn it off for
user-installed apps.

**GrapheneOS implementation:**
- Manifest: `core/res/AndroidManifest.xml:2053-2063` — `OTHER_SENSORS` declared
  `dangerous` with its own permission group.
- Enforcement: `frameworks/native` → `services/sensorservice/SensorService.cpp:2540-2583`
  (`OTHER_SENSORS` check; uids below `AID_APP_START` exempt; apps targeting ≤ P get legacy behavior;
  denied → zeroed values, no events; also hooks `onDeniedSpecialRuntimePermissionOp` into
  `package_native`), `libs/sensor/Sensor.cpp:67` (permission plumbing for the client path).
- Permission plumbing/UI: PermissionController mappings (`PermissionMapping.kt`, `KotlinUtils.kt`) so
  the permission shows up as a runtime toggle in Settings; `MissingSpecialRuntimePermissionNotification.java`
  (`services/core/java/com/android/server/ext/`, 164 lines) posts the "app tried to access sensors" note;
  `AUTO_GRANT_OTHER_SENSORS_PERMISSION` ExtSettings default (already seeded in lenOS `0006`).

**Port surface for lenOS:** `frameworks/native` (SensorService.cpp + Sensor.cpp: ~60 lines of checks),
`frameworks/base` (manifest constant + permission group + `package_native` note path),
`packages/modules/Permission` (mapping/strings/icon), plus Settings strings for group name.
No kernel work; works for all sensors since the gate is in sensor service, not the driver.
**Risks:** "zeroed data" must also cover `SensorDirectChannel`/batch paths (upstream covers them);
per-SoC differences minimal because the permission gate is Central.
**Size: L** (native service + permission module + framework glue). **API/version risk: low**
(manifest/permission infrastructure is stable; the native patch is Android 16-compatible in
GrapheneOS's 16 branch too).
**Verdict: port now — top value** (second to network permission). High user visibility, clean
enforcement point, already half-seeded in lenOS's ExtSettings constants.

---

## 7. Two-factor fingerprint unlock (duress PIN as second-factor PIN)

**What it does.** Optional second factor for biometric unlock: after a successful fingerprint match,
a separate "second factor PIN" (a different credential, not the primary passphrase) must be entered to
complete unlock. Failure counts toward the normal attempt limit. The duress PIN is honoured here too —
entering it as the second factor triggers the duress wipe path (§3). This lets users keep a strong
primary passphrase with convenient fingerprint+PIN unlock.

**GrapheneOS implementation (credential-domain model — the big one):**
- `LockDomain` (PRIMARY/SECONDARY) is a *new abstraction* in the locksettings stack:
  `services/core/java/com/android/server/locksettings/` — `LockSettingsService.java`,
  `SyntheticPasswordManager.java` (per-domain synthetic passwords, separate SPM blobs),
  `LockSettingsStorage.java`, `LockSettingsStateListener.java`, and even the duress code
  (`DuressPasswordHelper.java` references `LockDomain.Secondary` so the duress PIN is a valid
  *secondary* credential). 41 files reference `LockDomain` in the GrapheneOS tree (incl. tests).
- SystemUI: biometric/credential prompt flow for the secondary domain.
- Settings app: `ChooseBiometricSecondFactorPin.java`, `BiometricSecondFactorPinPreferenceController.java`,
  `BiometricSecondFactorSaveAndFinishWorker.java`, `BiometricSecondFactorPinSettings.java`,
  `ChangeBiometricSecondFactorPinPreferenceController.java`, `DeleteBiometricSecondFactorPinPreferenceController.java`,
  plus `ChooseLockGeneric.java`, `FingerprintSettings.java`, `ScreenLockSettings.java` integration.
- **LineageOS 23.2 has no `LockDomain` at all** (single-credential SPM). Backporting the domain model is
  an invasive change to synthetic-password storage, upgrade paths, and every lock-settings caller.
  There is no shortcut that preserves the "duress PIN counts as second factor" property without the
  domain split.
**Size: XL (new subsystem backport; hundreds to >1000 lines across fwb + Settings + SystemUI).**
**API/version risk: high** (credential storage formats, SP upgrade path, Weaver/StrongBox interaction;
GrapheneOS iterated on this over multiple releases).
**Verdict: port later (not now).** Very valuable for PIN-scramble/duress users, but it must be done
after the smaller duress eSIM work and with careful device testing; it is the largest item in the
"port later" bucket together with storage/contact scopes and the Play compatibility layer.

---

## 8. Secure Paste (clipboard read gating)

**What it does.** Apps cannot read clipboard content *set by other apps* unless allowed; they can
always read content they set themselves. Control is per-app with a global default for third-party
apps (`ALLOW_CLIPBOARD_READ_BY_DEFAULT`), integrated into the text-selection toolbar, IME, accessibility
and keyboard-shortcut paths. Android only shows a notice *after* a read; Secure Paste makes it opt-in.

**GrapheneOS implementation:**
- Setting: `core/java/android/ext/settings/ExtSettings.java:103-104` →
  `Settings.Global.ALLOW_CLIPBOARD_READ_BY_DEFAULT` (**the constant is already seeded by lenOS patch
  0006**), per-app switch `android/ext/settings/app/AswAllowClipboardRead.java`.
- Per-app state: `GosPackageStateFlag` bits `ALLOW_CLIPBOARD_READ_NON_DEFAULT`(31), `ALLOW_CLIPBOARD_READ`(32),
  `SUPPRESS_CLIPBOARD_ACCESS_DENIAL_NOTIF`(33) — part of scopes-style per-package state (see §14).
- Enforcement: `services/core/java/com/android/server/clipboard/ClipboardAccess.java` (imports
  `android.content.pm.GosPackageState`, computes a read policy per package/UID) called from
  `clipboard/ClipboardService.java:709-710` (`getClipboardReadPolicyForPackage`); denial notification
  path + suppression bit.
- UI glue: `packages/SystemUI` `SecurePasteSelectionToolbar.kt` (34), `SecurePasteAccessibility.kt` (61),
  `SecurePasteKeyEventHandler.kt` (51), `SecurePasteToolbar.kt` (27) — small classes that keep the
  standard paste affordances working when reads are blocked; `frameworks/base/tests/SecurePasteTests/`.

**Port surface for lenOS — staged:**
1. *Global-only stage (M):* read `ExtSettings.ALLOW_CLIPBOARD_READ_BY_DEFAULT` (or a lenOS key) in
   `ClipboardService`, block cross-app reads for third-party apps, keep same-app reads; add the SystemUI
   toolbar helpers. No new per-package state subsystem.
2. *Full stage (L–XL):* per-app overrides need either GrapheneOS's `GosPackageState` subsystem
   (heavier, shared with scopes/memtag/etc.) **or** reuse the already-present AOSP AppOps op
   `OP_READ_CLIPBOARD` (`AppOpsManager.java:1027` in LineageOS 23.2) as the per-app switch — a
   deliberate deviation that avoids the GOS state machinery.
**API/version risk: low** for stage 1; moderate for stage 2 depending on the path chosen.
**Verdict: port now (stage 1), port later (per-app).** Stage 1 closes the "any focused app reads
clipboard" hole cheaply; the AppOps route looks like the pragmatic lenOS-flavoured implementation.

---

## 9. Delayed "Allow" action on permission + ADB prompts

**What it does.** The positive/allow button in system permission dialogs and the ADB USB-authorization
prompt is disabled for one second, so neither accidental taps nor tapjacking-style app tricks can
confirm a grant instantly.

**GrapheneOS implementation:**
- Permission dialogs: `packages/modules/Permission/PermissionController/.../GrantPermissionsViewHandlerImpl.kt:411`
  — `button.postDelayed(action, 1000)`.
- ADB prompt: `packages/SystemUI/.../usb/UsbDebuggingActivity.java:110`
  — `getMainThreadHandler().postDelayed(() -> allowButton.setEnabled(true), 1000)`.

**LineageOS 23.2 status:** neither file contains a delay (raw-file check of `lineage-23.2`:
`UsbDebuggingActivity.java` has no `postDelayed`; `GrantPermissionsViewHandlerImpl.kt` only uses
`TransitionManager`). Port = two ~3-line patches.
**Size: S (< 10 LOC total).** **API/version risk: none.** **Verdict: quick win — port now.**

---

## 10. USB-C port control (USB-C and pogo pins)

**What it does.** Five modes for the USB-C port (and, on devices with pogo pins, those too):
Off, Charging-only, Charging-only when locked (default), Charging-only when locked except before first
unlock, and On. After locking (or immediately, depending on mode), new USB connections are blocked and
existing ones are ended; the data lines are disabled **at the hardware level via the USB controller**,
USB-C alternate modes (DisplayPort) are disabled, plus a kernel/OS-level second layer.

**GrapheneOS implementation:**
- Setting: `core/java/android/ext/settings/UsbPortSecurity.java` (20 lines) — mode constants +
  `IntSysProperty("persist.security.usb_mode", …)`, default `MODE_CHARGING_ONLY_WHEN_LOCKED`
  (`MODE_ALL_PORTS_ENABLED` on debuggable builds). Comment: *"keep in sync with USB HAL implementations
  that check this sysprop during init"* — the HAL/kernel side is where the hardware-level blocking lives.
- OS logic: `services/core/java/com/android/server/policy/keyguard/UsbPortSecurityHooks.java` (424 lines)
  — registers port-change receivers, tracks keyguard state (`onKeyguardShowingStateChanged`,
  `keyguardDismissedAtLeastOnce` for the "-AFU" mode), two-phase handling for new connections
  (`setDenyNewUsb2`), `setSecurityStateForAllPorts`, and the HAL interception
  `onHalEnableUsbDataSignal()`.
- HAL plumbing: `services/usb/java/com/android/server/usb/UsbService.java:429` (`init`) and `:1226`
  (`updateSetting`); `hal/port/UsbPortAidl.java:367` (OS intercepts `IUsb.enableUsbData` and lets the
  hook block/defer) and `:458` (`enableUsbDataWhileDocked` rejected when supported); same in
  `UsbPortHidl.java:277,:325`.
- Feature gate: `core/res/res/values/config.xml:7970` — `config_usbPortSecuritySupported=false`,
  enabled by device overlay where the vendor HAL/kernel implements the contract.

**SM7635 feasibility.** Two layers:
1. *OS side (portable, ~L):* setting + hooks + HAL interception. Works only if Nothing/Qualcomm's USB
   HAL implements AOSP's `IUsb.enableUsbData` (AIDL USB HAL method that AOSP's `UsbManager.setUsbDataSignalingEnabled`
   also uses) and the kernel honors it. That must be prototyped on a device: check the running HAL
   service's interface version and `adb shell dumpsys usb`. If the HAL supports it, we get
   "charging-only"-style data-line blocking while booted (probably not the persisted-ACROSS-boot sysprop
   contract, which requires HAL init support for `persist.security.usb_mode`).
2. *Hardware layer (not feasible):* disabling alternate modes / PD data lines in the controller and
   reading `persist.security.usb_mode` during HAL init are vendor firmware features. Nothing's stock
   firmware controls this; we cannot add it. Pogo pins: the Phone (3a)/3a Pro has none, so that half of
   the feature is N/A.

**Size:** OS-side port L (mostly the 424-line hooks file + HAL plumbing); hardware part infeasible.
**API/version risk:** low for OS side; the risk is entirely vendor-HAL behavior.
**Verdict: not feasible now (full feature); partial prototype possible (see step 1).** Put on the
"research" list; do not promise GrapheneOS-equivalent guarantees.

---

## 11. FBE filename padding 16 → 32 bytes

**What it does.** Per-profile file-based-encryption policies use 32-byte (instead of the stock 16-byte)
padding for encrypted filename lengths, reducing the information leaked by the length of directory
entries.

**GrapheneOS implementation** — a genuine one-liner, in `system/extras` (GrapheneOS fork
`platform_system_extras` @ branch 17), file `libfscrypt/fscrypt.cpp:247-248`:

```cpp
// GrapheneOS has always used the maximum 32 byte padding.
options->flags |= FSCRYPT_POLICY_FLAGS_PAD_32;
```

vold calls libfscrypt's `ParseOptions()` when creating the per-profile encryption policies
(`vold/FsCrypt.cpp:330` for `s_data_options`, `:372` for per-storage options), so changing libfscrypt
changes the policy flags of every policy created afterwards.

**Port surface for lenOS:** patch `system/extras` (libfscrypt) — effectively 2 lines + comment. The
device fstab (`device/nothing/asteroids/init/fstab.default:59`,
`fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0`) does not need changes;
padding is a policy flag, not an fstab option.
**Caveats:** applies to *newly created* encryption policies — on already-installed devices the existing
metadata keys keep 16-byte padding until factory reset/re-encryption, so this is a "new installs and
post-wipe" win (still worth shipping now; it also affects each new user profile created later).
No interaction with Qualcomm ICE (`inlinecrypt_optimized`/`wrappedkey_v0` are orthogonal flags).
**Size: S (~2 LOC + platform repo patch).** **API/version risk: none** (kernel 6.6 supports PAD_32;
AOSP's default is only PAD_16 for compatibility).
**Verdict: quick win — port now.**

---

## 12. Improved VPN leak blocking / always-on VPN hardening

**What it does.** Closes the known classes of "traffic escapes the VPN while 'Block connections without
VPN' is on" holes:
1. System-resolver DNS queries leaking to network DNS when the VPN is down (lockdown race).
2. DNS connections to the VPN's own DNS servers happening outside the tunnel.
3. Processes bypassing the VPN with multicast packets (directly or via kernel IGMP/MLD helper paths).
4. mDNS/"`*`" discovery via the system NSD Manager under VPN lockdown.
5. Multicast leaking into *another profile's* VPN tunnel.
6. A kernel/system-call interface-bind bypass in the eBPF firewall.

**GrapheneOS implementation (evidence from the full-history clones):**
- netd (`GrapheneOS/platform_netd`, branch 17 with history):
  - `82da9204` *"fix DNS leak in VPN lockdown mode when VPN is down"* — `server/NetworkController.cpp`,
    +3/−2 lines: when all VPNs are down, point the system resolver at the *blocked* network instead of
    the default network's DNS, so the resolver can't leak. Small, surgical.
  - `dcef5ccb` *"add multicast firewall"* — `server/MulticastFirewallController.cpp` (135) +
    `.h` (56) + `Controllers.cpp/.h` wiring (+8/+2) + tests (56); ~267 insertions total. Prevents
    sending multicast through a VPN tunnel the process isn't allowed to access (cross-profile leak) and
    is the base for the lockdown multicast filtering.
  - `d57ea8dc` *"stop dropping router advertisements received on VPN interface"* — +5 lines in the
    multicast controller: keep RAs working when the interface is under the lockdown firewall.
  - `40c47da2` *"Fix IPV4/6 privacy leak"* — `server/SockDiag.cpp` +8/−4 (flushes/handles sockets so
    IPv6 privacy addresses can't be used as a cross-network identifier; pairs with Wi-Fi privacy).
- DnsResolver (`GrapheneOS/platform_packages_modules_DnsResolver`, `DnsResolver-h`):
  - `890fe28` *"Exclude VPN and mobile data from .local resolution"* — `.local`/mDNS lookups skip VPN and
    cellular interfaces (backs the NSD behavior).
- NSD Manager: `modules_Connectivity` `service-t/src/com/android/server/NsdService.java:3452-3456` —
  `ConnectivityUtil.isRegularAppWithLockdownVpnEnabled(mContext, uid)` → returns `null`/refuses
  discovery for regular apps while a lockdown VPN is enabled. Helper:
  `frameworks/base/core/java/android/ext/ConnectivityUtil.java:41` (exported as a module-lib API
  `isRegularAppWithLockdownVpnEnabled(Context, int)` — small, easy to port).
- Vpn app-level: GrapheneOS's `Vpn.java` diff vs LineageOS 23.2 (`/tmp/opencode/vpn_diff.txt`) is
  mostly version drift (Android 17 refactors); the functional delta is that GrapheneOS no longer
  auto-unsets an always-on VPN whose package is currently "unsupported" (so the setting survives safe
  mode / temporary unavailability). Settings screens (`ConfigDialog`, `AppManagementFragment`,
  `VpnUtils`) are identical — the "Always-on VPN"/"Block connections without VPN" toggles are already
  available for all VPN apps by default in AOSP 16, so that part of the feature is *already present* in
  LineageOS 23.2.
- The "eBPF interface-bind bypass" (#6) was **not located** in the netd branch-17 scan; it may be a
  kernel-side fix (their kernel fork). Assume infeasible for us without kernel work.

**Port surface for lenOS:**
1. netd: cherry-pick/port `82da9204` (tiny), `dcef5ccb` + `d57ea8dc` (multicast firewall ~215 core
   LOC + tests), `40c47da2` (tiny) — our netd clone/PoC tree shows these apply against 23.2 with minor
   fuzz.
2. DnsResolver: port `890fe28` (or rely on it already being in mainline AOSP 16 — check current
   `DnsResolver` tree; the commit *is* in AOSP history, so likely present).
3. `frameworks/base` `android.ext.ConnectivityUtil` helper + `modules_Connectivity` `NsdService`
   lockdown check (~30 LOC total, plus strings if we want a user message).
4. `frameworks/base` `Vpn.java` "don't unset unsupported always-on" hunk (~5 LOC).
**Risks:** netd patches touch the firewall/eBPF paths — test tethering, RAs on Wi-Fi, IPv6, multicast
apps (mDNS, discovery); the multicast controller is the largest piece and has upstream tests we can use.
**Size: M** (netd + Connectivity + fwb; 4 small commits + 1 medium). **API/version risk: low**
(netd internal API stable across 16/17 where not renamed — check `Controllers` wiring).
**Verdict: port now.** This is a high-value, well-scoped hardening set; the netd commits are the
authoritative core of "improved VPN leak blocking" and are absent from LineageOS 23.2 (netd there is
stock AOSP).

---

## 13. Vanadium / WebView replacement options

**What it is.** GrapheneOS's hardened Chromium fork ("Vanadium") ships as both the system WebView
provider and the default browser, with MTE for the main allocator, type-based CFI, JIT disabled by
default with per-site toggle, content filtering, WebRTC IP handling policies, reduced UA/client hints,
remote services cut to component-update + DoH connectivity checks, etc. (full feature list on the
features page lines 495-587 of the dump).

**Not source-portable to lenOS in any patch-like way:**
- Building Vanadium = building Chromium with the GrapheneOS patch set (multi-GB, hours-long builds,
  Chromium version churn, their own release pipeline).
- WebView provider integration additionally needs the package/signature allow-listing that AOSP uses
  (`config_webview_packages`-style provider config), a build/update pipeline for the APK, and acceptance
  that the browser and WebView version must track line together.
- The GrapheneOS releases (browser APK, WebView APK, PDF viewer) are signed with the GrapheneOS release
  keys: an official prebuilt can be *installed as a user app* (browser) from their app repository, but
  *cannot legally/reliably become the system WebView* of a lenOS build (WebView provider signature
  trust is per-build; sideloading Vanadium's WebView requires relaxing the provider allow-list and
  accepting out-of-band updates).

**Pragmatic options for lenOS (rough effort, no source port):**
1. **Keep AOSP WebView + vendor a privacy browser** (current path): continue with LineageOS's browser
   stack; optionally recommend/install Cromite (privacy-hardened Chromium fork with its own release
   channel and WebView builds) — *M effort, no OS integration*, still not Vanadium.
2. **Bundle a prebuilt non-Vanadium Chromium WebView** (Cromite WebView or AOSP's Trichrome from
   LineageOS prebuilts — the latter is what ships now): *S–M*, no hardening delta beyond stock.
3. **Build Vanadium from source inside lenOS** — *XL, ongoing maintenance*, unrealistic for this
   project unless adopting GrapheneOS's entire Chromium fork/pipeline.
**Verdict: app-level bundle / port later — not source-portable.** If lenOS wants Vanadium-class
hardening, the realistic recommendation is (3) only as a long-term project, or (1)/(2) with Cromite as
the interim browser while keeping the stock WebView. Nothing in the rest of this inventory depends on
Vanadium.

---

## 14. Smaller ExtSettings-backed items and the remaining feature sweep

This section covers the remaining categories from the features page (ToC coverage is complete: every
heading is mapped here, in §5–§13, in §16–§18 or in the already-written sections). "Seeded" = the
ExtSettings *constant* already exists in lenOS patch 0006 but nothing enforces it yet.

### 14.1 Attack-surface / radio items

| Item | GrapheneOS implementation | lenOS port | Size | Verdict |
|---|---|---|---|---|
| Wi-Fi / Bluetooth / NFC auto-off timers | fwb `services/core/java/com/android/server/ext/WifiAutoOff.java` (141), `BluetoothAutoOff.java` (125), `DelayedConditionalAction.java` (122); keys `Settings.Global.wifi_off_timeout` / `bluetooth_off_timeout` (`Settings.java:14470/:14474`), NFC via the NFC app | Add the two service classes (NFC needs the Nfc app side), Settings dropdown rows; **constants seeded** in 0006 | S–M | port now (cheap attack-surface win) |
| USB attach attack surface | see §10 | see §10 | L | partial only |
| Native debugging (ptrace) block for bundled apps + per-app toggles + notification | ExtSettings `ASW` switches (`android/ext/settings/app/Asw*`), `GosPackageStateFlag.BLOCK_NATIVE_DEBUGGING*` (6-8), notification helper; enforcement partially via SELinux (GrapheneOS sepolicy) | constant present in 0006; enforcement needs their sepolicy/SELinuxFlags work | M–L | port later |
| Dynamic code loading toggles (memory/storage/WebView) | `GosPackageStateFlag.RESTRICT_*` (9-16) + `services/.../ext/DynCodeLoadingUtils.java` (116) + notification; enforcement in bionic/seccomp | constants present; **no-op without bionic/ART/seccomp work** | XL | not feasible now (toggles alone useless) |
| Exec spawning / hardened_malloc / MTE / BTI+PAC | bionic + `hardened_malloc` + build/ART/kernel work; toggles in ExtSettings/`GosPackageStateFlag` (17–23, 29–30) | platform-wide runtime replacement | XL+ | not feasible now (see §17) |
| JIT disabled base OS / dynamic code blocked for base OS | ART + seccomp work | none | XL | not feasible now |
| "User-created directories not listable without storage permission" | MediaProvider FUSE path (`jni/FuseDaemon.cpp`, `do_readdir_common` ~:2053); exact GOS hunk not pinned in the clone (verify) | fwb/MediaProvider test to reproduce, then patch | M | port later (verify) |
| Screenshot shutter sound toggle | SystemUI `ScreenshotSoundPolicy.kt`/`ScreenshotSoundController.kt`: GOS drops AOSP-16's `screenshotForceShutterSound` aconfig gate and gates the non-forced sound on `Settings.System.SOUND_EFFECTS_ENABLED` (`ScreenshotSoundController.kt:86-89`); forced-shutter regions unchanged (`MediaActionSound.mustPlayShutterSound()` identical) | fwb SystemUI refactor (~40 LOC) | S–M | port later (cosmetic) |
| Location privacy indicator | SystemUI `HeaderPrivacyIconsController.kt` + `PrivacyItemController.locationAvailable`; enables indicator for all location APIs (not just GNSS) | port the controller enablement + fixes | M | port later (nice-to-have) |

### 14.2 Privacy / identifier items

| Item | GrapheneOS implementation | lenOS port | Size | Verdict |
|---|---|---|---|---|
| Private screenshots (EXIF) | Timestamp/timezone tags gated on `ExtSettings.SCREENSHOT_TIMESTAMP_EXIF` (`ImageExporter.java:513`); Software tag removed — LineageOS 23.2 sets `exif.setAttribute(ExifInterface.TAG_SOFTWARE, "Android " + Build.DISPLAY)` (`los_ImageExporter.java:520`), GrapheneOS tree has no such line | 2 hunks in fwb SystemUI + Settings row; constant seeded | S | quick win |
| Sensitive notifications hidden by default / passwords hidden while typing | Confirmed: `packages/SettingsProvider/res/values/defaults.xml:170` — `def_lock_screen_allow_private_notifications` = **false** in GrapheneOS (LineageOS 23.2 same file `:170` = **true**), seeded in `DatabaseHelper.java:1642-1643` (fresh DB) and `:2245-2246` (upgrade); passwords-hidden default already exists in AOSP 16 (`def_text_show_password` empty) | flip our default to false (affects new installs/users; existing user choices kept) | S | quick win |
| Storage Scopes (alternative to storage permissions) | `GosPackageStateFlag.STORAGE_SCOPES_ENABLED = 0`; scope model `core/java/android/app/StorageScope.java`; fake permission grants `services/core/java/com/android/server/pm/GosPackageStatePermissions.java`; MediaProvider enforcement `src/com/android/providers/media/StorageScopesHooks.java` (`callingIdentity.getStorageScopes()`); app hooks `core/java/com/android/internal/app/StorageScopesAppHooks.java`; UI in Permission module `.../permissioncontroller/sscopes/` (Activity/Fragment/Utils + `strings_sscopes.xml`) + Settings `AppStorageScopesPreference.kt` | requires the GosPackageState core first (`GosPackageState*` + `PackageManagerHooks`), then scope model + MediaProvider hooks + Permission/Settings UI | L–XL | port later (after GosPackageState) |
| Contact Scopes (alternative to the Contacts permission) | `CONTACT_SCOPES_ENABLED = 5`; API/storage `core/java/android/ext/cscopes/ContactScopesApi.java` + `ContactScopesStorage.java`, `core/java/com/android/internal/app/ContactScopes.java`; provider filtering `ContactsProvider/src/.../ScopedContactsProvider.java` + `ContactScopesUiHelper.java` (design notes `ContactScopes.md`); UI `.../permissioncontroller/cscopes/ContactScopesActivity.kt` + Settings `AppContactScopesPreference.kt` | same GosPackageState dependency + ContactsProvider fork | L | port later (after GosPackageState) |
| Battery charge limit (80 %) | `core/java/android/ext/power/BatteryChargeLimit.java` — `CHARGE_LEVEL=80`, `Settings.Global.BATTERY_CHARGE_LIMIT`, gated by **`isGoogleDevice()`** (mechanism is Pixel-specific); Settings `BatteryChargingOptimizationPrefController/Fragment` | mechanism would need Nothing charger/kernel support; UI alone does nothing | S (stub), device support = L | not feasible now |
| LTE-only mode | Settings app `EnabledNetworkModePreferenceController.java` (LTE-only entry :655/:745-747/:831/:946-949), `PreferredNetworkModePreferenceController.java:222`, `NetworkModes.kt:28`; LineageOS 23.2 only has the mode mapping (:579/:669), no explicit LTE-only choice | Settings app patch + strings | S–M | port later (device/0004 already defaults 5G/LTE/3G, no 2G) |
| Cross-profile clipboard control | `android/ext/settings/CrossProfileClipboardAccessSettings.java`; read at `ClipboardService.java:1064/:1099` and `DragState.java:517` | fwb patch, per-profile setting | S–M | port later |
| Alt touchscreen mode | `android/ext/settings/AltTouchscreenMode.java`; used in `PhoneWindowManager.java:5549/:5643` (display state prop) | depends on touch controller/firmware behavior on SM7635 | M | port later / verify hardware |
| Removing auto location grant to system browsers | Helper `core/java/android/ext/BrowserUtils.java` (26 lines) exists; grant site not pinned in this scan (likely `DefaultPermissionGrantPolicy`) | verify, then small fwb patch | S–M | port later (verify) |
| PIN scrambling (incl. SIM PIN/PUK) + other SIM/eSIM protections | GrapheneOS base-view `setupPinScrambling` (SecureRandom shuffle + digit→view remap); keyguard reads the primary ExtSettings key, SIM PIN/PUK views read the SIM key; Settings UI via `com.android.settings.ext` controllers | **Done in the fidelity redo:** `frameworks_base/0008` (SystemUI) + `packages_apps_Settings/0001` (Settings: lock-picker switch, SIM-lock switch, controller infra) + primary default flipped ON in `frameworks_base/0006` (documented lenOS deviation — GrapheneOS ships it off). Old Lineage plumbing deleted (`PinScramblePreferenceController`, device/0005, lineage_sdk/0001). Duress is *not* accepted as a SIM PIN in GrapheneOS either (same upstream — nothing to port); duress wipes eSIM profiles (§3, done) | done | — | **done** |
| Prototype/EVT/PVT device warning | AMS `services/core/java/com/android/server/am/ActivityManagerService.java:6047-6081` (`ro.boot.secure_boot != PRODUCTION` → notification) | fwb + strings; note: on an unlockable Nothing device this fires as intended (gate on `ro.product.brand` if undesired) | S | quick win (consider gating) |
| UART debugging warning fix; bootloader/radio/boot partition version+fingerprint checks | Not located in this scan (Settings/About + device props) | verify separately | S–M | verify |
| Wireless alerts fully optional | `CellBroadcastReceiver` `res/values/config.xml:25` `show_presidential_alerts_settings=true` (LineageOS `false`) making the pref visible; `CellBroadcastChannelManager.java:283` (presidential `mAlwaysOn` commented out) so the pref actually controls delivery; `CellBroadcastAlertService.java:639` reads `KEY_ENABLE_CMAS_PRESIDENTIAL_ALERTS` | patch CellBroadcastReceiver (4 files, ~10 LOC) | S | quick win |
| CA removal (Chunghwa Telecom, Netlock) | `platform_system_ca-certificates` commit `14ad6bb` deletes `files/53a1b57a.0`, `files/60afe812.0`, `files/9d6523ce.0` | remove the same files; re-apply on each CA update | S | quick win |
| FLAG_IMMUTABLE log+warp instead of crash | fwb `core/java/android/app/PendingIntent.java:457-467`: logs the error and `return flags \| PendingIntent.FLAG_IMMUTABLE`; LineageOS `:444-465` throws | replace throw with log+warp | S | quick win |
| More precise system clock | fwb `TimeDetectorStrategyImpl.java:90`: drift warning threshold `SYSTEM_CLOCK_PARANOIA_THRESHOLD_MILLIS = 250` (LineageOS = 2000); the features page additionally cites the 2000 ms→50 ms *update* threshold (constant not re-located in this scan beyond the paranoia value) | lower the constants | S | quick win |
| Longer passwords | `DevicePolicyManager.MAX_PASSWORD_LENGTH`: GrapheneOS 128, LineageOS 23.2 = **64** (`DevicePolicyManager.java:3812`) | 1-line constant + audit `PasswordMetrics`/UI assumptions | S | quick win |
| More secure fingerprint unlock (5 attempts) | fwb `services/core/java/com/android/server/biometrics/sensors/fingerprint/hidl/LockoutFrameworkImpl.java`: `MAX_FAILED_ATTEMPTS_LOCKOUT_PERMANENT = 5` (LineageOS = 20 with 30 s timeouts) | 1-line constant | S | quick win |
| Package installer preserves disabled state | GrapheneOS forks `platform_packages_apps_PackageInstaller` and sets `SessionParams#setApplicationEnabledSettingPersistent()` on updates; the API exists in LineageOS 23.2 (`PackageInstaller.java:3949`, honored by the session/installer) | patch the AOSP PackageInstaller app | S | quick win |
| Compressed APEX disabled | build/product config | verify flag name | S | quick win (verify) |
| "Always-on VPN"/"Block connections without VPN" default | Already the AOSP 16 behavior (toggles available for all VPN apps); GrapheneOS delta is only "don't unset unsupported always-on" — see §12 | 1 hunk | S | port now (with §12) |

### 14.3 User/profile items

| Item | GrapheneOS implementation | lenOS port | Size | Verdict |
|---|---|---|---|---|
| More profiles (32 = 31+guest) | fwb `core/res/res/values/config.xml:3288` (32); LineageOS raw = 1 + Lineage vendor overlay = 4 | device/vendor RRO override `config_multiuserMaximumUsers` | S | quick win |
| End session (logout) without a device manager | AOSP 16 already has `logoutUser`; GrapheneOS enables the UI path and disables the lockscreen logout button (`KeyguardIndicationController` `if (false && …)`); `UserLogoutInteractor.kt` near-identical (GOS adds `isPolicyManagerLogoutEnabled`) | Settings enablement + small fwb check | S–M | port later |
| Disabling app installation for secondary users | Settings users screens (standard device-management restriction exposed to the owner) | Settings app patch | M | port later |
| Install available apps | `UserSystemPackageInstaller.java` (fwb) + config **not enabled in AOSP/Pixel** per GrapheneOS; enable + UI | fwb config + Settings UI | M | port later |
| Notification forwarding (cross-profile) | Not located in this fwb scan (verify their Settings/notification service changes) | verify | M–L (est.) | port later (verify) |
| User-installed apps can be disabled | Settings app enables "Disable" for non-system apps (framework support exists); GrapheneOS hardened the flow | Settings app patch | S–M | port later |
| Encrypted backups | LineageOS already ships Seedvault; GrapheneOS carries a hardened fork with security fixes | sync the fixes into our Seedvault (Lineage fork) | S–M | port later |
| Log viewer + user-facing crash reporting | fwb `services/core/java/com/android/server/ext/` bundle (17 files, 2722 lines total: `TombstoneHandler.java` 468, `DropBoxMonitor.java` 339, `SystemJournalNotif.java` 103, `SystemErrorNotification.java` 43, `BgDexoptUi.java` 171, `IntentReceiver.java` 103, `PackageManagerHooks.java` 226, `SeInfoOverride.java` 84, `AppCompatConf.java` 195, `AppSwitchNotification.java` 227, …) + Settings log-viewer UI | log viewer alone: M; full crash reporting: L | M–L | port later |

### 14.4 Anti-persistence, App-source and app-level items

| Item | GrapheneOS implementation | lenOS port | Size | Verdict |
|---|---|---|---|---|
| fs-verity enforcement for out-of-band APK updates (`PackageVerityExt`) | install-time + boot-time verified metadata, downgrade prevention, parsing-cache disabled | design work; not pinned in this scan | L | port later |
| System-app versionCode downgrade loophole | PM install + boot checks | as above | M–L | port later |
| Kernel LTS + hardening | their kernel forks + patches | we build `kernel/nothing/sm7635` from LineageOS source, but porting GrapheneOS's kernel hardening (zero-on-free, canaries, SCS/PAC, 4-level page tables, module signing) is a large kernel project with no firmware support | XL+ | not feasible now |
| Compressed-APEX / firmware-security reporting items | see 14.2 | verify | S–M | verify |
| Broad carrier support (CarrierConfig2) | their carrier-config conversion scripts + stripped anti-user configs (tethering provisioning, 2G forbidding, OMA-DM) | run their generator on the carrier DBs we can obtain; ship the generated configs; strip anti-user bits | M–L | port later |
| Sandboxed Google Play / Android Auto | GmsCompatConfig + compatibility layer (their own repos; apps sandboxed, no special privileges) | a project of its own; no AOSP-path port | XL | app-level bundle (later) |
| GrapheneOS app repository client | their client + server | alternatives exist (Obtainium/F-Droid); not source-portable | M | app-level bundle |
| Auditor | app + attestation service (attestation.app) | installable APK on any OS; strong value only with their service; not source-portable | S (bundle) | app-level bundle |
| Camera / PDF viewer / Setup Wizard | standalone apps | Camera & PDF viewer are standalone APKs (usable as a bundle); Setup Wizard is tied to their framework UX | S (bundle) / XL (wizard) | bundle later |
| Authenticated NTP + disabling network time | their NTP server with A-E; toggle | lenOS sets NTP server default via 0002; authenticated NTP needs a server (not portable); AOSP supports disabling time sync natively | S | done/not portable |

### 14.5 Other-features sweep (misc ToC items)

| Item | GrapheneOS implementation | lenOS port | Size | Verdict |
|---|---|---|---|---|
| Wi-Fi privacy parity | per-connection MAC randomization (new networks default to `RANDOMIZATION_ALWAYS`), per-network DHCP hostname off by default (`SendDhcpHostname2` tag rename ignores stock-written values); DHCP client state flushed on reconnect (netd), IPv6 privacy-address kernel fixes | **Done (redo):** `wifi/0001-privacy-mac-and-dhcp-defaults` ports GrapheneOS's exact change set; DHCP-state flush + IPv6 fixes not pinned in this scan — verify against netd/kernel | S–M (verify) | defaults done; verify the rest |
| Closed device identifier leaks | restriction tightening for legacy-target apps + exec spawning removes mitigation secrets as identifiers | exec spawning = §17 runtime cluster; legacy-target restrictions not pinned in this scan | M (verify) | port later (verify) |
| Improved sandboxing | SELinux + seccomp-bpf policy hardening, app and WebView renderer sandbox paths | program-level (see §17); no itemized patch surfaced | XL | infeasible now |
| More complete patching | fast kernel LTS point releases + missed-patch backports | operational: kernel workstream (§17) + release cadence, not a patch | n/a | process (not a patch) |
| Seamless automatic updates + rollback | their update client/server; rollback via A/B when first boot fails | LineageOS updater covers the basics; server-side parity is infra, not code | S (policy) | not a code port |
| Hardened build/signing infrastructure | release-engineering practice | adopt independently of the codebase | n/a | out of scope (process) |
| Minimal bundled apps | only essential apps integrated; no bundling partnerships | mechanism already exists (`LENOS_STRIP_PACKAGES`, vendor_lineage/0001); extend the strip list as policy | S | port now (policy step) |
| Keyboard suggestions off by default | "personalized keyboard suggestions based on gathering input history are disabled by default" (privacy-by-default) | seat not pinned (IME/dictionary setting); AOSP exposes the opt-out — flip the default | S (verify) | port later (verify) |
| Dialer call recording | GrapheneOS Dialer: recordings under `Recordings/Call Recordings`, no region restrictions or tone | LineageOS Dialer fork differs; app-level port + telecom checks | M | port later (app) |
| Firmware security visibility | version/configuration verification reporting inconsistencies + debug features enabled (companion to the bootloader/radio/boot-partition checks row in 14.2) | same verify bucket as that row | S–M (verify) | port later (verify) |

**Coverage note:** every features-page ToC item is covered somewhere in this document — mapping:
§5 (network), §6 (sensors), §7 (2FA), §8 (secure paste), §9 (delayed allow), §10 (USB-C),
§11 (FBE padding), §12 (VPN), §13 (Vanadium), §2 (auto reboot, done), §3 (duress, done),
§4 (QS gating, done), §15–§18 (rankings + audit), and the tables above for everything else.

---

## 15. Ranked: the next 15 ports (shipped items excluded)

Excluded as already done: ExtSettings infrastructure (`fwb/0006`), auto-reboot (`system_core/0001` +
`fwb/0003`), QS unlock gating (`fwb/0004`), duress backend + eSIM wipe (`fwb/0005`+`0007`,
`frameworks_opt_telephony/0001`). Sizes assume one experienced developer with the device to test on.

| # | Item | Size | Repos touched | One-line value |
|---|---|---|---|---|
| 1 | Network permission | M–L | fwb, Connectivity, Permission, PackageInstaller | user-revocable INTERNET with "network is down" semantics; AOSP 16 already ships the eBPF machinery, so this is mostly policy + UI |
| 2 | Sensors permission | L | fwn, fwb, Permission (+Settings) | zeroed-out accelerometer/gyro/compass/etc. for apps — the largest remaining privacy hole after network |
| 3 | VPN leak-blocking set | M | netd, Connectivity, fwb | 4 surgical netd fixes (DNS/RA/multicast/SockDiag) + NSD-under-lockdown — hardens the always-on VPN feature we already ship |
| 4 | Secure Paste, stage 1 (global default) | M | fwb (+Permission/Settings UI) | cross-app clipboard reads off by default; staging avoids the GosPackageState backport (per-app later via AppOps) |
| 5 | FBE filename padding 32 B | S | system/extras | one-line policy change in libfscrypt; metadata-length privacy (new installs / post-wipe) |
| 6 | Wi-Fi/Bluetooth auto-off timers | S–M | fwb (+Settings; NFC variant in the Nfc app) | radios power down after idle; constants already seeded in `fwb/0006` |
| 7 | Fingerprint lockout after 5 attempts | S | fwb | parity with GrapheneOS (LineageOS still allows 20 before permanent lockout) |
| 8 | MAX_PASSWORD_LENGTH 128 | S | fwb | one-line; supports duress/passphrase users who hit the 64 limit |
| 9 | Package installer preserves disabled state | S | packages/apps/PackageInstaller | disabled apps stay disabled after updates; AOSP API already present in 23.2 |
| 10 | Delayed "Allow" (permission + ADB) | S | Permission, SystemUI | 1-second anti-tapjacking gate, absent from LineageOS 23.2 |
| 11 | Wireless alerts fully optional | S | CellBroadcastReceiver | presidential alerts become opt-out (config + channel-manager + alert-service respect the pref) |
| 12 | FLAG_IMMUTABLE log+warp | S | fwb | mutable PendingIntent logs instead of crashing third-party apps (GrapheneOS behavior) |
| 13 | Screenshot EXIF defaults | S | fwb (SystemUI) | drops timestamp/timezone tags and the Software tag; constant seeded |
| 14 | Clock paranoia threshold 250 ms | S | fwb | GrapheneOS 250 ms vs LineageOS 2000 ms drift warning; cheap precision/privacy parity |
| 15 | More profiles (32) | S | vendor/device overlays | multiuser max 4 → 32; no framework work (fscrypt/quota paths already support it) |

**Runners-up (all small):** removal of Chunghwa Telecom + Netlock CAs (S), prototype-device warning (S),
LTE-only mode UI in Settings (S–M), GNSS/SUPL settings toggles (S–M), SIM-PIN scrambling (S–M),
cross-profile clipboard setting (S–M), sensitive-notification default (S), "remove auto location
grant to system browsers" (S–M, verify the grant site first).

**Sequencing suggestion.** Land the §16 quick-win batch first (zero design risk). Then the VPN set
(§12) and Secure Paste stage 1 (§8). Network (§5) and sensors (§6) each deserve their own release and
test pass. The FBE padding change (§11) only affects new encryption policies, so ship it whenever — but
pair it with a note that existing devices keep 16-byte padding until factory reset.

---

## 16. Quick wins (< ~50 LOC each)

All are GrapheneOS ports unless marked otherwise; each is independently shippable.

| Change | Where | Effort | Reference |
|---|---|---|---|
| Fingerprint permanent lockout 20 → 5 | fwb `biometrics/.../fingerprint/hidl/LockoutFrameworkImpl.java` | 1 line | GOS `:51` = 5; LOS `lineage-23.2` `:51` = 20 — **done** (`fwb/0009`) |
| Max password length 64 → 128 | fwb `DevicePolicyManager.MAX_PASSWORD_LENGTH` | 1 line | GOS 128; LOS `DevicePolicyManager.java:3812` = 64 — **done** (`fwb/0009`) |
| Clock drift warning 2000 → 250 ms | fwb `timedetector/TimeDetectorStrategyImpl.java` | 1 line | GOS `:90` = 250; LOS `:89` = 2*1000 — **done** (`fwb/0010`). The features page also advertises a 50 ms system-clock *update* threshold — not pinned to a constant in this scan (search the timedetector/alarm paths when implementing) |
| FBE padding 16 → 32 | `system/extras` `libfscrypt/fscrypt.cpp` | 1–2 lines | GOS branch 17 `:247-248` (`FSCRYPT_POLICY_FLAGS_PAD_32`) |
| Delayed "Allow" buttons | Permission `GrantPermissionsViewHandlerImpl.kt` + SystemUI `usb/UsbDebuggingActivity.java` | 2 hunks (~6 LOC) | GOS `:411` and `:108-110`; LOS has neither |
| Wireless alerts optional | CellBroadcastReceiver `res/values/config.xml` + `CellBroadcastChannelManager.java` (+ verify `CellBroadcastAlertService` read) | ~5 lines | GOS config `:25` true vs LOS false; GOS channel manager `:283` has the presidential `mAlwaysOn` commented out |
| Remove Chunghwa Telecom + Netlock CAs | `system/ca-certificates` `files/` | delete 3 files | GOS commit `14ad6bb` deletes `files/53a1b57a.0`, `files/60afe812.0`, `files/9d6523ce.0` |
| Package installer preserves disabled | `packages/apps/PackageInstaller` | ~5 lines | `SessionParams#setApplicationEnabledSettingPersistent()` exists in LOS 23.2 (`PackageInstaller.java:3949`) |
| Screenshot EXIF cleanup | fwb SystemUI `ImageExporter.java` | ~5 lines + Settings row | GOS gates timestamp on `ExtSettings.SCREENSHOT_TIMESTAMP_EXIF` (`:513`); LOS writes `TAG_SOFTWARE = "Android " + Build.DISPLAY` (`los_ImageExporter.java:520`) |
| Sensitive notification content hidden by default | fwb `packages/SettingsProvider/res/values/defaults.xml` | 1 line | GOS `def_lock_screen_allow_private_notifications` = false (`:170`) vs LOS 23.2 true; seeded at `DatabaseHelper.java:1642-1643` / `:2245-2246` (new installs/users only) — **done** (`fwb/0012`) |
| More profiles 32 | vendor/device RRO `config_multiuserMaximumUsers` | 1 value | GOS `core/res/res/values/config.xml:3288`; LOS raw 1 + Lineage overlay 4 — **done** (`device/0007`) |
| FLAG_IMMUTABLE log+warp | fwb `core/java/android/app/PendingIntent.java` | ~10 lines | GOS `:457-467` logs + returns `flags \| FLAG_IMMUTABLE`; LOS `:444-465` throws — **done** (`fwb/0011`) |
| Prototype/EVT device warning | fwb AMS + strings (optional; gate on `ro.product.brand` to avoid it firing on every unlockable Nothing device) | ~30 lines | GOS `ActivityManagerService.java:6047-6081` |

---

## 17. Not feasible without kernel, firmware or infrastructure work

| Item | Why it is out of reach now | What we can do instead |
|---|---|---|
| Exploit-mitigation program: `hardened_malloc`, exec spawning, MTE-for-apps defaults, BTI/PAC userspace hardening, JIT-disabled base OS, base-OS dynamic-code-loading block | These are bionic/ART/kernel/toolchain projects, not patch ports; the ExtSettings/ASW toggles registered in `fwb/0006` are config only and stay inert by design | Keep the toggles hidden; revisit only if lenOS adopts a runtime-hardening workstream |
| Kernel LTS + hardening | We build `kernel/nothing/sm7635` from LineageOS source, so kernel patches are *possible*, but GrapheneOS-grade kernel hardening (zero-on-free, canaries, hardened slab, module signing) targets their supported Pixels and is a project of its own against the vendor baseline | Track as a separate workstream; nothing in this inventory requires it |
| USB-C port control (full semantics) | Hardware data-line disable, alternate-mode (DisplayPort) block and boot-time `persist.security.usb_mode` enforcement live in the vendor USB HAL/kernel/firmware; Nothing controls them | OS-side prototype only if the SM7635 HAL implements AOSP `IUsb.enableUsbData` (verify with VINTF/`dumpsys usb`); see §10 |
| Battery charge limit (80 %) | GrapheneOS's mechanism is gated to Google devices (`BatteryChargeLimit.isGoogleDevice()`) and depends on Pixel charger/kernel support | Nothing's stock firmware has a vendor battery-protection feature, but it is not exposed via an AOSP path we can call; skip unless the kernel exposes a charge-stop node |
| Sandboxed Google Play + Android Auto + GmsCompatConfig | GrapheneOS's compatibility layer (their own repositories and app) — a separate large project; Android Auto support is tied to the sandboxed Play integration | Not applicable to lenOS's current app stack; revisit only if a Play-compat layer is ever adopted |
| Network location service | GrapheneOS runs a network-location proxy on their infrastructure; the OS hooks are portable but the backend is not | Keep GNSS-only location; optionally port the settings toggles (see §14.2) |
| Authenticated NTP | Requires GrapheneOS's NTP service; authentication is server-side | Point the NTP default at a trustworthy server (already a config knob in `fwb/0002`) |
| Auditor / verified attestation workflow | The app can be installed on any device, but the workflow needs their attestation service | Recommend the APK in documentation if desired |
| Verified boot / firmware trust improvements | Locked to Nothing's bootloader, AVB keys and firmware update chain | Document the bootloader-locking trade-offs |
| Vanadium as a source port | Whole-Chromium build + release pipeline (see §13) | App-level bundle decision (Cromite or similar), not a patch |
| UART-debugging warning fix; bootloader/radio/boot-partition version+fingerprint checks | Not located in the branch-17 scan in this pass | Verify before classifying — they may turn out to be small device/settings patches |

---

## 18. Deviations audit: the 23 lenOS patches vs GrapheneOS

Method: all rows read directly from `vendor/lenos/patches/` during this audit; GrapheneOS references are
from the branch-17 clones (`fwb-full`, `system_core`, `sepolicy`, `Settings`, `Permission`, …) plus raw
`GrapheneOS/*` fetches. Note: this series now has **23** patches (the fidelity redos plus the first
quick-win batch: `fwb/0009`–`0012` and `device/0007`; earlier notes said 18). Verdicts: **Faithful**
(line-level port; deltas only environmental), **Deliberate** (lenOS choice — keep), **Original** (no
GrapheneOS equivalent), **Plumbing** (build/device mechanics).

| Patch(es) | GrapheneOS equivalent | Deviation found | Verdict |
|---|---|---|---|
| `fwb/0001` SSAID rotate-on-reinstall | None (branch-17 SettingsProvider has no install-generation logic; AOSP relies on the SSAID row being dropped on uninstall, which a fast reinstall with uid reuse can miss) | Mixes `PackageInfo.firstInstallTime` into the SSAID HMAC as an install generation; toggle `lenos_ssaid_rotation_enabled` (default 1). Upgrades stay stable because `firstInstallTime` only moves on reinstall | **Original** — keep; document the app-compat effect (new SSAID after reinstall) |
| `fwb/0002` first-boot defaults | GrapheneOS spreads hardened defaults across `config_ext.xml`, module configs and provider seeds | Centralized `def_lenos_*` resources loaded in `DatabaseHelper#loadGlobalSettings`; keys: Private DNS mode/specifier, NTP server, captive-portal mode. The Wi-Fi MAC force-flag seed was removed in the Wi-Fi redo — Wi-Fi privacy defaults are now a GrapheneOS-faithful per-network default in `packages_modules_Wifi/0001`. The stock values in the patch preserve AOSP behaviour; the product overlay supplies hardened values | **Deliberate** — keep; the overlay is the place to review strictness |
| `fwb/0003` + `system_core/0001` auto-reboot | GrapheneOS init-based design (`trigger_shutdown`, dedicated `auto_reboot_ctl_prop`, `KeyguardServiceDelegate` hook) | (a) callback calls `HandlePowerctlMessage("reboot")` vs GOS `trigger_shutdown("reboot")` — both init-internal reboot paths, equivalent; (b) SELinux: no dedicated type — stock `sys.` → `system_prop` prefix rule applies (LOS `private/property_contexts:23`; GOS `property_contexts:29` declares `auto_reboot_ctl_prop`), so the context is coarser but no sepolicy patch is needed and system_server has system_prop write access; (c) hooked in A16's `KeyguardStateMonitor.onShowingStateChanged` vs GOS's KeyguardServiceDelegate (same keyguard events); (d) no call-in-progress deferral — same as GOS | **Faithful** — two benign environment deltas; revisit (b) only if sepolicy is tightened |
| `fwb/0004` QS unlock gating | GrapheneOS design (`QSTileImpl` gate + 11-tile allow-list + QSHost accessor) | None found | **Faithful** |
| `fwb/0005` duress credentials | GrapheneOS duress | Same class set, same `LockSettingsStorage` key (`duress_credentials`), same verify-result hook, same owner-credential enrolment rules | **Faithful** |
| `fwb/0006` ExtSettings | GrapheneOS `android.ext.settings` registry | Trimmed to the subset used; several constants are seeded but inert (AUTO_GRANT_OTHER_SENSORS_PERMISSION, WIFI/BLUETOOTH/NFC_AUTO_OFF, SCREENSHOT_TIMESTAMP_EXIF, ALLOW_CLIPBOARD_READ_BY_DEFAULT, RESTRICT_*_DYN_CODE_LOADING, FORCE_APP_MEMTAG, ALLOW_DISABLING_HARDENING_VIA_APP_COMPAT_CONFIG). PIN scramble is *not* inert anymore (fwb/0008 + Settings/0001). One deliberate default change: `SCRAMBLE_LOCKSCREEN_PIN_LAYOUT_PRIMARY` defaults to `true` (GrapheneOS ships `false`; lenOS hardening choice, commented in the patch; SIM layout inherits it) | **Deliberate** — keep trim + documented scramble default; do not surface UI for the other inert constants before enforcement lands |
| `fwb/0007` + `frameworks_opt_telephony/0001` eSIM duress wipe | GrapheneOS eSIM duress (same flag constant, SYSTEM_UID gate, carrier-notification suppression) | None found; the AIDL change is internal and the public `resetMemory` keeps its signature (hidden overload) | **Faithful** |
| `device/0001` lenOS product | n/a | Adds `lenos_asteroids.mk`; strips Gallery2 via `LENOS_STRIP_PACKAGES`, disables AudioFX | **Plumbing** |
| `device/0002` Wi-Fi privacy hardening | No exact GrapheneOS counterpart | Enterprise Wi-Fi without certificate validation disallowed (stock Nothing overlay sets the AOSP "STRONGLY RECOMMENDED false" value to true); default tether SSID "Nothing Phone (3a)" → "AndroidAP" | **Deliberate** — strict improvements; keep |
| `device/0003` SUPL off | GrapheneOS keeps A-GPS via their SUPL proxy with user toggles | Disables SUPL entirely (`gps.supl_host` emptied) | **Deliberate/stricter** — slower first fix, no A-GPS; revisit as a toggle if GNSS UX matters |
| `device/0004` default network without 2G | GrapheneOS exposes an LTE-only setting and strips carrier configs that forbid disabling 2G, but does not change the device default | `ro.telephony.default_network` 26 → 28 (26 = `NETWORK_MODE_NR_LTE_GSM_WCDMA`, includes 2G; 28 = `NETWORK_MODE_NR_LTE_WCDMA`, no 2G — verified against branch-17 `RILConstants.java:226/232/238`) | **Deliberate/stricter** — user-changeable in Settings; keep |
| `device/0005` + `lineage_sdk/0001` PIN scramble default | n/a — superseded by the GrapheneOS port | **Both patches deleted** in the fidelity redo: the Lineage scramble implementation they configured was replaced by GrapheneOS's (`frameworks_base/0008` + `packages_apps_Settings/0001`); the lenOS default-ON now rides `ExtSettings` (`fwb/0006`, commented deviation) | **Removed** — no longer part of the series |
| `device/0006` device name | None | Default `def_device_name` / `def_device_name_simple` → "Android" (Bluetooth / Wi-Fi Direct / hotspot display name) | **Original** — keep |
| `wifi/0001` Wi-Fi privacy defaults | GrapheneOS's `packages/modules/Wifi` change set: `RANDOMIZATION_ALWAYS = 100` as the default for new networks, `shouldUseNonPersistentRandomization` early-true for it, DHCP hostname off by default (`mIsSendDhcpHostnameEnabled` uninitialized), `SendDhcpHostname` → `SendDhcpHostname2` XML rename so stock-written values are ignored after upgrade, no secure-only backfill (their `XmlUtil.java` carries the "disabled by default for all Wi-Fi networks on GrapheneOS" comment) — an earlier inventory note claiming GrapheneOS leaves this stock was wrong | Ported exactly (4 files: `WifiConfiguration`, `WifiConfigManager`, `WifiConfigurationUtil`, `XmlUtil`). The earlier lenOS approximation — a global force-flag clamp (`Settings.Global.non_persistent_mac_randomization_force_enabled` seeding, persistence API, RRO bool) — was **deleted**: it silently overrode explicit per-network user choices | **Faithful (redo)** — keep |
| `fwb/0009` credential hardening | GrapheneOS `LockoutFrameworkImpl.java:51` (`MAX_FAILED_ATTEMPTS_LOCKOUT_PERMANENT = 5`) and `DevicePolicyManager.java:3950` (`MAX_PASSWORD_LENGTH = 128`) | Values ported verbatim; the 30 s timed lockout and the timed-attempt count (5) were already identical | **Faithful** — keep |
| `fwb/0010` clock-drift warning | GrapheneOS `TimeDetectorStrategyImpl.java:90` (`SYSTEM_CLOCK_PARANOIA_THRESHOLD_MILLIS = 250`) | Value ported verbatim (AOSP `2 * 1000`) | **Faithful** — keep |
| `fwb/0011` PendingIntent immutability warp | GrapheneOS `PendingIntent.checkPendingIntent2`: on a missing mutability flag under the enforced S+ compat change, log `Log.e(TAG, msg)` and return `flags \| FLAG_IMMUTABLE` instead of throwing; all four creation paths (`getActivity`, `getActivities` loop, `getBroadcast`, `getService`/foreground service) assign the returned flags | Ported verbatim, including the both-flags-still-throws behaviour. The lenOS comment in the patch notes the intent; no functional delta | **Faithful** — keep |
| `fwb/0012` lockscreen notification privacy | GrapheneOS `packages/SettingsProvider/res/values/defaults.xml:170` (`def_lock_screen_allow_private_notifications` `false`) | One line flipped in place (AOSP `true`); seeded through `DatabaseHelper` for new installs/users exactly as GrapheneOS does — no RRO or seed indirection | **Faithful** — keep |
| `device/0007` multiuser limit | GrapheneOS `core/res/res/values/config.xml:3288` (`config_multiuserMaximumUsers = 32`) | Same value, carried in the vendor overlay the device already uses (framework raw default is 1; the Lineage device overlay pinned 4). `config_enableMultiUserUI` is already `true` in that overlay, so both knobs the AOSP deprecation note asks for are set | **Faithful** — keep |
| `vendor_lineage/0001` strip packages | GrapheneOS edits its product app lists directly | Parameterized `LENOS_STRIP_PACKAGES` filter applied in three `vendor/lineage/config/*.mk` files | **Plumbing** — equivalent intent, cleaner mechanism |

**Conclusion.** No accidental behavioral deviations were found, and the approximations surfaced by the
redo audit have been replaced by faithful ports (auto-reboot init, QS gating, Wi-Fi privacy defaults,
PIN scrambling). Of the 23 patches: **14 are faithful GrapheneOS ports** — auto-reboot pair, QS gating,
duress, eSIM wipe pair, Wi-Fi privacy defaults (`wifi/0001`), SystemUI PIN scramble (`fwb/0008`), the
Settings scramble UI (`packages_apps_Settings/0001`, single-credential-domain adaptation) and the first
quick-win batch (`fwb/0009`–`0012`, `device/0007`, all value/line-level) — the
auto-reboot pair carries the two benign environment deltas listed above, the Settings port the
LockDomain removal; **5 are deliberate lenOS choices** (first-boot defaults, ExtSettings trim + PIN
scramble default ON, Wi-Fi enterprise hardening, SUPL-off, no-2G default) — several stricter than
anything GrapheneOS ships (enterprise Wi-Fi, SUPL-off, scramble default); **2 are lenOS-original**
(SSAID rotation, device name); **2 are build/device plumbing**. The re-done ports are line-level
faithful; earlier inventory text that called them (or the Wi-Fi privacy defaults) deviations is
superseded by this audit.

**Watch list (revisit conditions):**
1. Auto-reboot SELinux context — if sepolicy is ever tightened, add a dedicated `auto_reboot_ctl_prop`
   type like GrapheneOS instead of relying on the `sys.` prefix rule.
2. SUPL-off — if GNSS first-fix UX complaints appear, convert `device/0003` into a user toggle
   (GrapheneOS-style) rather than reverting the default.
3. Seeded-but-inert ExtSettings constants — do not expose UI for auto-off timers, sensors auto-grant,
   clipboard default, memtag/DCL toggles until their enforcement lands (§14). PIN scramble is the
   exception (wired, UI shipped).
4. PIN scramble default-ON — the one lenOS hardening deviation with a plausible accessibility
   trade-off (the keypad relayouts on every setup). The per-user switch exists; if feedback is bad,
   flip the `ExtSettings` default back to GrapheneOS's `false` instead of patching SystemUI.
5. Keep `vendor/lenos/docs/features.md` synced as the §16 quick wins land (each adds a patch; features.md
   currently references the right files for duress/eSIM/scramble).
6. SSAID rotation — the only lenOS-original behavior with plausible app-compat fallout; keep it
   documented and easily switchable (the toggle already exists).
