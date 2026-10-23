/*
 * Copyright (C) 2026 ShadowBladeX
 * SPDX-License-Identifier: Apache-2.0
 */
package org.aospextended.device.performance;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

import org.aospextended.device.util.Utils;

/** Manual profiles; privileged system access is provisioned by device init/SELinux. */
public final class KProfilesSettings {
    public static final String NODE = "/sys/kernel/kprofiles/kp_mode";
    public static final String KEY = "kprofiles_mode";
    private static final String TAG = "KProfilesSettings";

    private static boolean isValid(String value) {
        return "0".equals(value) || "1".equals(value)
                || "2".equals(value) || "3".equals(value);
    }

    public static String getCurrent() {
        String value = Utils.readLine(NODE);
        if (value != null) value = value.trim();
        return isValid(value) ? value : null;
    }

    public static boolean isSupported() {
        return Utils.fileWritable(NODE) && getCurrent() != null;
    }

    public static boolean setValue(Context context, String value) {
        if (!isValid(value) || !isSupported()) return false;
        try (FileOutputStream stream = new FileOutputStream(NODE)) {
            stream.write(value.getBytes(StandardCharsets.US_ASCII));
        } catch (IOException | SecurityException e) {
            Log.w(TAG, "Unable to apply performance profile", e);
            return false;
        }
        if (!value.equals(getCurrent())) return false;
        Utils.getSharedPreferences(context).edit().putString(KEY, value).apply();
        return true;
    }

    public static void restore(Context context) {
        SharedPreferences prefs = Utils.getSharedPreferences(context);
        if (!prefs.contains(KEY) || !isSupported()) return;
        String value;
        try {
            value = prefs.getString(KEY, "0");
        } catch (ClassCastException e) {
            value = "0";
        }
        setValue(context, isValid(value) ? value : "0");
    }
}
