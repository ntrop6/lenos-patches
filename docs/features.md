# lenOS 1.0.0 — feature matrix

Base: LineageOS 23.2 (`asteroids` = Nothing Phone (3a) / (3a) Pro).
All features below are **source-complete**: patches, resources and tests are in
this repository. None of it has been verified on a running device yet — the
first build/flash gets recorded in `../PROGRESS.md`.

## First-boot defaults (Settings.Global)

Seeded once by `frameworks/base/0002-lenos-first-boot-defaults.patch` from
resources that `rro/LenosSettingsProviderOverlay` hardens (stock values stay
AOSP-compatible in the upstream source). Every value stays a normal user
setting afterwards; lenOS never rewrites a user change. Wi-Fi privacy
defaults are not seeded here — they are GrapheneOS-faithful per-network
defaults in `packages_modules_Wifi/0001` (see Network).

| Setting | Value | Effect |
|---|---|---|
| `private_dns_mode` | `hostname` | strict DNS-over-TLS |
| `private_dns_specifier` | `dns.quad9.net` | Quad9 DoT |
| `NTP_SERVER` | `pool.ntp.org` | no Google time service (framework fallback lives in `rro/LenosFrameworksOverlay`) |
| `captive_portal_mode` | `1` | prompt — never silently logged-in to portals |

Other first-boot hardening from the same overlay: Bluetooth off, no Wi-Fi
wakeup scanning, no "open networks available" notifications, location off,
USB mass storage off, no lock-screen QR scanner shortcut.

One Secure default is seeded through the stock resource instead
(`frameworks/base/0012`, GrapheneOS-faithful): the
`def_lock_screen_allow_private_notifications` default flips to `false`, so
new installs and new users start with `Settings.Secure
lock_screen_allow_private_notifications=0` — lock-screen notifications hide
their content until the user explicitly allows it.

## Identity / correlation

| Feature | Where | Notes |
|---|---|---|
| SSAID (Android ID) rotates on reinstall | `frameworks/base/0001` | same app reinstall gets a new ID; setting `Settings.Secure`/user-visible to disable; units tested |
| Generic device name by default | `device_nothing_asteroids/0006` | "Android" instead of "Nothing Phone (3a)" — the device name is the Bluetooth adapter / Wi-Fi Direct name neighbours see; user can rename |
| Generic tether SSID | `device_nothing_asteroids/0002` | `AndroidAP`, no model name |
| Build fingerprint / product identity | *untouched by design* | keeps app compatibility, attestation, Nothing factory tooling |

## Users and profiles

| Feature | Where | Notes |
|---|---|---|
| Up to 32 users/profiles | `device_nothing_asteroids/0007` | GrapheneOS parity: `config_multiuserMaximumUsers` raised 4 → 32 in the vendor overlay (the framework raw default is 1; the overlay is what ships). Each profile is its own encryption domain, so more profiles support stronger per-identity separation; the limit is a ceiling, not a default |

## Network

