package io.github.pedroguille.folio;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import org.json.JSONObject;
import java.io.File;
import java.io.FileNotFoundException;

/** Read-only, per-URI access granted only when the user invokes Android's share sheet. */
public final class RecoveryProvider extends ContentProvider {
    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri uri) {
        JSONObject item = Storage.find(getContext(), uri.getLastPathSegment());
        return item == null ? "application/octet-stream" : Storage.mime(item.optString("name"));
    }
    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
        JSONObject item = Storage.find(getContext(), uri.getLastPathSegment());
        if (item == null) return null;
        String[] columns = projection == null ? new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE} : projection;
        MatrixCursor cursor = new MatrixCursor(columns);
        Object[] row = new Object[columns.length];
        for (int i = 0; i < columns.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(columns[i])) row[i] = item.optString("name");
            else if (OpenableColumns.SIZE.equals(columns[i])) row[i] = item.optLong("size");
        }
        cursor.addRow(row);
        return cursor;
    }
    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!"r".equals(mode) || Storage.find(getContext(), uri.getLastPathSegment()) == null) throw new FileNotFoundException();
        File file = Storage.recoveryFile(getContext(), uri.getLastPathSegment());
        if (file == null || !file.isFile()) throw new FileNotFoundException();
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public Uri insert(Uri u, ContentValues v) { throw new UnsupportedOperationException("Solo lectura"); }
    @Override public int delete(Uri u, String s, String[] a) { throw new UnsupportedOperationException("Solo lectura"); }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException("Solo lectura"); }
}
