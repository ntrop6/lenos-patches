# lenOS progress log

One entry per working session. "Verified" = seen working on a booted device
(see `docs/build.md` checklist); everything else is source-complete only.

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
   permission, 2nd PIN, prototype/EVT warning, memory hygiene on lock,
   MediaProvider directory listing, package-installer disabled-state
   persistence (auto reboot to BFU, QS-tile gating, duress, LTE-only and the
   GNSS toggles are done).
8. First-boot checks for the new rows: LTE-only entry order/selection,
   Network assistance defaults = Off, SUPL/PSDS switch survives reboot, and
   `dumpsys location` shows no SUPL/PSDS servers while off.
