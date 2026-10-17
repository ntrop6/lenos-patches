/*
 * Copyright (C) 2026 lenOS
 * SPDX-License-Identifier: Apache-2.0
 */
package com.android.settings.security;

import com.android.settings.R;
import com.android.settings.dashboard.DashboardFragment;
import com.android.settings.search.BaseSearchIndexProvider;
import com.android.settingslib.search.SearchIndexable;

@SearchIndexable
public class LenosDashboardFragment extends DashboardFragment {
    private static final String TAG = "LenosDashboard";

    @Override
    protected int getPreferenceScreenResId() {
        return R.xml.lenos_dashboard;
    }

    @Override
    protected String getLogTag() {
        return TAG;
    }

    @Override
    public int getMetricsCategory() {
        return 0x4c4e53; // 'LNS'
    }

    public static final BaseSearchIndexProvider SEARCH_INDEX_DATA_PROVIDER =
            new BaseSearchIndexProvider(R.xml.lenos_dashboard);
}
