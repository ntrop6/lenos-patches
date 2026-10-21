package org.lenos.security;

import android.app.Application;
import android.util.Log;

/**
 * Logs any uncaught throwable to a file so a crash is diagnosable even when
 * the user can't see logcat. The Activity itself also renders its own stack.
 */
public class CrashApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        // Capture the real handler before installing this one. Reading the
        // default inside the lambda would return this lambda and recurse.
        final Thread.UncaughtExceptionHandler previous =
                Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((t, e) -> {
            Log.e("lenOS-security", "uncaught in " + t, e);
            try {
                java.io.File f = new java.io.File(getFilesDir(), "last-crash.txt");
                java.io.PrintWriter pw = new java.io.PrintWriter(f);
                e.printStackTrace(pw);
                pw.close();
            } catch (Exception ignored) {
            }
            // Delegate to the real default handler so the process still dies
            // and Android shows the system crash dialog rather than hanging.
            if (previous != null) {
                previous.uncaughtException(t, e);
            }
        });
    }
}
