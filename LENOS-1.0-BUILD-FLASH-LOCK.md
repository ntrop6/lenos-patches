# lenOS 1.0.0-shizuku — build, flash, lock

Nothing Phone (3a) `asteroids`. Codename **shizuku**. Fingerprint untouched.

The driver is `lenos-1.0-shizuku.sh`. It does **not** replace the 2.8.1 wizard’s compiler (repo/Soong/signing/kernel bind). It **does** replace the overlay-script era: apply the lenOS patch series with `tools/lenos-patch.py` (strict `git apply`, every patch tested in `tests/`), package rootless without firmware re-sign, extract a flash plan that cannot put vbmeta before logicals, and it **will not** flash or lock.

## What this build is

| | |
|---|---|
| Artifact | `lenos-asteroids-rootless.zip` — custom AVB/OTA keys, `--clear-vbmeta-flags`, **stock `init_boot`**, no ReSukiSU |
| Branding | `ro.lenos.version=1.0.0` only |
| DNS | Quad9 DoT `dns.quad9.net` |
| NTP | `pool.ntp.org` |
| Captive portal | Cloudflare `cp.cloudflare.com/generate_204` |
| SUPL | blank |
| Radio | `default_network=28,28` (no 2G) |
| Identifiers | device name `Android`, tether `AndroidAP`, Wi-Fi DHCP hostname blocked |
| Also | PIN scramble on, location off, Bluetooth/wakeup scans off, lock-screen QR shortcut off, per-connection Wi-Fi MAC randomization, strict DoT |

`lenos-asteroids-prepatched.zip` **does not boot this unit.** Do not flash it again.

---

## 0. Rules that already cost us a brick

- Do not `repo sync`.
- Do not `git apply` a pile of patches. Use the patchkit: `tools/lenos-patch.py` (driver step `apply`); the series is strict and tested.
- Do not `--re-sign` firmware (`bluetooth` / `abl` / `xbl` → `Invalid VBMeta header magic`).
- Do not flash partitions individually. That is what killed slot A (vbmeta before logicals).
- Do not invent `android-info.txt`.
- Do not `fastboot boot` recovery (Bad Buffer Size).
- Do not `--disable-verity --disable-verification` with platform-tools 36 (`AVB_MAGIC` at offset 0).
- Do not re-run a sideload that already returned `status: 0` / ~47% `adb: failed to read command: Success`.
- Do not lock the currently booted **test-key / vbmeta `0x3`** image.
- Do not lock until **this** zip has booted **unlocked** with `veritymode=enforcing`.
- File copy laptop ↔ VM: `gcloud compute scp --tunnel-through-iap`, not OpenSSH `scp`.
- `tr`/`mapfile` of the whole `avbroot_patch.log` kills SSH. Do not.

If recovery/fastbootd are dead, stop and use `RECOVERY-3A.md`. Do not improvise.

---

## 1. Build (VM `lenos-build`, tmux)

```bash
# laptop → VM   (remove ~/vendor-lenos on the VM first; scp nests if it exists)
gcloud compute scp --tunnel-through-iap \
  --recurse vendor-lenos lenos-1.0-shizuku.sh \
  cesurmali76@lenos-build:~/

# on the VM, tmux
chmod +x ~/lenos-1.0-shizuku.sh
export LENOS_ALLOW_LOW_MEMORY=1 LENOS_BUILD_JOBS=4
~/lenos-1.0-shizuku.sh doctor
~/lenos-1.0-shizuku.sh apply          # reset hardening → patchkit reset/check/apply → markers
~/lenos-1.0-shizuku.sh build          # 8–17h: apply (again, idempotent) + mka --rootless --hardening full
~/lenos-1.0-shizuku.sh package        # avbroot, OS images only
~/lenos-1.0-shizuku.sh extract        # --fastboot --all + sanitize
```

`reset hardening` git-resets, then the patchkit resets/verifies/applies the
tested series and dies if any patch is missing. Manual equivalent in
`docs/build.md`; `apply` is also run inside `build`.

Gates after `package` / `extract`:

```bash
grep -q 'ro.lenos.version=1.0.0' ~/lenos-workspace/lineage/vendor/lenos/config/lenos.mk
grep -q 'dns.quad9.net' ~/lenos-workspace/lineage/vendor/lenos/rro/LenosSettingsProviderOverlay/res/values/defaults.xml
grep -q 'ro.telephony.default_network=28,28' ~/lenos-workspace/lineage/device/nothing/asteroids/system_ext.prop
test -s ~/lenos-workspace/extracted-rootless/android-info.txt
cat ~/lenos-workspace/lenos-asteroids-rootless.zip.sha256
```

