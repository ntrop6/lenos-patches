package org.lenos.opsec;

import android.content.ContentResolver;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.ImageDecoder;
import android.net.Uri;
import android.util.Size;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.UUID;

/** Re-encodes an image so that no EXIF/GPS/XMP/file-name metadata survives. */
final class ImageScrubber {
    private static final int MAX_DIMENSION = 4096;
    private static final int JPEG_QUALITY = 95;

    static final class Result {
        final Uri uri;
        final String mimeType;
        final int width;
        final int height;

        Result(Uri uri, String mimeType, int width, int height) {
            this.uri = uri;
            this.mimeType = mimeType;
            this.width = width;
            this.height = height;
        }
    }

    private ImageScrubber() {
    }

    static Result scrub(Context context, Uri source) throws IOException {
        final ContentResolver resolver = context.getContentResolver();
        String sourceType = resolver.getType(source);
        if (sourceType == null) {
            sourceType = "image/jpeg";
        }
        if ("image/gif".equals(sourceType)) {
            throw new IOException("animated GIF is not supported");
        }

        final ImageDecoder.Source decoderSource = ImageDecoder.createSource(resolver, source);
        final Bitmap bitmap;
        try {
            bitmap = ImageDecoder.decodeBitmap(decoderSource, (decoder, info, src) -> {
                final Size size = info.getSize();
                final int largest = Math.max(size.getWidth(), size.getHeight());
                if (largest > MAX_DIMENSION) {
                    final double scale = (double) MAX_DIMENSION / largest;
                    decoder.setTargetSize(
                            Math.max(1, (int) (size.getWidth() * scale)),
                            Math.max(1, (int) (size.getHeight() * scale)));
                }
            });
        } catch (ImageDecoder.DecodeException e) {
            throw new IOException("unable to decode image", e);
        }

        final String outputType;
        final Bitmap.CompressFormat format;
        final String extension;
        if ("image/png".equals(sourceType)) {
            outputType = "image/png";
            format = Bitmap.CompressFormat.PNG;
            extension = "png";
        } else if ("image/webp".equals(sourceType)) {
            outputType = "image/webp";
            format = Bitmap.CompressFormat.WEBP_LOSSY;
            extension = "webp";
        } else {
            outputType = "image/jpeg";
            format = Bitmap.CompressFormat.JPEG;
            extension = "jpg";
        }

        final File dir = new File(context.getCacheDir(), "scrubbed");
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IOException("unable to create cache directory");
        }
        final int width = bitmap.getWidth();
        final int height = bitmap.getHeight();
        final File output = new File(dir, UUID.randomUUID() + "." + extension);
        try (FileOutputStream out = new FileOutputStream(output)) {
            if (!bitmap.compress(format, JPEG_QUALITY, out)) {
                throw new IOException("unable to encode image");
            }
        } finally {
            bitmap.recycle();
        }

        return new Result(Uri.fromFile(output), outputType, width, height);
    }
}
