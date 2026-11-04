package io.github.pedroguille.folio;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Locale;

/** All exported bytes reach a private recovery file before a document provider is opened. */
final class Storage {
    static final long MAX_BYTES = 100L * 1024 * 1024;
    private Storage() {}

    static String safeName(String value) {
        String name = value == null ? "Documento" : value.replace('\\', '/');
        name = name.substring(name.lastIndexOf('/') + 1).replaceAll("[\\p{Cntrl}]", "").trim();
        if (name.isEmpty() || name.equals(".") || name.equals("..")) name = "Documento";
        int points = name.codePointCount(0, name.length());
        return points > 180 ? name.substring(name.offsetByCodePoints(0, points - 180)) : name;
    }

    static String mime(String name) {
        String n = name.toLowerCase(Locale.ROOT);
        if (n.endsWith(".docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        if (n.endsWith(".xlsx")) return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
        if (n.endsWith(".pptx")) return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
        if (n.endsWith(".pdf")) return "application/pdf";
        if (n.endsWith(".csv")) return "text/csv";
        if (n.endsWith(".html")) return "text/html";
        if (n.endsWith(".rtf")) return "application/rtf";
        if (n.endsWith(".doc")) return "application/msword";
        if (n.endsWith(".xls")) return "application/vnd.ms-excel";
        if (n.endsWith(".png")) return "image/png";
        if (n.endsWith(".jpg") || n.endsWith(".jpeg")) return "image/jpeg";
        if (n.endsWith(".txt") || n.endsWith(".md") || n.endsWith(".tsv")) return "text/plain";
        return "application/octet-stream";
    }

    static long copy(InputStream in, OutputStream out, long limit) throws IOException {
        byte[] buffer = new byte[65536];
        long total = 0;
        int count;
        while ((count = in.read(buffer)) != -1) {
            total += count;
            if (total > limit) throw new IOException("Este archivo supera el límite de 100 MB.");
            out.write(buffer, 0, count);
        }
        return total;
    }

    static File directory(Context context) {
        File dir = new File(context.getFilesDir(), "recovery");
        if (!dir.isDirectory() && !dir.mkdirs()) return null;
        return dir;
    }

    static SharedPreferences prefs(Context context) { return context.getSharedPreferences("folio", Context.MODE_PRIVATE); }

    static synchronized JSONArray recoveries(Context context) {
        try { return new JSONArray(prefs(context).getString("recoveries", "[]")); }
        catch (JSONException e) { return new JSONArray(); }
    }

    static synchronized JSONObject find(Context context, String id) {
        if (id == null) return null;
        JSONArray all = recoveries(context);
        for (int i = 0; i < all.length(); i++) {
            JSONObject item = all.optJSONObject(i);
            if (item != null && id.equals(item.optString("id"))) return item;
        }
        return null;
    }

    static synchronized void addRecovery(Context context, JSONObject item) throws IOException {
        JSONArray all = recoveries(context);
        JSONArray next = new JSONArray();
        next.put(item);
        for (int i = 0; i < all.length(); i++) {
            JSONObject old = all.optJSONObject(i);
            if (old != null && !old.optString("id").equals(item.optString("id"))) next.put(old);
        }
        // Never silently evict a saved recovery. The user can delete it explicitly from Home.
        if (!prefs(context).edit().putString("recoveries", next.toString()).commit()) {
            throw new IOException("No se pudo registrar la copia guardada.");
        }
    }

    static File recoveryFile(Context context, String id) {
        if (id == null || !id.matches("[a-f0-9-]{36}")) return null;
        File dir = directory(context);
        return dir == null ? null : new File(dir, id + ".saved");
    }

    static synchronized boolean deleteRecovery(Context context, String id) {
        JSONArray next = new JSONArray();
        JSONArray all = recoveries(context);
        for (int i = 0; i < all.length(); i++) {
            JSONObject entry = all.optJSONObject(i);
            if (entry != null && !id.equals(entry.optString("id"))) next.put(entry);
        }
        if (!prefs(context).edit().putString("recoveries", next.toString()).commit()) return false;
        File file = recoveryFile(context, id);
        return file == null || !file.exists() || file.delete();
    }
}
