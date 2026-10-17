/*
 * Copyright (C) 2024 GrapheneOS
 * Copyright (C) 2026 lenOS adaptation
 * SPDX-License-Identifier: Apache-2.0
 */
package com.android.settings.security;

import android.content.Context;
import android.os.UserHandle;
import android.provider.Settings;
import android.util.Log;

import androidx.preference.ListPreference;
import androidx.preference.Preference;

import com.android.settings.R;
import com.android.settings.core.BasePreferenceController;

import java.util.Set;

/** Controls the init-owned inactivity reboot timer. */
public class AutoRebootPreferenceController extends BasePreferenceController
        implements Preference.OnPreferenceChangeListener {
    private static final String TAG = "AutoRebootPref";
    private static final String SETTING = "lenos_auto_reboot_timeout_ms";
    private static final int DEFAULT_TIMEOUT_MILLIS = 64_800_000; // 18 hours
    private static final Set<Integer> ALLOWED_VALUES = Set.of(
            0, 600_000, 1_800_000, 3_600_000, 7_200_000, 14_400_000,
            28_800_000, 43_200_000, 64_800_000, 86_400_000, 129_600_000,
            172_800_000, 259_200_000);

    public AutoRebootPreferenceController(Context context, String preferenceKey) {
        super(context, preferenceKey);
    }

    @Override
    public int getAvailabilityStatus() {
        return UserHandle.myUserId() == UserHandle.USER_SYSTEM
                ? AVAILABLE : DISABLED_FOR_USER;
    }

    @Override
    public void displayPreference(androidx.preference.PreferenceScreen screen) {
        super.displayPreference(screen);
        Preference preference = screen.findPreference(getPreferenceKey());
        if (preference != null) {
            preference.setOnPreferenceChangeListener(this);
        }
    }

    @Override
    public void updateState(Preference preference) {
        if (!(preference instanceof ListPreference listPreference)) {
            return;
        }
        int value = Settings.Global.getInt(mContext.getContentResolver(),
                SETTING, DEFAULT_TIMEOUT_MILLIS);
        if (!ALLOWED_VALUES.contains(value)) {
            value = DEFAULT_TIMEOUT_MILLIS;
        }
        String stringValue = Integer.toString(value);
        listPreference.setValue(stringValue);
        int index = listPreference.findIndexOfValue(stringValue);
        if (value == 0) {
            listPreference.setSummary(R.string.auto_reboot_summary_off);
        } else if (index >= 0) {
            listPreference.setSummary(mContext.getString(R.string.auto_reboot_summary,
                    listPreference.getEntries()[index]));
        } else {
            listPreference.setSummary(R.string.auto_reboot_footer);
        }
    }

    @Override
    public boolean onPreferenceChange(Preference preference, Object newValue) {
        final int value;
        try {
            value = Integer.parseInt(String.valueOf(newValue));
        } catch (NumberFormatException e) {
            Log.e(TAG, "invalid timeout", e);
            return false;
        }
        if (!ALLOWED_VALUES.contains(value)) {
            Log.e(TAG, "rejected unsupported timeout: " + value);
            return false;
        }
        if (!Settings.Global.putInt(mContext.getContentResolver(), SETTING, value)) {
            return false;
        }
        updateState(preference);
        return true;
    }
}
