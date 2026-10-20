package org.lenos.opsec;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Share target that removes metadata before handing images to another app. */
public class ScrubActivity extends Activity {
    private static final int MAX_IMAGES = 20;

    private final ExecutorService mExecutor = Executors.newSingleThreadExecutor();
    private final Handler mMain = new Handler(Looper.getMainLooper());
    private final ArrayList<Uri> mSources = new ArrayList<>();

    private ImageView mPreview;
    private TextView mStatus;
    private ProgressBar mProgress;
    private Button mShare;
    private Button mSave;
    private Button mCancel;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_scrub);
        mPreview = findViewById(R.id.preview);
        mStatus = findViewById(R.id.status);
        mProgress = findViewById(R.id.progress);
        mShare = findViewById(R.id.share);
        mSave = findViewById(R.id.save);
        mCancel = findViewById(R.id.cancel);

        collectSources(getIntent());
        mCancel.setOnClickListener(v -> finish());
        if (mSources.isEmpty()) {
            mStatus.setText(R.string.scrub_nothing);
            setButtonsEnabled(false);
        } else if (mSources.size() > MAX_IMAGES) {
            mStatus.setText(R.string.scrub_too_many);
            setButtonsEnabled(false);
        } else {
            mPreview.setImageURI(mSources.get(0));
            mShare.setOnClickListener(v -> process(false));
            mSave.setOnClickListener(v -> process(true));
            setButtonsEnabled(true);
        }
    }

    private void collectSources(Intent intent) {
        if (intent == null) {
            return;
        }
        if (Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction())) {
            ArrayList<Uri> uris = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (uris != null) {
                mSources.addAll(uris);
            }
        } else {
            Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (uri != null) {
                mSources.add(uri);
            } else if (intent.getData() != null) {
                mSources.add(intent.getData());
            }
        }
    }

    private void process(boolean save) {
        setButtonsEnabled(false);
        mProgress.setVisibility(View.VISIBLE);
        mStatus.setText(R.string.scrub_working);
        mExecutor.execute(() -> {
            try {
                final List<ImageScrubber.Result> results = new ArrayList<>();
                for (Uri source : mSources) {
                    results.add(ImageScrubber.scrub(this, source));
                }
                if (save) {
                    for (ImageScrubber.Result result : results) {
                        saveToMediaStore(result);
                    }
                }
                mMain.post(() -> {
                    mProgress.setVisibility(View.GONE);
                    if (save) {
                        mStatus.setText(getString(R.string.scrub_saved, results.size()));
                        setButtonsEnabled(false);
                    } else {
                        mStatus.setText(R.string.scrub_shared);
                        share(results);
                    }
                });
            } catch (Exception e) {
                mMain.post(() -> {
                    mProgress.setVisibility(View.GONE);
                    setButtonsEnabled(true);
                    mStatus.setText(R.string.scrub_failed);
                    Toast.makeText(this, R.string.scrub_failed, Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void share(List<ImageScrubber.Result> results) {
        final ArrayList<Uri> uris = new ArrayList<>();
        String type = results.get(0).mimeType;
        for (ImageScrubber.Result result : results) {
            uris.add(FileProvider.getUriForFile(this, getPackageName() + ".files", new File(
                    result.uri.getPath())));
            if (!type.equals(result.mimeType)) {
                type = "image/*";
            }
        }
        final Intent intent;
        if (uris.size() == 1) {
            intent = new Intent(Intent.ACTION_SEND).putExtra(Intent.EXTRA_STREAM, uris.get(0));
        } else {
            intent = new Intent(Intent.ACTION_SEND_MULTIPLE).putParcelableArrayListExtra(
                    Intent.EXTRA_STREAM, uris);
        }
        intent.setType(type);
        final ClipData clip = ClipData.newRawUri("", uris.get(0));
        for (int i = 1; i < uris.size(); i++) {
            clip.addItem(new ClipData.Item(uris.get(i)));
        }
        intent.setClipData(clip);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivity(Intent.createChooser(intent, getString(R.string.scrub_title)));
    }

    private void saveToMediaStore(ImageScrubber.Result result) throws IOException {
        final String extension = result.mimeType.equals("image/png") ? "png"
                : result.mimeType.equals("image/webp") ? "webp" : "jpg";
        final ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME,
                "lenos-" + System.currentTimeMillis() + "-" + extension);
        values.put(MediaStore.Images.Media.MIME_TYPE, result.mimeType);
        values.put(MediaStore.Images.Media.RELATIVE_PATH,
                Environment.DIRECTORY_PICTURES + "/lenOS");
        values.put(MediaStore.Images.Media.IS_PENDING, 1);
        final Uri target = getContentResolver().insert(
                MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), values);
        if (target == null) {
            throw new IOException("unable to create MediaStore entry");
        }
        try (FileInputStream in = new FileInputStream(result.uri.getPath());
             OutputStream out = getContentResolver().openOutputStream(target)) {
            if (out == null) {
                throw new IOException("unable to open MediaStore entry");
            }
            final byte[] buffer = new byte[16 * 1024];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
        } catch (IOException e) {
            getContentResolver().delete(target, null, null);
            throw e;
        }
        values.clear();
        values.put(MediaStore.Images.Media.IS_PENDING, 0);
        getContentResolver().update(target, values, null, null);
    }

    private void setButtonsEnabled(boolean enabled) {
        mShare.setEnabled(enabled);
        mSave.setEnabled(enabled);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        mExecutor.shutdownNow();
    }
}
