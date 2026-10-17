#!/usr/bin/env python3
"""Write lenOS 1.0.0-shizuku OPSEC into the Lineage tree as source, not patches.

Idempotent. Does not git-apply. Does not repo sync. Does not lock.
DNS = Quad9 DoT (dns.quad9.net). NTP = time.grapheneos.org.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(sys.argv[1]).resolve()
HERE = Path(__file__).resolve().parent.parent
DEVICE = SRC / "device/nothing/asteroids"
SETTINGS = SRC / "packages/apps/Settings"
FWB = SRC / "frameworks/base"
CONN = SRC / "packages/modules/Connectivity"

DNS_DOT = "dns.quad9.net"
DNS_IP = "9.9.9.9"
NTP = "ntp://time.grapheneos.org"
CAPTIVE_HTTP = "http://connectivitycheck.grapheneos.network/generate_204"
CAPTIVE_HTTPS = "https://connectivitycheck.grapheneos.network/generate_204"
CAPTIVE_FB = "http://grapheneos.online/gen_204"
CAPTIVE_OTHER = "http://grapheneos.online/generate_204"


def log(msg: str) -> None:
    print(f"  {msg}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write(p: Path, t: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t, encoding="utf-8")


def upsert_prop(text: str, key: str, value: str) -> str:
    line = f"{key}={value}" if value != "" else f"{key}="
    pat = re.compile(rf"(?m)^{re.escape(key)}=.*$")
    if pat.search(text):
        return pat.sub(line, text)
    if not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def set_xml_bool(text: str, name: str, value: str) -> tuple[str, int]:
    pat = re.compile(rf'(<bool name="{name}">)[^<]*')
    n = len(pat.findall(text))
    return pat.sub(rf"\g<1>{value}", text), n


def set_xml_int(text: str, name: str, value: str) -> tuple[str, int]:
    pat = re.compile(rf'(<integer name="{name}">)[^<]*')
    n = len(pat.findall(text))
    return pat.sub(rf"\g<1>{value}", text), n


def set_xml_string(text: str, name: str, value: str) -> tuple[str, int]:
    pat = re.compile(rf'(<string\b[^>]*name="{name}"[^>]*>)[^<]*')
    n = len(pat.findall(text))
    return pat.sub(rf"\g<1>{value}", text), n


def insert_after(text: str, needle: str, addition: str) -> str:
    if addition.strip() in text:
        return text
    idx = text.find(needle)
    if idx < 0:
        return text
    nl = text.find("\n", idx)
    if nl < 0:
        return text
    return text[: nl + 1] + addition + text[nl + 1 :]


def replace_if(text: str, old: str, new: str) -> str:
    return text.replace(old, new) if old in text else text


# ---------------------------------------------------------------------------
# Device tree
# ---------------------------------------------------------------------------

def hardwire_device() -> None:
    prop_src = HERE / "config/lenos.prop"
    dest = DEVICE / "lenos.prop"
    write(dest, read(prop_src))
    log(f"wrote {dest.relative_to(SRC)}")

    sep = DEVICE / "system_ext.prop"
    if sep.exists():
        t = read(sep)
        t = t.replace("1.0.0-shinra-bansho", "1.0.0-shizuku")
        for line in read(prop_src).splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            t = upsert_prop(t, k, v)
        write(sep, t)
        log("system_ext.prop merged (2G=28, hostname empty, radio logs off, shizuku)")

    mk = DEVICE / "lineage_asteroids.mk"
    if mk.exists():
        t = read(mk)
        inherit = "$(call inherit-product, vendor/lenos/config/lenos.mk)\n"
        if "vendor/lenos/config/lenos.mk" not in t:
            write(mk, t.rstrip() + "\n\n" + inherit)
            log("lineage_asteroids.mk inherits vendor/lenos")

    # SUPL blank — CarrierConfig vendor overlay
    vendor_xml = DEVICE / "rro_overlays/CarrierConfigResCommon_Vendor/res/xml/vendor.xml"
    if vendor_xml.exists():
        t = read(vendor_xml)
        t2, n = set_xml_string(t, "gps.supl_host", "")
        write(vendor_xml, t2)
        log(f"SUPL host blanked ({n} hits) in CarrierConfig")

    # Wi-Fi: no insecure enterprise, generic tether SSID
    for rel in (
        "rro_overlays/AsteroidsWifiOverlay/res/values/config.xml",
        "rro_overlays/WifiResTarget/res/values/config.xml",
    ):
        p = DEVICE / rel
        if not p.exists():
            continue
        t = read(p)
        t, n1 = set_xml_bool(t, "config_wifiAllowInsecureEnterpriseConfigurationsForSettingsAndSUW", "false")
        t, n2 = set_xml_string(t, "wifi_tether_configure_ssid_default", "AndroidAP")
        write(p, t)
        log(f"{rel}: insecure-enterprise={n1} tether-ssid={n2}")

    # Device-tree NTP/DNS overlay (vendor RRO)
    fw = DEVICE / "rro_overlays/FrameworksResTarget_Vendor/res/values/config.xml"
    if fw.exists():
        t = read(fw)
        t = t.replace("ntp://time.android.com", NTP)
        t = t.replace("ntp://time.cloudflare.com", NTP)
        t = t.replace(">8.8.8.8<", f">{DNS_IP}<")
        t = t.replace(">194.242.2.2<", f">{DNS_IP}<")
        if "time.grapheneos.org" not in t:
            t = t.replace(
                "</resources>",
                f"""
    <string-array translatable="false" name="config_ntpServers">
        <item>{NTP}</item>
    </string-array>
    <string name="config_default_dns_server" translatable="false">{DNS_IP}</string>
