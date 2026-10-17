# lenOS 1.0.0 — feature matrix

Base: LineageOS 23.2 (`asteroids` = Nothing Phone (3a) / (3a) Pro).
All features below are **source-complete**: patches, resources and tests are in
this repository. None of it has been verified on a running device yet — the
first build/flash gets recorded in `../PROGRESS.md`.

## First-boot defaults (Settings.Global)

Seeded once by `frameworks/base/0002-lenos-first-boot-defaults.patch` from
resources that `rro/LenosSettingsProviderOverlay` hardens (stock values stay
AOSP-compatible in the upstream source). Every value stays a normal user
setting afterwards; lenOS never rewrites a user change.

| Setting | Value | Effect |
|---|---|---|
| `non_persistent_mac_randomization_force_enabled` | `true` | per-connection (non-persistent) Wi-Fi MAC randomization; networks see a new MAC every connection |
| `private_dns_mode` | `hostname` | strict DNS-over-TLS |
| `private_dns_specifier` | `dns.quad9.net` | Quad9 DoT |
| `NTP_SERVER` | `pool.ntp.org` | no Google time service (framework fallback lives in `rro/LenosFrameworksOverlay`) |
| `captive_portal_mode` | `1` | prompt — never silently logged-in to portals |

Other first-boot hardening from the same overlay: Bluetooth off, no Wi-Fi
wakeup scanning, no "open networks available" notifications, location off,
USB mass storage off, no lock-screen QR scanner shortcut.

## Identity / correlation

| Feature | Where | Notes |
|---|---|---|
| SSAID (Android ID) rotates on reinstall | `frameworks/base/0001` | same app reinstall gets a new ID; setting `Settings.Secure`/user-visible to disable; units tested |
| Generic device name by default | `device_nothing_asteroids/0006` | "Android" instead of "Nothing Phone (3a)" — the device name is the Bluetooth adapter / Wi-Fi Direct name neighbours see; user can rename |
| Generic tether SSID | `device_nothing_asteroids/0002` | `AndroidAP`, no model name |
| Build fingerprint / product identity | *untouched by design* | keeps app compatibility, attestation, Nothing factory tooling |

## Network

| Feature | Where | Notes |
|---|---|---|
| Wi-Fi MAC randomization (per connection) | RRO + first-boot default | force-enabled via `WifiConfigManager`'s existing flag |
| Strict Private DNS (DoT, Quad9) | first-boot default | breaks networks that block DoT or need captive-portal DNS; user-changeable |
| NTP without Google | first-boot default + frameworks RRO | `pool.ntp.org` is a central pool; SNTP is unauthenticated either way |
| Connectivity checks without Google | `rro/LenosNetworkStackOverlay` | `cp.cloudflare.com/generate_204`; the check still uses a third party (Cloudflare), it is just not Google (see limits) |
| DHCP hostname blocked by default | `packages_modules_Wifi/0001` | DHCP requests carry no hostname on open or secure networks; toggle in the lenOS app; persisted in `Settings.Global.lenos_wifi_send_dhcp_hostname_restriction` |
| Insecure enterprise Wi-Fi configs blocked | `device_nothing_asteroids/0002` | Settings/SetupWizard cannot configure "no certificate validation" enterprise networks |
| Default radio mode without 2G | `device_nothing_asteroids/0004` | `ro.telephony.default_network=28,28` (NR+LTE+WCDMA); no GSM/2G fallback, user can change |
| SUPL / AGPS network assistance off | `device_nothing_asteroids/0003` | no location data to a SUPL server; slower GPS first fix (trade-off, documented) |
| Modem/radio logging and snapshot props off | `config/lenos.mk` | `persist.vendor.radio.*` logging off, small radio log buffer, `persist.traced.enable=0` |

## Lock, data and recovery

| Feature | Where | Notes |
|---|---|---|
| Auto reboot to before-first-unlock (BFU) | `system_core/0001` + `frameworks_base/0003` + `frameworks_base/0006` | GrapheneOS port: init owns a `CLOCK_BOOTTIME_ALARM` timer driven through the `sys.auto_reboot_ctl` property; system_server forwards keyguard showing-state changes (timeout while locked, `on_device_unlocked` on unlock). Requests before the first unlock are ignored, a running timer is not restarted by relocking, and expiry performs a normal reboot, so the FBE keys stay out of memory until the next unlock. `Settings.Global.settings_reboot_after_timeout` (GrapheneOS key, 18h default via `android.ext.settings`, 0 = off, 10min–3 days) with UI in the lenOS app |
| Quick settings require unlock | `frameworks_base/0004` | GrapheneOS port: every tile action (click, secondary click, long click) goes through `QSTileImpl#handleAction`. While a secure keyguard is up, non-allow-listed tiles do nothing until the user authenticates — the keyguard bouncer is shown and the action runs only after a successful unlock. A locked device cannot toggle radios/connectivity (e.g. airplane mode to break remote tracking). Allow-list as in GrapheneOS: flashlight (both variants), QR scanner, color inversion/correction, Night Light, reduce bright colors, dark theme, rotation lock, battery saver, device controls |
| Duress PIN/password | `frameworks_base/0005` + app UI | entering either duress credential at any credential prompt (lock screen, Settings confirm, shell) destroys the KeyMint storage keys + Secretkeeper secrets — the user data becomes cryptographically inaccessible — and powers off. Only failed verifications are checked and only typed PIN/password credentials, so the real lock credential can never trigger it. Setting/checking/deleting requires the owner credential; the stored form is a scrypt-stretched hash, never the credential. Limitation: GrapheneOS's eSIM profile erasure (`EuiccWipe`) is not ported |

