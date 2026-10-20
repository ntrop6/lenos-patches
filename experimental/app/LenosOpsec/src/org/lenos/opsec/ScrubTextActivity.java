package org.lenos.opsec;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

/** Share target that strips known tracking parameters from links in shared text. */
public class ScrubTextActivity extends Activity {
    private EditText mText;
    private TextView mStatus;
    private Button mRemove;
    private Button mShare;
    private Button mCopy;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_scrub_text);
        mText = findViewById(R.id.text);
        mStatus = findViewById(R.id.status);
        mRemove = findViewById(R.id.remove);
        mShare = findViewById(R.id.share);
        mCopy = findViewById(R.id.copy);

        final Intent intent = getIntent();
        CharSequence shared = intent == null ? null : intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
        if (shared == null && intent != null) {
            shared = intent.getStringExtra(Intent.EXTRA_TEXT);
        }
        final String text = shared == null ? "" : shared.toString();

        findViewById(R.id.cancel).setOnClickListener(v -> finish());
        mRemove.setOnClickListener(v -> applyScrub(false));
        mShare.setOnClickListener(v -> applyScrub(true));
        mCopy.setOnClickListener(v -> copyCleaned());

        if (text.isEmpty()) {
            mStatus.setText(R.string.scrub_text_nothing);
            setButtonsEnabled(false);
        } else {
            mText.setText(text);
            mText.setSelection(0);
            setButtonsEnabled(true);
        }
    }

    private void applyScrub(boolean share) {
        final LinkScrubber.Result result = LinkScrubber.scrub(mText.getText().toString());
        mText.setText(result.text);
        mText.setSelection(0);
        if (result.removed == 0) {
            mStatus.setText(R.string.scrub_text_clean);
        } else {
            mStatus.setText(getString(R.string.scrub_text_removed, result.removed));
        }
        if (share) {
            share(result.text);
        }
    }

    private void copyCleaned() {
        final LinkScrubber.Result result = LinkScrubber.scrub(mText.getText().toString());
        mText.setText(result.text);
        final ClipboardManager clipboard = getSystemService(ClipboardManager.class);
        if (clipboard != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText(
                    getString(R.string.scrub_text_clip_label), result.text));
            Toast.makeText(this, R.string.scrub_text_copied, Toast.LENGTH_SHORT).show();
        }
    }

    private void share(String text) {
        final Intent share = new Intent(Intent.ACTION_SEND);
        share.setType("text/plain");
        share.putExtra(Intent.EXTRA_TEXT, text);
        startActivity(Intent.createChooser(share, getString(R.string.scrub_text_title)));
    }

    private void setButtonsEnabled(boolean enabled) {
        mRemove.setEnabled(enabled);
        mShare.setEnabled(enabled);
        mCopy.setEnabled(enabled);
    }
}
