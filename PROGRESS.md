# lenOS progress log

One entry per working session. "Verified" = seen working on a booted device
(see `docs/build.md` checklist); everything else is source-complete only.

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
4. Cromite/WebView decision (Jelly replacement), OTA/updater hardening,
   signed-update reporting.
5. Framework work that is still out of the series: duress credential backend,
   auto reboot to BFU, sensor permission, Secure Paste, QS-tile unlock gating,
   delayed allow buttons, LTE-only toggle, vold FBE filename padding.
