package com.unifiedstudio.android;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.View;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.Toast;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final String BASE_URL = "http://127.0.0.1:8765/";
    private static final String SD_URL = "http://127.0.0.1:8766/";
    private static final int FILE_CHOOSER = 7001;
    private static final int MODEL_PICKER = 7002;

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private Process diffusionProcess;
    private volatile boolean sdServerReady = false;
    private volatile boolean sdWaitStarted = false;
    private LinearLayout sdControls;
    private File modelsDir;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        sdControls = new LinearLayout(this);
        sdControls.setOrientation(LinearLayout.HORIZONTAL);
        sdControls.setGravity(Gravity.CENTER_VERTICAL);
        sdControls.setPadding(12, 10, 12, 10);
        sdControls.setBackgroundColor(Color.argb(220, 12, 18, 25));
        sdControls.setVisibility(View.GONE);

        Button importModel = new Button(this);
        importModel.setText("استيراد موديل");
        importModel.setOnClickListener(v -> launchModelPicker());
        sdControls.addView(importModel, new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        Button backToStudio = new Button(this);
        backToStudio.setText("العودة للاستوديو");
        backToStudio.setOnClickListener(v -> { if (webView.canGoBack()) webView.goBack(); else webView.loadUrl(BASE_URL); });
        sdControls.addView(backToStudio, new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        FrameLayout.LayoutParams controlsParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.TOP);
        root.addView(sdControls, controlsParams);
        setContentView(root);

        configureWebView();
        try {
            File frontend = new File(getFilesDir(), "frontend");
            copyAssetTree("frontend", frontend);

            File guides = new File(getFilesDir(), "guides");
            copyAssetTree("guides", guides);

            File outputs = new File(getFilesDir(), "outputs");
            if (!outputs.exists() && !outputs.mkdirs())
                throw new IOException("Cannot create outputs directory");

            File db = new File(getFilesDir(), "data/unified.db");
            File parent = db.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs())
                throw new IOException("Cannot create database directory");

            modelsDir = new File(getFilesDir(), "models");
            if (!modelsDir.exists() && !modelsDir.mkdirs())
                throw new IOException("Cannot create models directory");

            startLocalDiffusionEngine();

            Python py = Python.getInstance();
            PyObject bridge = py.getModule("android_server");
            bridge.callAttr("start_server", frontend.getAbsolutePath(),
                    outputs.getAbsolutePath(), db.getAbsolutePath(), null);
            waitForUnifiedServer();
        } catch (Exception e) {
            Toast.makeText(this, "Unified Studio startup failed: " + e.getMessage(),
                    Toast.LENGTH_LONG).show();
        }
    }

    private void startLocalDiffusionEngine() {
        try {
            // Android 10+ blocks execve() from writable app-data files.
            // Package sd-server as libsd-server.so so PackageManager extracts it
            // into the read-only nativeLibraryDir, which is executable by app processes.
            File nativeDir = new File(getApplicationInfo().nativeLibraryDir);
            File executable = new File(nativeDir, "libsd-server.so");
            File runtime = new File(nativeDir, "libsdserver_cxx.so");
            if (!executable.isFile() || !executable.canExecute())
                throw new IOException("Bundled sd-server is missing or not executable in nativeLibraryDir");
            if (!runtime.isFile())
                throw new IOException("Bundled SD C++ runtime is missing from nativeLibraryDir");

            File logFile = new File(getFilesDir(), "sd-server.log");
            ProcessBuilder builder = new ProcessBuilder(
                    executable.getAbsolutePath(),
                    "--model-dir", modelsDir.getAbsolutePath(),
                    "--listen-ip", "127.0.0.1",
                    "--listen-port", "8766",
                    "-v");
            builder.directory(getFilesDir());
            builder.environment().put("LD_LIBRARY_PATH", nativeDir.getAbsolutePath());
            builder.environment().put("TMPDIR", getCacheDir().getAbsolutePath());
            builder.redirectErrorStream(true);
            builder.redirectOutput(logFile);
            diffusionProcess = builder.start();
            waitForLocalSdServer();
        } catch (Exception e) {
            Toast.makeText(this, "Stable Diffusion لم يبدأ: " + e.getMessage(),
                    Toast.LENGTH_LONG).show();
        }
    }

    private void waitForLocalSdServer() {
        if (sdWaitStarted) return;
        sdWaitStarted = true;
        new Thread(() -> {
            for (int attempt = 0; attempt < 120; attempt++) {
                if (diffusionProcess != null && !diffusionProcess.isAlive()) {
                    String log = readLogTail(new File(getFilesDir(), "sd-server.log"));
                    runOnUiThread(() -> Toast.makeText(MainActivity.this,
                            "محرك Stable Diffusion توقف عند التشغيل. " + log,
                            Toast.LENGTH_LONG).show());
                    return;
                }
                HttpURLConnection connection = null;
                try {
                    connection = (HttpURLConnection) new URL(SD_URL).openConnection();
                    connection.setConnectTimeout(700);
                    connection.setReadTimeout(700);
                    int code = connection.getResponseCode();
                    if (code >= 200 && code < 500) {
                        sdServerReady = true;
                        return;
                    }
                } catch (Exception ignored) {
                } finally {
                    if (connection != null) connection.disconnect();
                }
                try { Thread.sleep(500); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            }
        }, "StableDiffusionHealthCheck").start();
    }

    private String readLogTail(File file) {
        try {
            if (!file.exists()) return "لا يوجد سجل تشغيل.";
            byte[] bytes = new byte[(int) Math.min(file.length(), 900)];
            try (java.io.RandomAccessFile raf = new java.io.RandomAccessFile(file, "r")) {
                raf.seek(Math.max(0, file.length() - bytes.length));
                raf.readFully(bytes);
            }
            String value = new String(bytes, "UTF-8").replace('\n', ' ').trim();
            return value.length() > 240 ? value.substring(value.length() - 240) : value;
        } catch (Exception ignored) {
            return "تعذر قراءة سجل المحرك.";
        }
    }

    private void openLocalStableDiffusion() {
        if (diffusionProcess == null || !diffusionProcess.isAlive()) {
            Toast.makeText(this, "محرك Stable Diffusion متوقف. أعد فتح التطبيق.",
                    Toast.LENGTH_LONG).show();
            return;
        }
        if (sdServerReady) {
            webView.loadUrl(SD_URL);
            return;
        }
        Toast.makeText(this, "جاري تشغيل واجهة Stable Diffusion...", Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            for (int i = 0; i < 60; i++) {
                if (sdServerReady) {
                    runOnUiThread(() -> webView.loadUrl(SD_URL));
                    return;
                }
                try { Thread.sleep(500); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            }
            String log = readLogTail(new File(getFilesDir(), "sd-server.log"));
            runOnUiThread(() -> Toast.makeText(MainActivity.this,
                    "واجهة Stable Diffusion لم تبدأ. " + log, Toast.LENGTH_LONG).show());
        }, "OpenStableDiffusion").start();
    }

    private void launchModelPicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_TITLE, "اختيار ملف موديل Stable Diffusion");
        try {
            startActivityForResult(intent, MODEL_PICKER);
        } catch (Exception e) {
            Toast.makeText(this, "تعذر فتح مدير الملفات: " + e.getMessage(),
                    Toast.LENGTH_LONG).show();
        }
    }

    private String getDisplayName(Uri uri) {
        String name = null;
        try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (column >= 0) name = cursor.getString(column);
            }
        } catch (Exception ignored) {
        }
        if (name == null || name.trim().isEmpty()) name = "stable-diffusion-model.safetensors";
        return name;
    }

    private void importModel(Uri uri) {
        final String originalName = getDisplayName(uri);
        final String lower = originalName.toLowerCase(Locale.ROOT);
        if (!(lower.endsWith(".safetensors") || lower.endsWith(".ckpt") ||
                lower.endsWith(".gguf") || lower.endsWith(".pt") ||
                lower.endsWith(".bin") || lower.endsWith(".pth") ||
                lower.endsWith(".sft"))) {
            Toast.makeText(this,
                    "اختر ملف موديل مدعومًا: safetensors أو ckpt أو gguf",
                    Toast.LENGTH_LONG).show();
            return;
        }

        Toast.makeText(this, "جاري نسخ ملف الموديل إلى مساحة التطبيق...",
                Toast.LENGTH_LONG).show();
        new Thread(() -> {
            String safeName = originalName.replaceAll("[^A-Za-z0-9._-]", "_");
            File category = lower.endsWith(".gguf")
                    ? new File(modelsDir, "diffusion_models")
                    : new File(modelsDir, "checkpoints");
            if (!category.exists() && !category.mkdirs()) {
                runOnUiThread(() -> Toast.makeText(this, "تعذر إنشاء مجلد الموديلات.",
                        Toast.LENGTH_LONG).show());
                return;
            }
            File destination = new File(category, safeName);
            try (InputStream in = getContentResolver().openInputStream(uri);
                 FileOutputStream out = new FileOutputStream(destination)) {
                if (in == null) throw new IOException("تعذر فتح الملف المختار");
                byte[] buffer = new byte[1024 * 1024];
                int count;
                while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
                out.getFD().sync();
                runOnUiThread(() -> {
                    Toast.makeText(this, "تم استيراد الموديل. افتح Models ثم حدّث قائمة الملفات واضغط Load models.",
                            Toast.LENGTH_LONG).show();
                    if (webView != null && webView.getUrl() != null &&
                            webView.getUrl().startsWith(SD_URL)) webView.reload();
                });
            } catch (Exception e) {
                if (destination.exists()) destination.delete();
                runOnUiThread(() -> Toast.makeText(this,
                        "فشل استيراد الموديل: " + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }, "StableDiffusionModelImport").start();
    }

    private class AndroidBridge {
        @JavascriptInterface
        public void openLocalStableDiffusion() {
            runOnUiThread(() -> openLocalStableDiffusion());
        }

        @JavascriptInterface
        public void importStableDiffusionModel() {
            runOnUiThread(() -> launchModelPicker());
        }
    }

    private void configureWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        webView.addJavascriptInterface(new AndroidBridge(), "AndroidBridge");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String scheme = uri.getScheme();
                String url = uri.toString();
                if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {
                    if (url.startsWith(BASE_URL) || url.startsWith(SD_URL)) return false;
                    try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                    catch (Exception ignored) {}
                    return true;
                }
                return false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                if (sdControls != null)
                    sdControls.setVisibility(url != null && url.startsWith(SD_URL)
                            ? View.VISIBLE : View.GONE);
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try { startActivityForResult(params.createIntent(), FILE_CHOOSER); }
                catch (Exception e) { fileCallback = null; return false; }
                return true;
            }
        });
        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {
            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
            catch (Exception ignored) {}
        });
    }

    private void waitForUnifiedServer() {
        new Thread(() -> {
            for (int attempt = 0; attempt < 60; attempt++) {
                HttpURLConnection connection = null;
                try {
                    connection = (HttpURLConnection) new URL(BASE_URL + "health").openConnection();
                    connection.setRequestMethod("GET");
                    connection.setConnectTimeout(1200);
                    connection.setReadTimeout(1200);
                    if (connection.getResponseCode() == HttpURLConnection.HTTP_OK) {
                        runOnUiThread(() -> {
                            if (webView != null && !isFinishing()) webView.loadUrl(BASE_URL);
                        });
                        return;
                    }
                } catch (Exception ignored) {
                } finally {
                    if (connection != null) connection.disconnect();
                }
                try { Thread.sleep(500); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            }
            runOnUiThread(() -> Toast.makeText(MainActivity.this,
                    "Unified Studio server did not become ready. Check the bundled Python runtime.",
                    Toast.LENGTH_LONG).show());
        }, "UnifiedStudioHealthCheck").start();
    }

    private void copyAssetTree(String assetPath, File destination) throws IOException {
        String[] children = getAssets().list(assetPath);
        if (children == null || children.length == 0) {
            copyAssetFile(assetPath, destination);
            return;
        }
        if (!destination.exists() && !destination.mkdirs())
            throw new IOException("Cannot create " + destination);
        for (String child : children)
            copyAssetTree(assetPath + "/" + child, new File(destination, child));
    }

    private void copyAssetFile(String assetPath, File destination) throws IOException {
        File parent = destination.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs())
            throw new IOException("Cannot create " + parent);
        if (destination.exists() && !destination.canWrite()) destination.setWritable(true, true);
        try (InputStream in = getAssets().open(assetPath);
             FileOutputStream out = new FileOutputStream(destination)) {
            byte[] buffer = new byte[8192];
            int n;
            while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == MODEL_PICKER) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null)
                importModel(data.getData());
            return;
        }
        if (requestCode == FILE_CHOOSER && fileCallback != null) {
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    results = new Uri[count];
                    for (int i = 0; i < count; i++)
                        results[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) results = new Uri[]{data.getData()};
            }
            fileCallback.onReceiveValue(results);
            fileCallback = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (diffusionProcess != null && diffusionProcess.isAlive()) diffusionProcess.destroy();
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
