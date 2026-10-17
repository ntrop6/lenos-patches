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
| `lenos_auto_reboot_timeout_ms` | `64800000` | reboot to before-first-unlock after 18h locked (see "Lock, data and recovery") |

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
| Auto reboot to before-first-unlock (BFU) | `frameworks_base/0003` + first-boot default | `LenosAutoRebootService` reboots a secured device that stayed locked for 18h: the FBE keys leave memory and stay out until the next unlock. Timer arms at screen off, resets on every unlock; `Settings.Global.lenos_auto_reboot_timeout_ms` (0 = off, 10min–3 days) with UI in the lenOS app; reboot deferred while a call is in progress; skipped without a secure lock |
| Quick settings require unlock | `frameworks_base/0004` | while a secure lock screen is up, tapping/long-pressing any QS tile only shows "Unlock the device to use quick settings" — a locked device cannot toggle radios/connectivity (e.g. airplane mode to break remote tracking). Flashlight and camera-toggle tiles stay usable |

## Apps and UI

| Item | Status |
|---|---|
| Minimal app set | `Gallery2` stripped via `LENOS_STRIP_PACKAGES` (`vendor_lineage/0001`), AudioFX off (`TARGET_EXCLUDES_AUDIOFX`), MP3/Music app (`Twelve`) kept for now |
| Jelly browser | **kept** for 1.0; Cromite/WebView replacement is still under investigation (see limits) |
| `LenosSecurity` app | ships with: Wi-Fi DHCP hostname toggle, PIN-scramble state, auto-BFU timer (framework service), duress UI (experimental, see below), status card |

## Experimental (UI present, backend not in the 1.0 series)

These ship **disabled in effect** and must not be relied on until their
backends land in the patch series:

* **Duress PIN/password**: the app's LockBridge UI is from the earlier
  1.0.0-shizuku work; the LockSettingsService backend is not part of the
  current series. The app shows the duress backend as `?`.
* Anything not listed above (sensors permission, Secure Paste, delayed allow
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
  the 18h timer fires, the device reboots; telephony/notifications stay off
  until the user unlocks again (emergency calls work at BFU). It is skipped
  while a call is in progress and on devices without a secure lock. The app
  offers off / 10 minutes … 3 days.
* **Quick settings gating has two deliberate exceptions** (flashlight and
  camera toggle) and is not user-configurable in 1.0; on devices without a
  secure lock it does nothing. The toast is the only feedback — no unlock
  prompt is forced.
* **Jelly (WebView-based browser) still ships.** It is the Lineage default and
  gets WebView security updates from the system; replacing it with Cromite and
  updating WebView are separate work items.

## Verification checklist (on the first flash)

See `build.md`. At minimum: `cmd overlay list --user 0` shows all three lenOS
RROs enabled, `settings list global | grep -E "private_dns|ntp|captive"` shows
the seeded values, `settings get global lenos_auto_reboot_timeout_ms` shows
`64800000`, the Wi-Fi hostname toggle changes the persisted setting, and on the
lock screen a tile tap (e.g. airplane mode) shows the "Unlock the device to use
quick settings" toast while the flashlight tile keeps working.