| Feature | Where | Notes |
|---|---|---|
| Wi-Fi MAC randomization (per connection) | `packages_modules_Wifi/0001` (GrapheneOS port) | new networks default to `RANDOMIZATION_ALWAYS` (per-connection, non-persistent MACs); a per-network strategy the user picks explicitly still wins |
| Strict Private DNS (DoT, Quad9) | first-boot default | breaks networks that block DoT or need captive-portal DNS; user-changeable |
| NTP without Google | first-boot default + frameworks RRO | `pool.ntp.org` is a central pool; SNTP is unauthenticated either way |
| Connectivity checks without Google | `rro/LenosNetworkStackOverlay` | `cp.cloudflare.com/generate_204`; the check still uses a third party (Cloudflare), it is just not Google (see limits) |
| DHCP hostname blocked by default | `packages_modules_Wifi/0001` (GrapheneOS port) | new networks never send the hostname (XML tag renamed `SendDhcpHostname` → `SendDhcpHostname2`, so values written by stock Android are ignored after upgrade); per-network opt-in in the Wi-Fi network details — no global override |
| VPN lockdown DNS leak fixed | `system_netd/0001` (GrapheneOS port) | the system resolver no longer marks every query as VPN-protected; with all VPNs down under "Block connections without VPN", DNS falls into the blocked path instead of the default network's resolvers (GrapheneOS `82da9204`) |
| VPN multicast firewall | `system_netd/0001` (GrapheneOS port) | drops multicast, IGMP and MLD in/out/through `tun+` interfaces, closing the cross-profile VPN side channel; inbound router advertisements stay allowed (GrapheneOS `dcef5ccb` + `d57ea8dc`) |
| NSD blocked under VPN lockdown | `packages_modules_Connectivity/0001` + `frameworks_base/0017` (GrapheneOS port) | regular apps get no NSD connector while an always-on VPN with lockdown is active, so mDNS discovery can't bypass the tunnel; system apps keep access (`android.ext.ConnectivityUtil`) |
| Always-on VPN survives temporary app loss | `frameworks_base/0018` (GrapheneOS port) | an unsupported (disabled/safe-mode) always-on VPN package no longer clears the setting, so the lockdown fail-safe stays configured and the VPN restarts when the package returns |
| Insecure enterprise Wi-Fi configs blocked | `device_nothing_asteroids/0002` | Settings/SetupWizard cannot configure "no certificate validation" enterprise networks |
| Distrusted root CAs removed | `system_ca-certificates/0001` | Chunghwa Telecom (HiPKI Root CA - G1, ePKI Root CA) and NetLock Arany (Class Gold) roots are deleted from the system trust store, matching GrapheneOS commit `14ad6bb` and Google's 2025 root-store distrust; user-installed CAs and app-pinned trust are unaffected (see limits) |
| Wireless alerts optional | `packages_apps_CellBroadcastReceiver/0001` (GrapheneOS port) | presidential alerts and (in Brazil) extreme alerts become user-toggleable: the presidential preference is visible, runs the config service and is read by the alert path (GrapheneOS commits "allow toggling presidential alerts" + "always allow disabling extreme alerts"). Every alert type stays enabled by default — nothing is silently forced on or off |
| Default radio mode without 2G | `device_nothing_asteroids/0004` | `ro.telephony.default_network=28,28` (NR+LTE+WCDMA); no GSM/2G fallback, user can change |
| SUPL / AGPS network assistance off | `device_nothing_asteroids/0003` | no location data to a SUPL server; slower GPS first fix (trade-off, documented) |
| Modem/radio logging and snapshot props off | `config/lenos.mk` | `persist.vendor.radio.*` logging off, small radio log buffer, `persist.traced.enable=0` |

## Lock, data and recovery

| Feature | Where | Notes |
|---|---|---|
| Auto reboot to before-first-unlock (BFU) | `system_core/0001` + `frameworks_base/0003` + `frameworks_base/0006` | GrapheneOS port: init owns a `CLOCK_BOOTTIME_ALARM` timer driven through the `sys.auto_reboot_ctl` property; system_server forwards keyguard showing-state changes (timeout while locked, `on_device_unlocked` on unlock). Requests before the first unlock are ignored, a running timer is not restarted by relocking, and expiry performs a normal reboot, so the FBE keys stay out of memory until the next unlock. `Settings.Global.settings_reboot_after_timeout` (GrapheneOS key, 18h default via `android.ext.settings`, 0 = off, 10min–3 days) with UI in the lenOS app |
| Quick settings require unlock | `frameworks_base/0004` | GrapheneOS port: every tile action (click, secondary click, long click) goes through `QSTileImpl#handleAction`. While a secure keyguard is up, non-allow-listed tiles do nothing until the user authenticates — the keyguard bouncer is shown and the action runs only after a successful unlock. A locked device cannot toggle radios/connectivity (e.g. airplane mode to break remote tracking). Allow-list as in GrapheneOS: flashlight (both variants), QR scanner, color inversion/correction, Night Light, reduce bright colors, dark theme, rotation lock, battery saver, device controls |
| PIN keypad scrambling | `frameworks_base/0008` + `packages_apps_Settings/0001` (+ default in `0006`) | GrapheneOS port: the keypad is shuffled with `SecureRandom` on every setup and hardware keys route through the digit→view map; the keyguard reads `ExtSettings.SCRAMBLE_LOCKSCREEN_PIN_LAYOUT_PRIMARY`, SIM PIN/PUK views read the inheriting `SCRAMBLE_SIM_PIN_LAYOUT`. lenOS deviation: default **on** (GrapheneOS ships it off; commented in `frameworks_base/0006`). UI: lock-screen picker switch + SIM-lock switch; the lenOS app toggles the same `Settings.Secure` key |
| Duress PIN/password | `frameworks_base/0005` + `0007`, `frameworks_opt_telephony/0001` + app UI | entering either duress credential at any credential prompt (lock screen, Settings confirm, shell) destroys the KeyMint storage keys + Secretkeeper secrets — the user data becomes cryptographically inaccessible — erases every eSIM profile and powers off. The eUICC reset runs on a side thread with a three second budget, requires system uid and skips the carrier eSIM-removal notification. Only failed verifications are checked and only typed PIN/password credentials, so the real lock credential can never trigger it. Setting/checking/deleting requires the owner credential; the stored form is a scrypt-stretched hash, never the credential |
| Credential limits (GrapheneOS values) | `frameworks_base/0009` | the fingerprint sensor locks out permanently after 5 failed attempts (AOSP 20; the 30 s timed lockout is unchanged) and the maximum supported password length is 128 characters (AOSP 64) |
| Lock-screen notification content hidden | `frameworks_base/0012` | GrapheneOS default: content stays hidden on the lock screen until the user allows private notifications (see first-boot defaults) |
| FBE filename padding | `system_extras/0001` (GrapheneOS port) | every encryption policy created by this build pads filenames to 32 bytes instead of AOSP's 16 (GrapheneOS commit "pad filenames to 32 bytes instead of 16 or 4 bytes"), hiding filename lengths better. The pre-R 4-byte compatibility branch is dropped (`PRODUCT_SHIPPING_API_LEVEL := 35` makes it unreachable); `vold` picks the flags up through `libfscrypt`. Only applies to policies created after flashing (see limits) |

