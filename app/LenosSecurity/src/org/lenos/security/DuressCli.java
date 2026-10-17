package org.lenos.security;

import android.content.Context;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;

/**
 * Runs as root via {@code app_process} so Binder calls are uid 0.
 *
 * Stdin protocol (one field per line; secrets never on argv):
 *   HAS\n<ownerPin>\n
 *   SET\n<ownerPin>\n<duressPin>\n<duressPassword>\n
 *   DELETE\n<ownerPin>\n
 */
public final class DuressCli {
    public static void main(String[] args) {
        int code = 1;
        try {
            Context ctx = systemContext();
            LockBridge lock = new LockBridge(ctx);
            BufferedReader in = new BufferedReader(
                    new InputStreamReader(System.in, StandardCharsets.UTF_8));
            String cmd = line(in);
            if ("HAS".equals(cmd)) {
                Object owner = lock.createPin(line(in));
                try {
                    boolean has = lock.hasDuress(owner);
                    System.out.println(has ? "HAS=1" : "HAS=0");
                } finally {
                    lock.zeroize(owner);
                }
                code = 0;
            } else if ("SET".equals(cmd)) {
                Object owner = lock.createPin(line(in));
                Object pin = lock.createPin(line(in));
                Object pass = lock.createPassword(line(in));
                try {
                    lock.setDuress(owner, pin, pass);
                    System.out.println("SET=OK");
                } finally {
                    lock.zeroize(owner);
                    lock.zeroize(pin);
                    lock.zeroize(pass);
                }
                code = 0;
            } else if ("DELETE".equals(cmd)) {
                Object owner = lock.createPin(line(in));
                try {
                    lock.deleteDuress(owner);
                    System.out.println("DELETE=OK");
                } finally {
                    lock.zeroize(owner);
                }
                code = 0;
            } else {
                System.err.println("unknown command");
            }
        } catch (Throwable t) {
            System.err.println(t.getClass().getSimpleName() + ": " + t.getMessage());
            code = 2;
        }
        System.exit(code);
    }

    private static Context systemContext() throws Exception {
        Class<?> looper = Class.forName("android.os.Looper");
        looper.getMethod("prepareMainLooper").invoke(null);
        Class<?> at = Class.forName("android.app.ActivityThread");
        at.getMethod("systemMain").invoke(null);
        Object thread = at.getMethod("currentActivityThread").invoke(null);
        Method get = at.getMethod("getSystemContext");
        return (Context) get.invoke(thread);
    }

    private static String line(BufferedReader in) throws Exception {
        String s = in.readLine();
        if (s == null) {
            throw new IllegalArgumentException("short input");
        }
        return s;
    }
}
