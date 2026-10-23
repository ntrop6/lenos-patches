# lenOS experimental product fragment.
#
# Inherited from config/lenos.mk only when LENOS_EXPERIMENTAL is 1/true/yes.
# The build helper sets that flag for both patch application and the build, and
# installs experimental/app/ into $SRC/vendor/lenos/app/ only in this mode.
# A default 1.0 build neither includes this fragment nor has the app source.
#
# Everything here is source-complete but not build- or device-validated. See
# experimental/STATUS.md and experimental/docs/verification.md before using it.

PRODUCT_PACKAGES += \
    LenosOpsec

# Makes an experimental image identifiable at runtime. This is not a security
# boundary and must not be treated as one.
PRODUCT_PRODUCT_PROPERTIES += \
    ro.lenos.experimental=1

# HTS-1: hardened thread-stack layout in bionic. The property belongs to the
# experimental series, so it is present only when this fragment is inherited
# (LENOS_EXPERIMENTAL=1). The stable/default build keeps the stock thread
# mapping. See experimental/docs/verification.md before relying on it.
PRODUCT_PRODUCT_PROPERTIES += \
    ro.lenos.hardened_thread_stacks=1