## Framework infrastructure

| Feature | Where | Notes |
|---|---|---|
| `android.ext.settings` (GrapheneOS) | `frameworks_base/0006` | `Setting`/`BoolSetting`/`IntSetting`/`StringSetting` plus the system-property variants, and `ExtSettings` with the GrapheneOS key set (auto-reboot timeout, Wi-Fi/BT/NFC auto-off, clipboard read, sensor permission grant, screenshot EXIF, PIN scramble, DCL/memtag defaults). Defaults are `core/res/res/values/config_ext.xml` resources and `Settings.Global`/`Settings.Secure` keys with GrapheneOS-identical literals, so later ports can drop in without redefining storage. Entries whose enforcement code is not ported yet are inert (no UI is surfaced for them); PIN scramble, the clipboard defaults and the Wi-Fi/Bluetooth auto-off timers are enforced — see the lock, clipboard and framework sections |
| Radio auto-off timers | `frameworks_base/0020` + `packages_apps_Settings/0001` (GrapheneOS port) | Wi-Fi is turned off after a configurable idle timeout when it is on but not connected to any network, and Bluetooth when the adapter is on with no connected device (including LE/GATT); default "Never" (GrapheneOS default), choices 15 s–8 h in More security & privacy. GrapheneOS's `SystemServerExt` is trimmed to the auto-off wiring; GrapheneOS shows these on its Exploit protection screen with a radio-button sub-screen — lenOS uses plain list rows (documented substitution). NFC auto-off is not ported (needs the Nfc app side) |
| PendingIntent immutability warp | `frameworks_base/0011` | GrapheneOS port: once the S+ compat change is enforced, an app that omitted `FLAG_IMMUTABLE`/`FLAG_MUTABLE` no longer crashes with `IllegalArgumentException` — the framework logs and forces `FLAG_IMMUTABLE`; every creation path (`getActivity`, `getActivities`, `getBroadcast`, `getService`/foreground service) honours the returned flags. Passing both flags still throws |
| Clock-drift warning at 250 ms | `frameworks_base/0010` | GrapheneOS value: the time detector logs a warning when something other than itself moves the system clock by more than 250 ms (AOSP 2 s) |
| Delayed Allow buttons | `packages_modules_Permission/0001` + `frameworks_base/0014` | GrapheneOS port: the Allow button in runtime permission dialogs (all six allow variants) and in the USB-debugging authorization prompt only becomes clickable one second after the dialog appears, so accidental taps cannot confirm a grant instantly; Deny/Cancel stay immediate |
| Secure paste (stage 1) | `frameworks_base/0015` + `packages_apps_Settings/0001` | GrapheneOS clipboard read gate: with "Secure paste" enabled in More security & privacy, third-party apps may only read clipboard items they copied themselves; the default IME and system apps keep access, and denied readers get the mime types without the clip label so paste affordances survive. Off by default (GrapheneOS default); enabling it without the stage-2 per-app UI and SystemUI paste toolbar intentionally stops cross-app paste. Stage 1 uses the global `ALLOW_CLIPBOARD_READ_BY_DEFAULT` default only |
| Cross-profile shared clipboard | `frameworks_base/0016` + `packages_apps_Settings/0001` | GrapheneOS setting `cross_profile_clipboard_access` (per user; literal key): follow defaults / import-only / export-only / disallow. Gates clipboard propagation between related profiles and cross-profile drag-and-drop. Default follows stock Android, so the control is opt-in |
| No implicit location grant to browsers | `frameworks_base/0019` (GrapheneOS port) | the first-boot default-grant pass no longer gives the browser role holder (or the `CATEGORY_APP_BROWSER` system handler) foreground location; a browser must ask the user like any other app. Matches GrapheneOS, whose `DefaultPermissionGrantPolicy` has no browser block |