`avbroot ota verify` must **not** say `vbmeta` / `boot` / `init_boot` are still the AOSP test key.

Copy off the VM (zip, sha256, `extracted-rootless/`, `avb_pkmd.bin`). Leave `out/`, Docker, ccache, private keys’ only copy **on** the box. Keys must already exist in ≥2 places before you ever lock.

---

## 2. Flash (laptop). Do not lock in this section.

fastboot **35+**. NixOS: `nix-shell -p android-tools`. Not Google’s ELF binary.

The phone must already boot **some** OS (current test-key lenOS, or stock). From a brick: `RECOVERY-3A.md` first. Bootloader fastboot **cannot** write `system`/`vendor`/`product`.

```bash
sha256sum ~/lenos/lenos-asteroids-rootless.zip
# must match the server .sha256

fastboot --version
test -s ~/lenos/extracted-rootless/android-info.txt
grep -i asteroid ~/lenos/extracted-rootless/android-info.txt
cat ~/lenos/extracted-rootless/fastboot-info.txt
```

`android-info.txt` must exist and mention Asteroids. If it is missing, extract failed — **stop**. Do not write a dummy.

```bash
adb reboot bootloader
fastboot getvar product          # asteroids
fastboot getvar unlocked         # yes
fastboot reboot fastboot         # userspace fastbootd
fastboot getvar is-userspace     # MUST be yes. if no: STOP
fastboot --set-active=a

export ANDROID_PRODUCT_OUT=$HOME/lenos/extracted-rootless
fastboot flashall -w --skip-reboot
```

`-w` when leaving Nothing OS. Any `FAILED` → do not reboot to system, paste the log.

**Do not** `erase`/`flash avb_custom_key` on this pass. Reboot unlocked:

```bash
fastboot reboot
```

First boot takes minutes.

### After it boots — still unlocked

Enable developer options, USB debugging, **OEM unlocking ON**.

```bash
adb shell getprop ro.lenos.version           # 1.0.0
adb shell getprop ro.boot.veritymode         # enforcing
adb shell getprop ro.boot.vbmeta.digest      # record; must match THIS zip
adb reboot bootloader
fastboot getvar has-slot:init_boot
fastboot getvar has-slot:vendor_boot
fastboot getvar has-slot:vbmeta
fastboot getvar slot-unbootable:b
fastboot reboot
```

Mismatch on version / verity / digest → **do not lock**. Live with it unlocked until you are sure.

Sideload of the **same** zip is optional (flashall does not update bootloader/modem; we are not flashing firmware from this OTA anyway). If you sideload: recovery → Apply from ADB. ~47% + `status: 0` = success. **No** extra packages. Do not re-run it.

---

## 3. Lock — optional, last, and it can brick

Rootless has **no** ReSukiSU, so **OEMUnlockOnBoot cannot be installed**. The 2.8.1 wizard `lock` command refuses rootless for that reason. That refusal is correct.

Locking wipes `/data`, which clears the OEM-unlocking toggle. If the phone then fails to boot, you may have **no unlock path**. Slot B having real `_b` partitions is required and is **not** a parachute.

Do not lock unless every box is true:

- [ ] **This** zip booted unlocked (not the old test-key `0x3` image)
- [ ] `ro.lenos.version=1.0.0`
- [ ] `ro.boot.veritymode=enforcing`
- [ ] `ro.boot.vbmeta.digest` matches `avbroot ota verify` of this zip
- [ ] `has-slot:init_boot` / `vendor_boot` / `vbmeta` → yes
- [ ] `slot-unbootable:b` → no
- [ ] OEM unlocking is ON
- [ ] `avb.key` / `ota.key` exist in ≥2 offline places
- [ ] you accept that a failed boot after lock may be unrecoverable

Then, still on the laptop:

```bash
adb reboot bootloader
fastboot getvar unlocked                     # yes
fastboot erase avb_custom_key
fastboot flash avb_custom_key ~/lenos/avb_pkmd.bin
# Nothing fastboot reporting size 0 is normal
fastboot reboot
# confirm it STILL boots
```

Only then:

```bash
adb reboot bootloader
fastboot flashing lock                       # confirm on device; wipes /data
```

Yellow custom-key warning with your key digest = expected.

After lock: OEM unlocking **ON forever**. Never sideload an unpatched / Lineage / Nothing OTA. Never `Direct install` / `Uninstall` in ReSukiSU if you later add root — both flash unsigned boot images.

`lenos-1.0-shizuku.sh lock` and `flash` are refused on purpose.

---

## Updates later

Rebuild on the VM (`build` → `package` → `extract`). Once locked, prefer recovery sideload of the **new** rootless zip (your OTA cert). Each zip is bound to that build; do not reuse an old `init_boot`.