</resources>
""",
                1,
            )
        write(fw, t)
        log("FrameworksResTarget_Vendor NTP/DNS hardwired")

    # Qualcomm gps.conf / izat.conf if present anywhere under device or vendor
    for root in (DEVICE, SRC / "vendor/nothing", SRC / "vendor/qcom"):
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() not in {".conf", ".txt", ".xml"}:
                continue
            if p.stat().st_size > 200_000:
                continue
            try:
                t = read(p)
            except OSError:
                continue
            orig = t
            t = re.sub(r"(?m)^SUPL_HOST\s*=.*$", "SUPL_HOST=", t)
            t = re.sub(r"(?m)^NTP_SERVER\s*=.*$", "NTP_SERVER=time.grapheneos.org", t)
            t = t.replace("path1.xtracloud.net", "qualcomm.psds.grapheneos.org")
            t = t.replace("path2.xtracloud.net", "qualcomm.psds.grapheneos.org")
            t = t.replace("path3.xtracloud.net", "qualcomm.psds.grapheneos.org")
            t = t.replace("izatcloud.net", "qualcomm.psds.grapheneos.org")
            t = t.replace("xtrapath1.izatcloud.net", "qualcomm.psds.grapheneos.org")
            t = t.replace("time.xtracloud.net", "time.grapheneos.org")
            t = t.replace("time.google.com", "time.grapheneos.org")
            if t != orig:
                write(p, t)
                log(f"GNSS endpoints rewritten in {p.relative_to(SRC)}")


# ---------------------------------------------------------------------------
# frameworks/base config.xml + SettingsProvider defaults (the actual sources)
# ---------------------------------------------------------------------------

def hardwire_frameworks_config() -> None:
    cfg = FWB / "core/res/res/values/config.xml"
    if not cfg.exists():
        log("WARN: frameworks/base config.xml missing")
        return
    t = read(cfg)
    t = t.replace("ntp://time.android.com", NTP)
    t = t.replace("ntp://time.cloudflare.com", NTP)
    t = t.replace("2.android.pool.ntp.org", "time.grapheneos.org")
    # default DNS probe
    t2, n = set_xml_string(t, "config_default_dns_server", DNS_IP)
    t = t2
    t2, n1 = set_xml_string(t, "config_captive_portal_https_url", CAPTIVE_HTTPS)
    t2, n2 = set_xml_string(t2, "config_captive_portal_http_url", CAPTIVE_HTTP)
    t2, n3 = set_xml_string(t2, "config_captive_portal_fallback_url", CAPTIVE_FB)
    t2, n4 = set_xml_string(t2, "config_captive_portal_other_fallback_urls", CAPTIVE_OTHER)
    t = t2
    # nearby sharing component — blank if the resource exists
    t, n5 = set_xml_string(t, "config_defaultNearbySharingComponent", "")
    t, n6 = set_xml_bool(t, "config_enableWifiScanAlwaysAvailable", "false")
    write(cfg, t)
    log(f"frameworks/base config.xml: dns={n} captive={n1+n2+n3+n4} nearby={n5}")

    defaults = FWB / "packages/SettingsProvider/res/values/defaults.xml"
    if defaults.exists():
        t = read(defaults)
        for name, val in (
            ("def_bluetooth_on", "false"),
            ("def_wifi_on", "false"),
            ("def_wifi_wakeup_enabled", "false"),
            ("def_networks_available_notification_on", "false"),
            ("assisted_gps_enabled", "false"),
            ("def_usb_mass_storage_enabled", "false"),
            ("def_lock_screen_show_qr_code_scanner", "false"),
        ):
            t, _ = set_xml_bool(t, name, val)
        t, _ = set_xml_int(t, "def_wifi_scan_always_available", "0")
        t, _ = set_xml_int(t, "def_location_mode", "0")
        t, _ = set_xml_string(t, "def_device_name", "Android")
        t, _ = set_xml_string(t, "def_device_name_simple", "Android")
        write(defaults, t)
        log("SettingsProvider defaults.xml: location off, BT/Wi-Fi off, name=Android")


def hardwire_database_helper() -> None:
    hits = list((FWB / "packages/SettingsProvider").rglob("DatabaseHelper.java"))
    if not hits:
        log("WARN: DatabaseHelper.java missing")
        return
    p = hits[0]
    t = read(p)
    t = t.replace("base.dns.mullvad.net", DNS_DOT)
    t = t.replace("194.242.2.2", DNS_IP)
    if DNS_DOT in t and "PRIVATE_DNS_SPECIFIER" in t:
        write(p, t)
        log("DatabaseHelper already seeded — Quad9")
        return
    block = f'''
            // lenOS 1.0.0-shizuku — first-boot Settings.Global. Not an overlay.
            loadSetting(stmt, Settings.Global.PRIVATE_DNS_MODE, "hostname");
            loadSetting(stmt, Settings.Global.PRIVATE_DNS_SPECIFIER, "{DNS_DOT}");
            loadSetting(stmt, Settings.Global.CAPTIVE_PORTAL_HTTP_URL, "{CAPTIVE_HTTP}");
            loadSetting(stmt, Settings.Global.CAPTIVE_PORTAL_HTTPS_URL, "{CAPTIVE_HTTPS}");
            loadSetting(stmt, Settings.Global.CAPTIVE_PORTAL_FALLBACK_URL, "{CAPTIVE_FB}");
            loadSetting(stmt, Settings.Global.CAPTIVE_PORTAL_OTHER_FALLBACK_URLS, "{CAPTIVE_OTHER}");
            loadSetting(stmt, Settings.Global.WIFI_SCAN_ALWAYS_AVAILABLE, "0");
            loadSetting(stmt, Settings.Global.BLE_SCAN_ALWAYS_AVAILABLE, "0");
            loadSetting(stmt, Settings.Global.WIFI_WAKEUP_ENABLED, "0");
            loadSetting(stmt, Settings.Global.NFC_ON, "0");
'''
    needle = "INSERT OR IGNORE INTO global"
    if needle not in t:
        log("WARN: no global INSERT in DatabaseHelper")
        return
    t = insert_after(t, needle, block)
    # location off in secure table if present
    sec = "INSERT OR IGNORE INTO secure"
    if sec in t and "LOCATION_MODE" not in t[t.find(sec) : t.find(sec) + 2500]:
        t = insert_after(
            t,
            sec,
            """
            loadSetting(stmt, Settings.Secure.LOCATION_MODE, "0");