## Apps and UI

| Item | Status |
|---|---|
| Minimal app set | `Gallery2` stripped via `LENOS_STRIP_PACKAGES` (`vendor_lineage/0001`), AudioFX off (`TARGET_EXCLUDES_AUDIOFX`), MP3/Music app (`Twelve`) kept for now |
| Jelly browser | **kept** for 1.0; Cromite/WebView replacement is still under investigation (see limits) |
| `LenosSecurity` app | ships with: auto-BFU timer (init backend), PIN-scramble switch (writes the same `Settings.Secure` key SystemUI reads), duress PIN/password UI (framework service), status card. The old global Wi-Fi hostname toggle was dropped in the GrapheneOS-faithful redo — that control is per network in Wi-Fi settings, and the app no longer needs `NETWORK_SETTINGS` |
| Screenshot metadata | `frameworks_base/0013` + `packages_apps_Settings/0001` | SystemUI screenshot exports carry no timestamp, timezone or build-string EXIF metadata by default (GrapheneOS's `ExtSettings.SCREENSHOT_TIMESTAMP_EXIF` gate, default off; LineageOS's `TAG_SOFTWARE = "Android " + Build.DISPLAY` line removed to match GrapheneOS/AOSP). Per-user toggle: Settings → Security & privacy → More security & privacy → "Save screenshot timestamp to EXIF" |

## Not in the 1.0 series

Anything not listed above (sensors permission, LTE-only toggle, 2nd PIN, safe
recovery, signed OTA/updater, reproducible builds, custom AVB key) is **not
implemented yet**.

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
* **DHCP hostname is off by default** (GrapheneOS-faithful). A network that
  needs the device name must be opted in per network in its Wi-Fi network
  details (Advanced). There is no global switch, by design: a global clamp
  would override explicit per-network user choices.
* **Secure paste is stage 1.** It ships the global default and the framework
  enforcement, but not GrapheneOS's per-app switch or the SystemUI/text-selection
  paste toolbar. Enabling it blocks third-party apps from reading another app's
  clip; cross-app paste then depends on the receiving app or on turning the
  toggle back off. The per-app UI, paste grants and toolbar are stage 2.
* **PIN scramble is on by default** — a lenOS deviation from GrapheneOS
  (which ships it off). The keypad relayouts on every setup, which can
  disorient screen-reader/accessibility users; switch it off in Settings →
  Security → Screen lock settings, or the SIM lock screen for SIM PIN/PUK.
  The secondary-credential scramble setting is dormant: Android 16's
  LineageOS base has a single credential domain.
* **Five bad fingerprint reads lock the sensor out permanently** (until the
  device is unlocked with the PIN/password) — GrapheneOS's value; AOSP allows
  20. Dry or move the finger rather than retrying if reads keep failing.
* **Lock-screen notification content stays hidden by default where the
  default applies** — new installs and new users. A device updated over an
  existing install keeps its stored value (`Settings.Secure
  lock_screen_allow_private_notifications`); the toggle is Settings →
  Notifications → Lockscreen notifications.
* **Screenshot metadata is stripped by default** — the built-in screenshot
  flow writes no capture date, timezone or build string to the image EXIF
  (GrapheneOS default). The per-user toggle "Save screenshot timestamp to
  EXIF" (Settings → Security & privacy → More security & privacy) restores
  the AOSP timestamps; the build-string tag never comes back. Third-party
  screenshot tools manage their own metadata.
