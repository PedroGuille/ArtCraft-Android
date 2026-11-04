package io.github.pedroguille.folio;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.res.Configuration;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.util.Base64;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.webkit.JavascriptInterface;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    static final String ORIGIN = "https://folio.invalid";
    private static final int OPEN = 101, CHOOSE = 102, SAVE = 103;
    private WebView web;
    private FrameLayout container;
    private boolean ready;
    private boolean darkAppearance;
    private boolean pickerShowing;
    private ValueCallback<Uri[]> chooser;
    private Intent pendingIntent;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Map<String, File> documents = new ConcurrentHashMap<>();
    private final Map<String, SaveJob> jobs = new ConcurrentHashMap<>();
    private final ArrayDeque<String> saveQueue = new ArrayDeque<>();
    private String activeSave;

    private static final class SaveJob {
        String id, name;
        long size, written;
        File file;
        FileOutputStream output;
        boolean complete;
    }

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override public void onCreate(Bundle state) {
        // Restore the native surfaces before the WebView sends its saved appearance.
        darkAppearance = Storage.prefs(this).getBoolean("darkAppearanceV2", true);
        setTheme(darkAppearance ? R.style.AppTheme_Dark : R.style.AppTheme);
        super.onCreate(state);
        if (android.os.Build.VERSION.SDK_INT >= 29) {
            getWindow().setStatusBarContrastEnforced(false);
            getWindow().setNavigationBarContrastEnforced(false);
        }
        if (android.os.Build.VERSION.SDK_INT >= 28) {
            android.view.WindowManager.LayoutParams attributes = getWindow().getAttributes();
            attributes.layoutInDisplayCutoutMode = android.view.WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            getWindow().setAttributes(attributes);
        }
        web = new WebView(this);
        container = new FrameLayout(this);
        container.addView(web, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(container);
        // In split screen Android requires visible system bars. Paint behind them,
        // but inset the editor exactly once so tabs and document controls stay usable.
        container.setOnApplyWindowInsetsListener((view, insets) -> {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                int types = WindowInsets.Type.ime() | WindowInsets.Type.displayCutout();
                if (isInMultiWindowMode()) types |= WindowInsets.Type.systemBars();
                android.graphics.Insets safe = insets.getInsets(types);
                view.setPadding(safe.left, safe.top, safe.right, safe.bottom);
            } else {
                // Legacy immersive windows may report the stable navigation inset even while
                // hidden. Only a keyboard-sized bottom inset needs document padding.
                int bottom = insets.getSystemWindowInsetBottom();
                int keyboard = bottom > getResources().getDisplayMetrics().heightPixels / 5 ? bottom : 0;
                android.view.DisplayCutout cutout = android.os.Build.VERSION.SDK_INT >= 28 ? insets.getDisplayCutout() : null;
                boolean split = isInMultiWindowMode();
                view.setPadding(Math.max(split ? insets.getSystemWindowInsetLeft() : 0, cutout == null ? 0 : cutout.getSafeInsetLeft()),
                    Math.max(split ? insets.getSystemWindowInsetTop() : 0, cutout == null ? 0 : cutout.getSafeInsetTop()),
                    Math.max(split ? insets.getSystemWindowInsetRight() : 0, cutout == null ? 0 : cutout.getSafeInsetRight()),
                    Math.max(split ? bottom : keyboard, cutout == null ? 0 : cutout.getSafeInsetBottom()));
            }
            return insets;
        });
        applyWindowAppearance();
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true); // Only URIs chosen through the system picker.
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setTextZoom(100);
        settings.setDatabaseEnabled(false);
        web.addJavascriptInterface(new Bridge(), "AndroidFolio");
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) { return intercept(request.getUrl()); }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                return !("https".equals(uri.getScheme()) && "folio.invalid".equals(uri.getHost()));
            }
            @Override public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
                ready = false;
                new AlertDialog.Builder(MainActivity.this).setTitle("El editor se detuvo").setMessage("Puedes volver a abrir las copias exportadas desde Copias guardadas. Los cambios posteriores a la última exportación podrían haberse perdido.")
                    .setPositiveButton("Volver a abrir Lucy", (d, w) -> recreate()).setNegativeButton("Cerrar", (d, w) -> finish()).show();
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (pickerShowing) { callback.onReceiveValue(null); return true; }
                if (chooser != null) chooser.onReceiveValue(null);
                chooser = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
                String[] types = params.getAcceptTypes();
                if (types != null && types.length > 0 && types[0].contains("/")) intent.putExtra(Intent.EXTRA_MIME_TYPES, types);
                try { pickerShowing = true; startActivityForResult(intent, CHOOSE); }
                catch (Exception e) { pickerShowing = false; chooser.onReceiveValue(null); chooser = null; error("No se pudo abrir el selector de archivos."); }
                return true;
            }
        });
        pendingIntent = getIntent();
        web.loadUrl(ORIGIN + "/index.html");
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, () -> onBackPressed());
        }
        // Incomplete transfers are never presented as valid recoveries.
        File dir = Storage.directory(this);
        if (dir != null) {
            File[] leftovers = dir.listFiles((d, n) -> n.endsWith(".part"));
            if (leftovers != null) for (File file : leftovers) file.delete();
        }
    }

    private void applyWindowAppearance() {
        boolean split = isInMultiWindowMode();
        int color = darkAppearance ? Color.rgb(37,41,37) : Color.rgb(247,248,250);
        setTheme(darkAppearance ? R.style.AppTheme_Dark : R.style.AppTheme);
        // The decor/task backgrounds remain visible when the OS forces bars or
        // briefly draws a resize surface. Coloring only the WebView leaves white bands.
        getWindow().setBackgroundDrawable(new ColorDrawable(color));
        getWindow().setStatusBarColor(color);
        getWindow().setNavigationBarColor(color);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN
            | WindowManager.LayoutParams.FLAG_TRANSLUCENT_STATUS | WindowManager.LayoutParams.FLAG_TRANSLUCENT_NAVIGATION);
        if (container != null) container.setBackgroundColor(color);
        if (web != null) web.setBackgroundColor(color);
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            setTaskDescription(new android.app.ActivityManager.TaskDescription.Builder()
                .setLabel(getString(R.string.app_name)).setIcon(R.mipmap.app_icon).setPrimaryColor(color)
                .setBackgroundColor(color).setStatusBarColor(color).setNavigationBarColor(color).build());
        }
        View decor = getWindow().getDecorView();
        int appearance = darkAppearance ? 0 : View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        int flags = View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE | appearance;
        if (!split) flags |= View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION;
        decor.setSystemUiVisibility(flags);
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            android.view.WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) {
                int light = android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                controller.setSystemBarsAppearance(darkAppearance ? 0 : light, light);
                controller.setSystemBarsBehavior(android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                if (split) controller.show(WindowInsets.Type.systemBars());
                else controller.hide(WindowInsets.Type.systemBars());
            }
        }
        decor.requestApplyInsets();
    }

    @Override protected void onResume() {
        super.onResume();
        getWindow().getDecorView().post(this::applyWindowAppearance);
    }

    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) getWindow().getDecorView().post(this::applyWindowAppearance);
    }

    @Override public void onMultiWindowModeChanged(boolean inMultiWindowMode, Configuration configuration) {
        super.onMultiWindowModeChanged(inMultiWindowMode, configuration);
        applyWindowAppearance();
        getWindow().getDecorView().post(this::applyWindowAppearance);
    }

    @Override public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        getWindow().getDecorView().post(this::applyWindowAppearance);
    }

    private WebResourceResponse intercept(Uri uri) {
        if ("blob".equals(uri.getScheme()) || "data".equals(uri.getScheme())) return null;
        if (!"https".equals(uri.getScheme()) || !"folio.invalid".equals(uri.getHost())) return response(403, "Blocked", "text/plain", new ByteArrayInputStream(new byte[0]));
        String path = uri.getPath();
        if (path == null || path.indexOf('\0') >= 0 || path.contains("\\") || path.contains("..")) return missing();
        try {
            if (path.startsWith("/documents/")) {
                String[] parts = path.split("/");
                File file = parts.length > 2 ? documents.get(parts[2]) : null;
                if (file == null || !file.isFile()) return missing();
                return response(200, "OK", "application/octet-stream", new FileInputStream(file));
            }
            String asset = path.equals("/") ? "index.html" : path.substring(1);
            String type = asset.endsWith(".wasm") ? "application/wasm" : asset.endsWith(".js") ? "text/javascript" : asset.endsWith(".css") ? "text/css" : asset.endsWith(".json") ? "application/json" : asset.endsWith(".ttf") ? "font/ttf" : Storage.mime(asset);
            return response(200, "OK", type, getAssets().open(asset));
        } catch (Exception e) { return missing(); }
    }

    private WebResourceResponse missing() { return response(404, "Not found", "text/plain", new ByteArrayInputStream(new byte[0])); }

    private WebResourceResponse response(int code, String reason, String mime, InputStream bytes) {
        Map<String,String> headers = new HashMap<>();
        headers.put("X-Content-Type-Options", "nosniff");
        headers.put("Cache-Control", "no-store");
        headers.put("Content-Security-Policy", "default-src 'self' blob: data:; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self' blob: data:; object-src 'none'; base-uri 'self'");
        return new WebResourceResponse(mime, mime.startsWith("text/") || mime.equals("application/json") ? "UTF-8" : null, code, reason, headers, bytes);
    }

    private JSONObject event(String type) { JSONObject obj = new JSONObject(); try { obj.put("type", type); } catch (Exception ignored) {} return obj; }
    private void emit(JSONObject obj) { runOnUiThread(() -> { if (web != null) web.evaluateJavascript("window.FolioNative&&window.FolioNative.onEvent(" + obj + ")", null); }); }
    private void error(String message) { JSONObject e = event("error"); try { e.put("message", message); } catch (Exception ignored) {} emit(e); }

    private void openPicker() {
        if (pickerShowing) return;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        try { pickerShowing = true; startActivityForResult(intent, OPEN); }
        catch (Exception e) { pickerShowing = false; error("No hay un selector de documentos disponible."); }
    }

    private void stage(Uri uri, boolean persist) {
        if (uri == null || !"content".equals(uri.getScheme())) { error("Elige un documento con el selector de archivos de Android."); return; }
        io.execute(() -> {
            File target = null;
            try {
                if (persist) {
                    try { getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION); }
                    catch (SecurityException ignored) { /* Some share and cloud providers issue temporary access only. */ }
                }
                String name = "Documento";
                try (Cursor cursor = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) {
                        int col = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                        if (col >= 0) name = Storage.safeName(cursor.getString(col));
                        int size = cursor.getColumnIndex(OpenableColumns.SIZE);
                        if (size >= 0 && !cursor.isNull(size) && cursor.getLong(size) > Storage.MAX_BYTES) throw new java.io.IOException("Este archivo supera el límite de 100 MB.");
                    }
                }
                String id = UUID.randomUUID().toString();
                target = new File(getCacheDir(), "import-" + id);
                try (InputStream input = getContentResolver().openInputStream(uri); FileOutputStream output = new FileOutputStream(target)) {
                    if (input == null) throw new java.io.IOException("No se pudo leer este documento.");
                    Storage.copy(input, output, Storage.MAX_BYTES);
                }
                documents.put(id, target);
                JSONObject e = event("opened");
                e.put("name", name).put("size", target.length()).put("uri", uri.toString()).put("url", ORIGIN + "/documents/" + id).put("time", System.currentTimeMillis());
                emit(e);
            } catch (Exception e) { if (target != null) target.delete(); error(e.getMessage() == null ? "No se pudo leer este documento." : e.getMessage()); }
        });
    }

    private void sendRecoveries() { JSONObject e = event("recoveries"); try { e.put("items", Storage.recoveries(this)); } catch (Exception ignored) {} emit(e); }

    private void queueSave(String id) { saveQueue.add(id); launchNextSave(); }
    private void launchNextSave() {
        if (activeSave != null || pickerShowing || saveQueue.isEmpty()) return;
        activeSave = saveQueue.remove();
        SaveJob job = jobs.get(activeSave);
        if (job == null) { activeSave = null; launchNextSave(); return; }
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(Storage.mime(job.name)).putExtra(Intent.EXTRA_TITLE, job.name);
        try { pickerShowing = true; startActivityForResult(intent, SAVE); }
        catch (Exception e) { pickerShowing = false; completeSave(job, false, "No hay un selector de archivos disponible. La copia guardada está a salvo en Lucy."); }
    }

    private void completeSave(SaveJob job, boolean saved, String message) {
        JSONObject e = event("saveResult");
        try { e.put("id", job.id).put("saved", saved).put("recovery", true).put("name", job.name).put("message", message); } catch (Exception ignored) {}
        emit(e);
        jobs.remove(job.id);
        activeSave = null;
        sendRecoveries();
        launchNextSave();
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        pickerShowing = false;
        if (request == OPEN && result == RESULT_OK && data != null) {
            ClipData selected = data.getClipData();
            if (selected != null) {
                for (int i = 0; i < selected.getItemCount(); i++) stage(selected.getItemAt(i).getUri(), true);
            } else stage(data.getData(), true);
        }
        else if (request == CHOOSE && chooser != null) {
            // Some WebView providers parse only Intent.data and discard ClipData.
            // Font pickers use ClipData for a batch: forward every selected file.
            Uri[] uris = result == RESULT_OK ? selectedUris(data) : null;
            chooser.onReceiveValue(uris); chooser = null;
        } else if (request == SAVE && activeSave != null) {
            SaveJob job = jobs.get(activeSave);
            if (job != null) {
                if (result != RESULT_OK || data == null || data.getData() == null) completeSave(job, false, "Exportación cancelada. La copia está disponible en Copias guardadas.");
                else {
                    Uri uri = data.getData();
                    io.execute(() -> {
                        try (InputStream input = new FileInputStream(job.file); OutputStream output = getContentResolver().openOutputStream(uri, "wt")) {
                            if (output == null) throw new java.io.IOException("El proveedor seleccionado no pudo escribir el archivo.");
                            Storage.copy(input, output, Storage.MAX_BYTES);
                            output.flush();
                        } catch (Exception e) {
                            runOnUiThread(() -> completeSave(job, false, "La exportación falló. La copia está a salvo en Lucy. " + e.getMessage()));
                            return;
                        }
                        runOnUiThread(() -> completeSave(job, true, "Guardado: " + job.name));
                    });
                }
            }
        }
        launchNextSave();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        // Open incoming documents in this workspace without replacing an existing tab.
        pendingIntent = intent;
        if (ready) consumeIntent();
    }

    private static Uri[] selectedUris(Intent data) {
        if (data == null) return null;
        LinkedHashSet<Uri> uris = new LinkedHashSet<>();
        if (data.getData() != null) uris.add(data.getData());
        ClipData clips = data.getClipData();
        if (clips != null) for (int i = 0; i < clips.getItemCount(); i++) {
            Uri uri = clips.getItemAt(i).getUri();
            if (uri != null) uris.add(uri);
        }
        return uris.isEmpty() ? null : uris.toArray(new Uri[0]);
    }

    private void consumeIntent() {
        if (pendingIntent == null) return;
        Intent intent = pendingIntent;
        pendingIntent = null;
        if (Intent.ACTION_VIEW.equals(intent.getAction())) stage(intent.getData(), false);
        else if (Intent.ACTION_SEND.equals(intent.getAction())) {
            Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            stage(uri, false);
        }
    }

    @Override public void onBackPressed() {
        if (ready) web.evaluateJavascript("window.FolioNative&&window.FolioNative.back()", null);
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        ready = false;
        if (chooser != null) chooser.onReceiveValue(null);
        for (SaveJob job : jobs.values()) if (!job.complete) { try { if (job.output != null) job.output.close(); } catch (Exception ignored) {} if (job.file != null) job.file.delete(); }
        io.shutdown();
        if (web != null) { web.removeJavascriptInterface("AndroidFolio"); web.destroy(); web = null; }
        super.onDestroy();
    }

    private final class Bridge {
        @JavascriptInterface public void post(String json) {
            if (json == null || json.length() > 16384) return;
            try {
                JSONObject m = new JSONObject(json);
                runOnUiThread(() -> {
                    String op = m.optString("type");
                    if (op.equals("ready")) { ready = true; sendRecoveries(); consumeIntent(); }
                    else if (op.equals("appearance")) {
                        darkAppearance = m.optBoolean("dark", false);
                        Storage.prefs(MainActivity.this).edit().putBoolean("darkAppearanceV2", darkAppearance).apply();
                        applyWindowAppearance();
                    }
                    else if (op.equals("open")) openPicker();
                    else if (op.equals("exit")) finish();
                    else if (op.equals("recoveries")) sendRecoveries();
                    else if (op.equals("releaseDocument")) {
                        Uri url = Uri.parse(m.optString("url"));
                        String path = url.getPath();
                        if ("https".equals(url.getScheme()) && "folio.invalid".equals(url.getHost()) && path != null && path.matches("/documents/[a-f0-9-]+")) {
                            File file = documents.remove(path.substring("/documents/".length()));
                            // Recovery snapshots belong to the user; release only their mapping.
                            if (file != null && getCacheDir().equals(file.getParentFile()) && file.getName().startsWith("import-")) io.execute(() -> file.delete());
                        }
                    }
                    else if (op.equals("openRecovery")) {
                        String id = m.optString("id");
                        JSONObject item = Storage.find(MainActivity.this, id);
                        File file = Storage.recoveryFile(MainActivity.this, id);
                        if (item == null || file == null || !file.isFile()) { error("Esta copia guardada no está disponible."); return; }
                        String token = UUID.randomUUID().toString();
                        documents.put(token, file);
                        JSONObject e = event("opened");
                        try { e.put("name", item.optString("name")).put("size", file.length()).put("url", ORIGIN + "/documents/" + token).put("recoveryId", id).put("time", System.currentTimeMillis()); } catch (Exception ignored) {}
                        emit(e);
                    } else if (op.equals("deleteRecovery")) {
                        String id = m.optString("id");
                        new AlertDialog.Builder(MainActivity.this).setTitle("¿Eliminar la copia guardada?").setMessage("Se eliminará únicamente la copia privada que conserva Lucy.")
                            .setPositiveButton("Eliminar", (d, w) -> { if (!Storage.deleteRecovery(MainActivity.this, id)) error("No se pudo eliminar esta copia."); sendRecoveries(); }).setNegativeButton("Cancelar", null).show();
                    } else if (op.equals("share")) {
                        String id = m.optString("id");
                        JSONObject item = Storage.find(MainActivity.this, id);
                        if (item == null) { error("Guarda una copia antes de compartir."); return; }
                        Uri uri = Uri.parse("content://io.github.pedroguille.folio.recovery/" + id);
                        Intent send = new Intent(Intent.ACTION_SEND).setType(Storage.mime(item.optString("name"))).putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        send.setClipData(ClipData.newUri(getContentResolver(), item.optString("name"), uri));
                        try { startActivity(Intent.createChooser(send, "Compartir documento")); } catch (Exception e) { error("No hay aplicaciones disponibles para compartir."); }
                    } else if (op.equals("keyboard")) {
                        web.requestFocus();
                        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(web, InputMethodManager.SHOW_IMPLICIT);
                    }
                });
            } catch (Exception e) { error("Solicitud de la aplicación no válida."); }
        }

        @JavascriptInterface public String beginSave(String metadata) {
            try {
                if (metadata == null || metadata.length() > 4096 || jobs.size() >= 2) throw new java.io.IOException("Hay otra exportación en curso.");
                JSONObject m = new JSONObject(metadata);
                long size = m.optLong("size", -1);
                if (size < 1 || size > Storage.MAX_BYTES) throw new java.io.IOException("La exportación debe ocupar entre 1 byte y 100 MB.");
                File dir = Storage.directory(MainActivity.this);
                if (dir == null || dir.getUsableSpace() < size + 8L * 1024 * 1024) throw new java.io.IOException("Libera espacio de almacenamiento antes de exportar.");
                SaveJob job = new SaveJob();
                job.id = UUID.randomUUID().toString(); job.name = Storage.safeName(m.optString("name")); job.size = size;
                job.file = new File(dir, job.id + ".part"); job.output = new FileOutputStream(job.file);
                jobs.put(job.id, job);
                return new JSONObject().put("id", job.id).toString();
            } catch (Exception e) { return "{\"error\":" + JSONObject.quote(e.getMessage() == null ? "No se pudo iniciar la exportación." : e.getMessage()) + "}"; }
        }

        @JavascriptInterface public boolean appendSave(String id, String base64) {
            SaveJob job = jobs.get(id);
            if (job == null || job.complete || base64 == null || base64.length() > 90000) return false;
            synchronized (job) {
                try {
                    byte[] bytes = Base64.decode(base64, Base64.NO_WRAP);
                    if (job.written + bytes.length > job.size) return false;
                    job.output.write(bytes); job.written += bytes.length; return true;
                } catch (Exception e) { return false; }
            }
        }

        @JavascriptInterface public boolean finishSave(String id) {
            SaveJob job = jobs.get(id);
            if (job == null || job.complete) return false;
            synchronized (job) {
                try {
                    if (job.written != job.size) throw new java.io.IOException("Exportación incompleta.");
                    job.output.flush(); job.output.getFD().sync(); job.output.close();
                    File finalFile = Storage.recoveryFile(MainActivity.this, id);
                    if (finalFile == null || !job.file.renameTo(finalFile)) throw new java.io.IOException("No se pudo finalizar la copia guardada.");
                    job.file = finalFile;
                    JSONObject item = new JSONObject().put("id", id).put("name", job.name).put("size", job.size).put("time", System.currentTimeMillis());
                    Storage.addRecovery(MainActivity.this, item);
                    job.complete = true;
                    runOnUiThread(() -> queueSave(id));
                    return true;
                } catch (Exception e) { abortSave(id); error("La exportación falló: " + e.getMessage()); return false; }
            }
        }

        @JavascriptInterface public void abortSave(String id) {
            SaveJob job = jobs.get(id);
            if (job == null || job.complete) return;
            jobs.remove(id);
            try { job.output.close(); } catch (Exception ignored) {}
            job.file.delete();
        }

        @JavascriptInterface public String readClipboard() {
            try {
                ClipboardManager cm = (ClipboardManager)getSystemService(CLIPBOARD_SERVICE);
                ClipData data = cm.getPrimaryClip();
                if (data == null || data.getItemCount() == 0) return "";
                CharSequence text = data.getItemAt(0).coerceToText(MainActivity.this);
                return text == null ? "" : text.toString();
            } catch (Exception e) { return ""; }
        }
        @JavascriptInterface public void writeClipboard(String text) {
            if (text != null && text.length() <= 2 * 1024 * 1024) runOnUiThread(() -> ((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText(getString(R.string.app_name), text)));
        }
    }
}
