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

# HTS-1: hardened thread-stack layout in bionic. This is deliberately off even
# in an experimental build unless the build explicitly opts in. The bionic
# patch reads the read-only property; an absent/false value keeps the stock
# thread mapping. See experimental/docs/verification.md before enabling it.
ifneq ($(filter 1 true yes,$(LENOS_HARDENED_THREAD_STACKS)),)
PRODUCT_PRODUCT_PROPERTIES += \
    ro.lenos.hardened_thread_stacks=1
endif
