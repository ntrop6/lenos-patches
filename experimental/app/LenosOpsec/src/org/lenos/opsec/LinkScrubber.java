package org.lenos.opsec;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Removes common link-tracking parameters without opening or resolving the links. */
final class LinkScrubber {
    private static final Pattern URL_PATTERN = Pattern.compile("https?://[^\\s<>\"']+");

    private static final Set<String> TRACKING_PARAMETERS = new HashSet<>(Arrays.asList(
            "fbclid", "gclid", "dclid", "msclkid", "yclid", "twclid", "igshid",
            "mc_cid", "mc_eid", "_ga", "_gl", "gclsrc", "srsltid", "gad_source",
            "wbraid", "gbraid", "mkt_tok", "elqtrackid", "elqtrack", "sc_cid",
            "si", "ref", "ref_src", "ref_url"));

    private LinkScrubber() {
    }

    static final class Result {
        final String text;
        final int removed;

        Result(String text, int removed) {
            this.text = text;
            this.removed = removed;
        }
    }

    static Result scrub(String input) {
        if (input == null || input.isEmpty()) {
            return new Result(input == null ? "" : input, 0);
        }
        final Matcher matcher = URL_PATTERN.matcher(input);
        final StringBuilder output = new StringBuilder(input.length());
        int last = 0;
        int removed = 0;
        while (matcher.find()) {
            output.append(input, last, matcher.start());
            final CleanedUrl cleaned = clean(matcher.group());
            output.append(cleaned.url);
            removed += cleaned.removed;
            last = matcher.end();
        }
        output.append(input, last, input.length());
        return new Result(output.toString(), removed);
    }

    private static CleanedUrl clean(String url) {
        final int hash = url.indexOf('#');
        final String fragment = hash >= 0 ? url.substring(hash) : "";
        final String withoutFragment = hash >= 0 ? url.substring(0, hash) : url;
        final int queryStart = withoutFragment.indexOf('?');
        if (queryStart < 0) {
            return new CleanedUrl(url, 0);
        }

        final String prefix = withoutFragment.substring(0, queryStart);
        final String query = withoutFragment.substring(queryStart + 1);
        final StringBuilder kept = new StringBuilder();
        int removed = 0;
        for (String part : query.split("&", -1)) {
            final int equals = part.indexOf('=');
            final String name = (equals >= 0 ? part.substring(0, equals) : part)
                    .toLowerCase(java.util.Locale.ROOT);
            if (isTracking(name)) {
                removed++;
                continue;
            }
            if (kept.length() > 0) {
                kept.append('&');
            }
            kept.append(part);
        }
        if (removed == 0) {
            return new CleanedUrl(url, 0);
        }
        final String cleaned = kept.length() == 0 ? prefix : prefix + "?" + kept;
        return new CleanedUrl(cleaned + fragment, removed);
    }

    private static boolean isTracking(String name) {
        if (name.startsWith("utm_") || name.startsWith("pk_") || name.startsWith("mtm_")
                || name.startsWith("hsa_") || name.startsWith("vero_")
                || name.startsWith("oly_")) {
            return true;
        }
        return TRACKING_PARAMETERS.contains(name);
    }

    private static final class CleanedUrl {
        final String url;
        final int removed;

        CleanedUrl(String url, int removed) {
            this.url = url;
            this.removed = removed;
        }
    }
}