""",
        )
    write(p, t)
    log(f"DatabaseHelper first-boot: Quad9 DoT + GrapheneOS captive + scans/NFC/location off")


# ---------------------------------------------------------------------------
# NETWORK permission (declaration + Connectivity + BPF) as source splices
# ---------------------------------------------------------------------------

def hardwire_network_permission() -> None:
    manifest = FWB / "core/res/AndroidManifest.xml"
    strings = FWB / "core/res/res/values/strings.xml"
    api = FWB / "core/api/current.txt"
    if manifest.exists():
        t = read(manifest)
        if 'android:name="android.permission.NETWORK"' not in t:
            m = re.search(
                r'<permission android:name="android.permission.INTERNET"[\s\S]*?/>',
                t,
            )
            perm = '''
    <permission android:name="android.permission.NETWORK"
        android:description="@string/permdesc_network"
        android:label="@string/permlab_network"
        android:protectionLevel="normal|instant" />
'''
            if m:
                t = t[: m.end()] + perm + t[m.end() :]
                write(manifest, t)
                log("AndroidManifest: android.permission.NETWORK")
            else:
                log("WARN: INTERNET permission not found")
        else:
            log("NETWORK permission already in manifest")

    if strings.exists():
        s = read(strings)
        if "permlab_network" not in s:
            s = s.replace(
                '<string name="permlab_createNetworkSockets">',
                '<string name="permlab_network">access networks</string>\n    '
                '<string name="permdesc_network">Allows the app to access networks, including the local network. When denied, the app cannot use any network interface, resolve DNS, or communicate over localhost.</string>\n    '
                '<string name="permlab_createNetworkSockets">',
                1,
            )
            write(strings, s)
            log("NETWORK permission strings")

    if api.exists():
        a = read(api)
        if 'NETWORK = "android.permission.NETWORK"' not in a:
            a = a.replace(
                'field public static final String NEARBY_WIFI_DEVICES = "android.permission.NEARBY_WIFI_DEVICES";\n',
                'field public static final String NEARBY_WIFI_DEVICES = "android.permission.NEARBY_WIFI_DEVICES";\n'
                '    field public static final String NETWORK = "android.permission.NETWORK";\n',
                1,
            )
            write(api, a)
            log("current.txt Manifest.permission.NETWORK")

    if not CONN.exists():
        log("WARN: packages/modules/Connectivity missing")
        return

    np = CONN / "service/src/com/android/server/connectivity/NetworkPermissions.java"
    if np.exists():
        t = read(np)
        if "TRAFFIC_PERMISSION_NETWORK" not in t:
            t = t.rstrip() + """

    /** lenOS: revocable layer on INTERNET. Must match BPF_PERMISSION_NETWORK. */
    public static final int TRAFFIC_PERMISSION_NETWORK = 1 << 5;
}
"""
            # the original file already ended with } — avoid double brace if we appended after
            # rewrite more carefully
            t = read(np)
            t = t.replace(
                "public static final int TRAFFIC_PERMISSION_SDKSANDBOX_LOCALHOST = 16;",
                "public static final int TRAFFIC_PERMISSION_SDKSANDBOX_LOCALHOST = 16;\n\n"
                "    /** lenOS: revocable layer on INTERNET. Must match BPF_PERMISSION_NETWORK. */\n"
                "    public static final int TRAFFIC_PERMISSION_NETWORK = 1 << 5;",
                1,
            )
            if "TRAFFIC_PERMISSION_NETWORK" not in t:
                t = read(np)
                t = re.sub(r"\n\}\s*$", "\n    public static final int TRAFFIC_PERMISSION_NETWORK = 1 << 5;\n}\n", t, count=1)
            write(np, t)
            log("TRAFFIC_PERMISSION_NETWORK")
        else:
            log("TRAFFIC_PERMISSION_NETWORK already present")

    pm = CONN / "service/src/com/android/server/connectivity/PermissionMonitor.java"
    if pm.exists():
        t = read(pm)
        if "TRAFFIC_PERMISSION_NETWORK" not in t:
            t = t.replace(
                "import static com.android.server.connectivity.NetworkPermissions.TRAFFIC_PERMISSION_INTERNET;",
                "import static com.android.server.connectivity.NetworkPermissions.TRAFFIC_PERMISSION_INTERNET;\n"
                "import static com.android.server.connectivity.NetworkPermissions.TRAFFIC_PERMISSION_NETWORK;",
                1,
            )
            t = t.replace(
                "permissions |= TRAFFIC_PERMISSION_INTERNET;",
                "permissions |= TRAFFIC_PERMISSION_INTERNET;\n"
                "                permissions |= TRAFFIC_PERMISSION_NETWORK;",
                1,
            )
            write(pm, t)
            log("PermissionMonitor default-grants NETWORK with INTERNET")

    cs = CONN / "service/src/com/android/server/ConnectivityService.java"
    if cs.exists():
        t = read(cs)
        if "hasNetworkPermission" not in t:
            t = t.replace(
                "import static android.net.INetd.PERMISSION_INTERNET;",
                "import static android.net.INetd.PERMISSION_INTERNET;\n"
                "import static com.android.server.connectivity.NetworkPermissions.TRAFFIC_PERMISSION_NETWORK;",
                1,
            )
            t = t.replace(
                "return (mBpfNetMaps.getNetPermForUid(uid) & PERMISSION_INTERNET) != 0;\n    }",
                "return (mBpfNetMaps.getNetPermForUid(uid) & PERMISSION_INTERNET) != 0;\n    }\n\n"
                "    private boolean hasNetworkPermission(final int uid) {\n"
                "        return (mBpfNetMaps.getNetPermForUid(uid) & TRAFFIC_PERMISSION_NETWORK) != 0;\n"
                "    }",
                1,
            )
            t = t.replace(
                "return blockedByUidRules || !hasInternetPermission;",
                "return blockedByUidRules || !hasInternetPermission || !hasNetworkPermission(uid);",
                1,
            )
            write(cs, t)
            log("ConnectivityService enforces NETWORK")

    bpf_h = CONN / "bpf/progs/netd.h"
    bpf_c = CONN / "bpf/progs/netd.c"
    if bpf_h.exists():
        t = read(bpf_h)
        if "BPF_PERMISSION_NETWORK" not in t:
            t = t.replace(
                "BPF_PERMISSION_UPDATE_DEVICE_STATS = 1 << 3,",
                "BPF_PERMISSION_UPDATE_DEVICE_STATS = 1 << 3,\n"
                "    BPF_PERMISSION_NETWORK = 1 << 5,",
                1,
            )
            write(bpf_h, t)
            log("netd.h BPF_PERMISSION_NETWORK")
    if bpf_c.exists():
        t = read(bpf_c)
        t = t.replace(
            "return permissions ? *permissions : BPF_PERMISSION_INTERNET;",
            "return permissions ? *permissions : (BPF_PERMISSION_INTERNET | BPF_PERMISSION_NETWORK);",
        )
        t = t.replace(
            "if (get_app_permissions(uid) & BPF_PERMISSION_INTERNET) {",
            "const uint8_t perms = get_app_permissions(uid);\n"
            "    if ((perms & BPF_PERMISSION_INTERNET) && (perms & BPF_PERMISSION_NETWORK)) {",
            1,
        )
        write(bpf_c, t)
        log("netd.c inet_create requires NETWORK")


# ---------------------------------------------------------------------------
# PIN scramble default + memory-clear-on-lock (source, not patch)
# ---------------------------------------------------------------------------

def hardwire_lock_memory() -> None:
    pin_settings = SETTINGS / "src/com/android/settings/security/screenlock/PinScramblePreferenceController.java"
    if pin_settings.exists():
        t = read(pin_settings)
        t = t.replace(
            "LineageSettings.System.LOCKSCREEN_PIN_SCRAMBLE_LAYOUT,\n                0) == 1);",
            "LineageSettings.System.LOCKSCREEN_PIN_SCRAMBLE_LAYOUT,\n                1) == 1);",
        )
        t = t.replace(
            "LOCKSCREEN_PIN_SCRAMBLE_LAYOUT,\n                0)",
            "LOCKSCREEN_PIN_SCRAMBLE_LAYOUT,\n                1)",
        )
        write(pin_settings, t)
        log("PIN scramble Settings default = on")

    pin_kg = FWB / "packages/SystemUI/src/com/android/keyguard/KeyguardPinViewController.java"
    if pin_kg.exists():
        t = read(pin_kg)
        t = t.replace(
            "LineageSettings.System.LOCKSCREEN_PIN_SCRAMBLE_LAYOUT, 0,",
            "LineageSettings.System.LOCKSCREEN_PIN_SCRAMBLE_LAYOUT, 1,",
        )
        write(pin_kg, t)
        log("PIN scramble Keyguard default = on")

    ksm = FWB / "services/core/java/com/android/server/policy/keyguard/KeyguardStateMonitor.java"
    if ksm.exists():
        t = read(ksm)
        if "requestConcurrentGC" not in t:
            if "import dalvik.system.VMRuntime;" not in t:
                t = t.replace(
                    "import android.util.Slog;",
                    "import android.util.Slog;\n\nimport dalvik.system.VMRuntime;",
                    1,
                )
            t = t.replace(
                "mIsShowing = showing;",
                "mIsShowing = showing;\n\n"
                "        if (showing) {\n"
                "            VMRuntime.getRuntime().requestConcurrentGC();\n"
                "        }",
                1,
            )
            write(ksm, t)
            log("system_server GC on lock")

    kvm = FWB / "packages/SystemUI/src/com/android/systemui/keyguard/KeyguardViewMediator.java"
    if kvm.exists():
        t = read(kvm)
        if "requestConcurrentGC" not in t:
            if "import dalvik.system.VMRuntime;" not in t:
                t = t.replace(
                    "import androidx.annotation.VisibleForTesting;",
                    "import androidx.annotation.VisibleForTesting;\n\nimport dalvik.system.VMRuntime;",
                    1,
                )
            needle = "mShowing = showing;"
            if needle in t:
                t = t.replace(
                    needle,
                    "final boolean wasShowing = mShowing;\n        mShowing = showing;",
                    1,
                )
                t = t.replace(
                    "mAodShowing = aodShowing;",
                    "mAodShowing = aodShowing;\n\n"
                    "        if (showing && !wasShowing) {\n"
                    "            VMRuntime.getRuntime().requestConcurrentGC();\n"
                    "        }",
                    1,
                )
                write(kvm, t)
                log("SystemUI GC on lock")


# ---------------------------------------------------------------------------
# Settings homepage tile + copy of lenOS sources
# ---------------------------------------------------------------------------

def hardwire_settings() -> None:
    src = HERE / "settings"
    if src.exists():
        for p in src.rglob("*"):
            if p.is_file():
                dest = SETTINGS / p.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(p.read_bytes())
        log("copied vendor/lenos/settings into packages/apps/Settings")

    top = SETTINGS / "res/xml/top_level_settings.xml"
    if not top.exists():
        return
    t = read(top)
    if "top_level_lenos" in t:
        log("homepage tile already present")
        return
    needle = 'android:key="top_level_security"'
    if needle not in t:
        log("WARN: no top_level_security key")
        return
    tile = '''
        <com.android.settings.widget.HomepagePreference
            android:fragment="com.android.settings.security.LenosDashboardFragment"
            android:icon="@drawable/ic_settings_security_filled"
            android:key="top_level_lenos"
            android:order="-45"
            android:title="@string/lenos_security_features_title"
            android:summary="@string/auto_reboot_footer"
            settings:highlightableMenuKey="@string/menu_key_security"/>
'''
    t = t.replace(needle, tile + "\n        " + needle, 1)
    write(top, t)
    log("Settings homepage tile top_level_lenos")


def main() -> None:
    if not (DEVICE / "lineage_asteroids.mk").exists():
        sys.exit(f"ERROR: not an asteroids tree: {SRC}")
    print("[lenOS 1.0.0-shizuku hardwire]")
    hardwire_device()
    hardwire_frameworks_config()
    hardwire_database_helper()
    hardwire_network_permission()
    hardwire_lock_memory()
    hardwire_settings()
    print("OK. DNS=dns.quad9.net NTP=time.grapheneos.org SUPL=blank name=Android")


if __name__ == "__main__":
    main()
