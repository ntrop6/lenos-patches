# lenOS product configuration.
#
# Inherited from device/nothing/asteroids/lenos_asteroids.mk (see
# patches/device_nothing_asteroids/0001-add-lenos-product.patch).
#
# Branding is ro.lenos.* only. ro.build.*, the build fingerprint and the
# device identity stay stock on purpose: changing them breaks app
# compatibility, attestation and Nothing factory tooling.

# lenOS companion app ("lenOS security"). Everything else in the UI is stock
# LineageOS Settings; this app only hosts controls that Settings does not have.
PRODUCT_PACKAGES += \
    LenosSecurity

# Privacy overlays (enabled at boot, no user interaction required):
# * LenosFrameworksOverlay        - non-Google NTP fallback pool (framework-res)
# * LenosNetworkStackOverlay      - Cloudflare connectivity-check probes
# * LenosSettingsProviderOverlay  - hardened first-boot (Settings.Global) defaults
PRODUCT_PACKAGES += \
    LenosFrameworksOverlay \
    LenosNetworkStackOverlay \
    LenosSettingsProviderOverlay

# Privileged permission allowlist for LenosSecurity. The APK is signed with
# the platform key, so most permissions are already satisfied by the signature;
# the allowlist keeps the app working (and documents the intent) if it is ever
# built without the platform certificate.
PRODUCT_COPY_FILES += \
    vendor/lenos/config/privapp-permissions-org.lenos.security.xml:$(TARGET_COPY_OUT_SYSTEM)/etc/permissions/privapp-permissions-org.lenos.security.xml

# Product properties are loaded last by init, so they override values from
# system/system_ext/vendor/odm (see system/core/init/property_service.cpp).
# Keep this list short and commented; anything user-visible belongs in the
# SettingsProvider defaults or a documented toggle instead.
PRODUCT_PRODUCT_PROPERTIES += \
    ro.lenos.version=1.0.0 \
    ro.lenos.base=lineage-23.2 \
    ro.lenos.dns=dns.quad9.net \
    # Auto-reboot-to-BFU backend: framework system service
    # (LenosAutoRebootService, frameworks/base). Status string for the lenOS
    # security app; the timer value lives in Settings.Global.
    ro.lenos.security.auto_bfu=framework \
    # Duress credential backend: LockSettingsService (frameworks/base/0005)
    # with the lenOS security app as UI. Destructive by design; entering a
    # duress credential at any prompt destroys the storage keys. Status string
    # for the app.
    ro.lenos.security.duress=framework \
    persist.traced.enable=0 \
    persist.logd.size.radio=64K \
    persist.vendor.verbose_logging_enabled=0 \
    persist.vendor.radio.adb_log_on=0 \
    persist.vendor.radio.ims_log_enabled=0 \
    persist.vendor.sys.modem.logging.enable=0 \
    persist.vendor.radio.snapshot_enabled=0 \
    persist.vendor.radio.snapshot_timer=0
