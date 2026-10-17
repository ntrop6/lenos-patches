/*
 * Copyright (C) 2026 lenOS
 * SPDX-License-Identifier: Apache-2.0
 */
package com.android.settings.security;

import android.content.Context;
import android.os.UserHandle;

import com.android.internal.widget.LockPatternUtils;
import com.android.settings.core.BasePreferenceController;
import com.android.settings.overlay.FeatureFactory;

/** Exposes duress setup only to the secured Owner user. */
public class DuressPasswordPreferenceController extends BasePreferenceController {
    private final LockPatternUtils mLockPatternUtils;

    public DuressPasswordPreferenceController(Context context, String preferenceKey) {
        super(context, preferenceKey);
        mLockPatternUtils = FeatureFactory.getFeatureFactory()
                .getSecurityFeatureProvider().getLockPatternUtils(context);
    }

    @Override
    public int getAvailabilityStatus() {
        if (UserHandle.myUserId() != UserHandle.USER_SYSTEM) {
            return DISABLED_FOR_USER;
        }
        return mLockPatternUtils.isSecure(UserHandle.USER_SYSTEM)
                ? AVAILABLE : CONDITIONALLY_UNAVAILABLE;
    }
}