* **The CA removals touch the system store only** — the platform TLS store
  no longer trusts Chunghwa Telecom (HiPKI Root CA - G1, ePKI Root CA) and
  NetLock Arany (Class Gold), matching GrapheneOS and Google's 2025
  root-store distrust. User-installed CAs, app-pinned trust and non-TLS
  uses are unaffected. The AOSP snapshot pinned by LineageOS 23.2 still
  ships these roots, so if that revision ever changes the patchkit hard-fails
  until the removal is re-verified (by design).
* **FBE filename padding applies to new encryption policies only** — the
  32-byte padding is written into each policy when it is created (fresh
  install, factory reset, or a new user profile); data encrypted before
  flashing keeps its original policy flags, which stay readable. It is a
  metadata-hardening change, not a fix for an exploitable flaw, and file
  contents encryption is unchanged.
* **Emergency alert toggles are user choices, not new defaults** — all
  wireless alert types ship enabled and the port only makes the presidential
  (and, in Brazil, extreme-alert) switches real. Where regulation expects no
  opt-out, turning an alert off is the user's deliberate decision, mirroring
  GrapheneOS. The legacy settings fragment used on pre-S/watch UIs keeps
  AOSP's always-on wiring, same as GrapheneOS on this branch.
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
  erase), erases the eSIM profiles, then powers off — there is no undo. It is
  opt-in: nothing happens until the user sets a duress PIN/password with the
  owner credential. The carrier does not receive an eSIM removal
  notification, and a missing or unresponsive eUICC can delay the power-off
  by at most three seconds. The app warns "do not test on this phone"; only
  test when a full wipe is acceptable.
* **Jelly (WebView-based browser) still ships.** It is the Lineage default and
  gets WebView security updates from the system; replacing it with Cromite and
  updating WebView are separate work items.

## Verification checklist (on the first flash)

See `build.md`. At minimum: `cmd overlay list --user 0` shows all three lenOS
RROs enabled, `settings list global | grep -E "private_dns|ntp|captive"` shows
the seeded values, `settings get global settings_reboot_after_timeout` shows
`64800000` (or unset — the ExtSettings default is 18h),
`getprop sys.auto_reboot_ctl` shows a timeout while the device is locked and
`on_device_unlocked` right after unlocking, the lock-screen keypad is shuffled
on every appearance (`settings get secure lockscreen_scramble_pin_layout`
unset means default on; `0` disables it), a newly saved Wi-Fi network shows
per-connection random MAC and no DHCP hostname (network details),
`pm get-max-users` reports 32, on a fresh install
`settings get secure lock_screen_allow_private_notifications` is `0`, a fresh
screenshot shows no `DateTimeOriginal`/`OffsetTimeOriginal`/`Software` EXIF
tags unless "Save screenshot timestamp to EXIF" is enabled (`settings get
secure screenshot_timestamp_exif` unset means off),
`ls /system/etc/security/cacerts | grep -E "53a1b57a|60afe812|9d6523ce"`
prints nothing, Settings > Safety & emergency > Wireless emergency alerts
lists a working "Presidential alerts" switch, a fresh permission dialog keeps
its Allow button inactive for a moment (the GrapheneOS delay), a new copy in
one app is readable in another app with Secure paste off (the default), enabling
"Secure paste" in More security & privacy makes a third-party app see an empty
clipboard for the other app's item while the keyboard still pastes, the
cross-profile clipboard row accepts the four GrapheneOS policies, and on
the lock screen tapping a sensitive tile (e.g.
airplane mode) opens the unlock prompt without changing state until unlock,
while the flashlight tile keeps working.

VPN lockdown: configure an always-on VPN with "Block connections without VPN",
then stop the VPN app's tunnel (force-stop/disable it) — DNS and all traffic
must fail closed instead of reaching the default network's resolvers; a
regular app's mDNS/NSD discovery must be refused while lockdown is active
(system apps keep working), and inbound IPv6 router advertisements from the
Wi-Fi access point must still arrive (IPv6 does not disappear when no VPN is
connected).

Duress (destructive — run last, only when a wipe is acceptable): set a pair
with `cmd lock_settings set-duress-credentials --old <owner cred> --duress-pin
1234 --duress-password ''` (owner credential required), check the app's status
card flips to "set", then enter the duress PIN at the lock screen: the device
must delete the storage keys and power off, and the following boot must no
longer be able to decrypt the user data (expect the device to treat the data
partition as gone / factory reset).
