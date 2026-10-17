"""Duress eSIM wipe (GrapheneOS EuiccWipe port).

Feature contract (see docs/features.md):
* Entering a duress credential erases every profile on every eUICC before the
  device powers off. The cryptographic erase (KeyMint keys + Secretkeeper)
  happens regardless and never waits for the eUICC; the eSIM wipe runs on its
  own thread with a 3 second budget.
* EuiccWipe (frameworks/base, internal telephony package) enumerates
  TelephonyManager#getUiccSlotsInfo and, for every eUICC slot, calls
  EuiccCardManager#resetMemory with RESET_OPTION_DELETE_OPERATIONAL_PROFILES |
  RESET_OPTION_DELETE_FIELD_LOADED_TEST_PROFILES, waits for all callbacks and
  reports success only if every reset returned RESULT_OK.
* The @hide EuiccCardManager#resetMemory(..., flags) overload +
  RESET_FLAG_IS_FOR_DURESS_WIPE=1 are the only new surface; the public 4-arg
  API delegates with flags=0.
* EuiccCardController (frameworks/opt/telephony) only honors flags from
  SYSTEM_UID (others get a SecurityException) and, when the duress flag is
  set, skips updateEmbeddedSubscriptions() so the carrier does not receive an
  eSIM removal notification while the device is being wiped.
* The IEuiccCardController AIDL carries the flags argument, keeping the phone
  process implementation and the framework API in sync.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest

EUICC_WIPE = "telephony/java/com/android/internal/telephony/euicc/EuiccWipe.java"
CARD_MANAGER = "telephony/java/android/telephony/euicc/EuiccCardManager.java"
CONTROLLER_AIDL = (
    "telephony/java/com/android/internal/telephony/euicc/IEuiccCardController.aidl")
CONTROLLER = "src/java/com/android/internal/telephony/euicc/EuiccCardController.java"
WIPE = "services/core/java/com/android/server/locksettings/DuressWipe.java"
HELPER = "services/core/java/com/android/server/locksettings/DuressPasswordHelper.java"


class TestEuiccWipeHelper(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0007-lenos-esim-duress-wipe.patch"]

    def test_java_still_parses(self):
        self.assert_java_syntax(EUICC_WIPE)
        self.assert_java_syntax(CARD_MANAGER)

    def test_helper_resets_every_euicc_slot(self):
        self.assert_contains(
            EUICC_WIPE,
            "public class EuiccWipe {",
            "public static boolean run(Context ctx, int flags)",
            "ctx.getSystemService(TelephonyManager.class)",
            "ctx.getSystemService(EuiccCardManager.class)",
            "telephonyManager.getUiccSlotsInfo()",
            "usi.getIsEuicc()",
            "usi.getCardId()",
            "euiccCardManager.resetMemory(cardId, opts, callbackExecutor, cb, flags);",
        )

    def test_helper_requests_a_full_profile_reset(self):
        self.assert_contains(
            EUICC_WIPE,
            "EuiccCardManager.RESET_OPTION_DELETE_OPERATIONAL_PROFILES",
            "EuiccCardManager.RESET_OPTION_DELETE_FIELD_LOADED_TEST_PROFILES",
            "CompletableFuture.allOf(",
            "if (res.intValue() != EuiccCardManager.RESULT_OK) {",
        )

    def test_card_manager_api_matches_grapheneos(self):
        body = self.text(CARD_MANAGER)
        self.assertIn("resetMemory(cardId, options, executor, callback, 0);", body)
        self.assertIn("public static final int RESET_FLAG_IS_FOR_DURESS_WIPE = 1;", body)
        self.assertIn(
            "public void resetMemory(String cardId, @ResetOption int options,\n"
            "            @CallbackExecutor Executor executor, ResultCallback<Void> callback, "
            "int flags) {",
            body,
        )
        self.assertIn("}, flags);", body)

    def test_aidl_carries_the_flags_argument(self):
        self.assert_contains(
            CONTROLLER_AIDL,
            "oneway void resetMemory(String callingPackage, String cardId, int options, "
            "in IResetMemoryCallback callback, int flags);",
        )


class TestEuiccCardController(LenosPatchTest):
    PROJECT = "frameworks/opt/telephony"
    PATCHES = ["0001-lenos-esim-duress-wipe.patch"]

    def test_java_still_parses(self):
        self.assert_java_syntax(CONTROLLER)

    def test_only_system_uid_can_use_flags(self):
        self.assert_contains(
            CONTROLLER,
            "import android.os.Process;",
            "public void resetMemory(String callingPackage, String cardId,\n"
            "            @EuiccCardManager.ResetOption int options, IResetMemoryCallback "
            "callback, int flags) {",
            "if (Binder.getCallingUid() != Process.SYSTEM_UID) {",
            'throw new SecurityException("only SYSTEM_UID is allowed to use flags");',
        )

    def test_carrier_notification_is_suppressed_for_duress_wipes(self):
        body = self.text(CONTROLLER)
        self.assertIn(
            "if ((flags & EuiccCardManager.RESET_FLAG_IS_FOR_DURESS_WIPE) == 0) {", body)
        gate = body.index("EuiccCardManager.RESET_FLAG_IS_FOR_DURESS_WIPE) == 0")
        refresh = body.index("updateEmbeddedSubscriptions(", gate)
        complete = body.index("callback.onComplete(EuiccCardManager.RESULT_OK);", refresh)
        self.assertLess(refresh, complete)
        self.assertIn("port.resetMemory(options, cardCb, mEuiccMainThreadHandler);", body)


class TestDuressWipeOrdering(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0005-lenos-duress-credentials.patch", "0007-lenos-esim-duress-wipe.patch"]

    def test_esim_wipe_runs_before_the_poweroff(self):
        self.assert_java_syntax(WIPE)
        self.assert_java_syntax(HELPER)
        self.assert_contains(
            WIPE,
            "import com.android.internal.telephony.euicc.EuiccWipe;",
            "EuiccWipe.run(context, EuiccCardManager.RESET_FLAG_IS_FOR_DURESS_WIPE)",
            "EuiccWipeThread.start(context)",
            "euiccWipeThread.await(3000);",
        )
        self.assert_contains(
            HELPER,
            "DuressWipe.run(mLockSettingsService.getContext());",
        )
        body = self.text(WIPE)
        self.assertLess(body.index("EuiccWipeThread.start(context)"),
                        body.index("RecoverySystemService.deleteSecrets();"))
        self.assertLess(body.index("RecoverySystemService.deleteSecrets();"),
                        body.index("euiccWipeThread.await(3000);"))
        self.assertLess(body.index("euiccWipeThread.await(3000);"),
                        body.index("PowerManagerService.lowLevelShutdown(null);"))


if __name__ == "__main__":
    unittest.main()
