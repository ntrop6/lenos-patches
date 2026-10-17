# vendor/lenos — 1.0.0-shizuku

This is the product. `hardwire.py` writes it **into the Lineage sources**. There is no `git apply`. `patches/` is provenance only and is not used.

Codename **shizuku**. Fingerprint untouched. DNS **Quad9**.

## What gets written into the tree

| File | What |
|---|---|
| `device/nothing/asteroids/lenos.prop` + `system_ext.prop` | `ro.lenos.*=1.0.0-shizuku`, `default_network=28,28` (no 2G), empty hostname, radio/IMS/modem logs off |
| `frameworks/base/.../config.xml` | NTP `time.grapheneos.org`, DNS probe `9.9.9.9`, GrapheneOS captive-portal 204s, nearby-sharing component blanked |
| `SettingsProvider/DatabaseHelper.java` | first-boot: Private DNS **hostname / dns.quad9.net**, captive portal, Wi-Fi/BLE scan off, NFC off, location off |
| `SettingsProvider/defaults.xml` | BT/Wi-Fi/wakeup off, location 0, device name `Android`, USB mass-storage off |
| CarrierConfig `gps.supl_host` | **empty** (no `supl.google.com`) |
| Wifi overlays | insecure enterprise **false**, tether SSID `AndroidAP` |
| `gps.conf` / izat under device+vendor | SUPL blank, XTRA → `qualcomm.psds.grapheneos.org`, NTP `time.grapheneos.org` if those files exist |
| `AndroidManifest` + Connectivity + `netd.c` | `android.permission.NETWORK` declared and enforced at socket create |
| Keyguard / SystemUI | PIN scramble default on, GC on lock |
| Settings | homepage **lenOS security** tile + duress/BFU sources |

Overlays under `vendor/lenos/overlay` are the same values as backup. The source files themselves are changed.

Not invented into this compile: hardened_malloc (`repo sync` of `external/hardened_malloc`), Cromite APK, USB-HAL-on-lock, exec-spawn. RKP hostname left alone (keystore attestation, no Graphene proxy).

## On the VM

`reset hardening` git-resets. Hardwire **after** it.

```bash
gcloud compute scp --tunnel-through-iap --recurse vendor-lenos cesurmali76@lenos-build:~/vendor-lenos
export LENOS_ALLOW_LOW_MEMORY=1 LENOS_BUILD_JOBS=4
~/lenOS-2.8.1-ReSukiSU-single.sh reset hardening
bash ~/vendor-lenos/integrate.sh "$HOME/lenos-workspace/lineage"
grep dns.quad9.net ~/lenos-workspace/lineage/frameworks/base/packages/SettingsProvider -r | head
grep gps.supl_host ~/lenos-workspace/lineage/device/nothing/asteroids/rro_overlays/CarrierConfigResCommon_Vendor/res/xml/vendor.xml
~/lenOS-2.8.1-ReSukiSU-single.sh reset build
~/lenOS-2.8.1-ReSukiSU-single.sh build --rootless --hardening full
```

No `repo sync`. Do not lock.
