# lenOS 1.0.0-shizuku — inherited from device/nothing/asteroids/lineage_asteroids.mk
# Branding is ro.lenos.* only. Do not touch PRODUCT_BUILD_PROP / fingerprint.

PRODUCT_PACKAGES += LenosSecurity ExactCalculator

PRODUCT_PACKAGE_OVERLAYS += vendor/lenos/overlay

PRODUCT_COPY_FILES += \
    vendor/lenos/config/privapp-permissions-org.lenos.security.xml:$(TARGET_COPY_OUT_SYSTEM)/etc/permissions/privapp-permissions-org.lenos.security.xml

PRODUCT_PACKAGES_REMOVE += \
    Jelly \
    Browser2 \
    Gallery2 \
    FMRadio \
    Eleven \
    AudioFX \
    LiveWallpapersPicker \
    Email \
    Updater \
    Glimpse \
    MatLog \
    WeatherProvider \
    OpenWeatherMapProvider \
    Calendar

PRODUCT_SYSTEM_EXT_PROPERTIES += \
    persist.traced.enable=0 \
    persist.vendor.verbose_logging_enabled=0 \
    persist.vendor.radio.adb_log_on=0 \
    persist.vendor.radio.ims_log_enabled=0 \
    persist.vendor.sys.modem.logging.enable=0 \
    persist.vendor.radio.snapshot_enabled=0 \
    persist.vendor.radio.snapshot_timer=0 \
    net.hostname=