## Framework infrastructure

| Feature | Where | Notes |
|---|---|---|
| `android.ext.settings` (GrapheneOS) | `frameworks_base/0006` | `Setting`/`BoolSetting`/`IntSetting`/`StringSetting` plus the system-property variants, and `ExtSettings` with the GrapheneOS key set (auto-reboot timeout, Wi-Fi/BT/NFC auto-off, clipboard read, sensor permission grant, screenshot EXIF, PIN scramble, DCL/memtag defaults). Defaults are `core/res/res/values/config_ext.xml` resources and `Settings.Global`/`Settings.Secure` keys with GrapheneOS-identical literals, so later ports can drop in without redefining storage. Entries whose enforcement code is not ported yet are inert |

## Apps and UI

| Item | Status |
|---|---|
| Minimal app set | `Gallery2` stripped via `LENOS_STRIP_PACKAGES` (`vendor_lineage/0001`), AudioFX off (`TARGET_EXCLUDES_AUDIOFX`), MP3/Music app (`Twelve`) kept for now |
| Jelly browser | **kept** for 1.0; Cromite/WebView replacement is still under investigation (see limits) |
| `LenosSecurity` app | ships with: Wi-Fi DHCP hostname toggle, PIN-scramble state, auto-BFU timer (init backend), duress PIN/password UI (framework service), status card |

## Not in the 1.0 series

Anything not listed above (sensors permission, Secure Paste, delayed allow
buttons, LTE-only toggle, 2nd PIN, vold FBE filename padding, safe recovery,
signed OTA/updater, reproducible builds, custom AVB key) is
**not implemented yet**.

## Honest limits

* **The modem/baseband is untouched.** Proprietary firmware still runs and can
  still leak. Nothing in this build changes that; airplane mode is the only
  real radio kill.
* **Connectivity checks still contact a third party.** Cloudflare replaces
  Google; the traffic metadata still goes somewhere central. `captive_portal_mode=1`
  only controls portal auto-login. Self-hosting the endpoint is possible later
  via the same RRO.
* **Strict DoT (Quad9) is a central service** and breaks on networks that
  block DoT. Users can switch to opportunistic/off in Settings.
* **No SUPL means slower GPS first fixes** (minutes outdoors, longer indoors);
  GNSS itself still works.
* **DHCP hostname restriction blocks the per-network user request too** —
  the restriction overrides the per-network "send hostname" preference on
  purpose. Re-enable in the lenOS app if a network needs the hostname.
* **Device name "Android" is what Settings > About shows** until the user
  renames it. The stock model string is still visible in adb/property contexts
  (fingerprint stays stock by design).
* **Location is off by default** (mode 0). Emergency calls still take the
  network E911 path; on-device GNSS/aGPS is off until the user enables
  location. Carrier/network location is unaffected by this default.
* **Auto reboot to BFU interrupts connectivity until the next unlock.** When
  the timer fires the device reboots; telephony/notifications stay off until
  the user unlocks again (emergency calls work at BFU). As in GrapheneOS the
  timer is not deferred for a call in progress; it only arms after the first
  unlock, so a device still sitting at BFU is never rebooted. The app offers
  off / 10 minutes … 3 days. Deviation: the property write uses the generic
  `system_prop` SELinux context instead of GrapheneOS's dedicated
  `auto_reboot_ctl_prop` type — system_server is allowed either way; a
  dedicated type needs a `system/sepolicy` project in the series.
* **Quick settings gating is not user-configurable in 1.0** and does nothing
  on devices without a secure lock. Allow-listed non-sensitive tiles
  (flashlight, display controls, rotation lock, battery saver, device
  controls, QR scanner) still work; everything else opens the unlock prompt
  (the keyguard bouncer) and only runs after authentication. The allow-list is
  GrapheneOS's, so the camera toggle is no longer a lock-screen exception.
* **The duress wipe is destructive by design and not yet device-verified.**
  It deletes the KeyMint storage keys and Secretkeeper secrets (cryptographic
  erase), then powers off — there is no undo. It is opt-in: nothing happens
  until the user sets a duress PIN/password with the owner credential. eSIM
  profiles are **not** erased (GrapheneOS erases them; this port does not).
  The app warns "do not test on this phone"; only test when a full wipe is
  acceptable.
* **Jelly (WebView-based browser) still ships.** It is the Lineage default and
  gets WebView security updates from the system; replacing it with Cromite and
  updating WebView are separate work items.

## Verification checklist (on the first flash)

See `build.md`. At minimum: `cmd overlay list --user 0` shows all three lenOS
RROs enabled, `settings list global | grep -E "private_dns|ntp|captive"` shows
the seeded values, `settings get global settings_reboot_after_timeout` shows
`64800000` (or unset — the ExtSettings default is 18h),
`getprop sys.auto_reboot_ctl` shows a timeout while the device is locked and
`on_device_unlocked` right after unlocking, the Wi-Fi hostname toggle changes
the persisted setting, and on the lock screen tapping a sensitive tile (e.g.
airplane mode) opens the unlock prompt without changing state until unlock,
while the flashlight tile keeps working.

Duress (destructive — run last, only when a wipe is acceptable): set a pair
with `cmd lock_settings set-duress-credentials --old <owner cred> --duress-pin
1234 --duress-password ''` (owner credential required), check the app's status
card flips to "set", then enter the duress PIN at the lock screen: the device
must delete the storage keys and power off, and the following boot must no
longer be able to decrypt the user data (expect the device to treat the data
partition as gone / factory reset).
