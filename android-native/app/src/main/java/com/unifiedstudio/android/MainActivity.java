package com.unifiedstudio.android;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.DownloadListener;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends Activity {
    private static final String BASE_URL = "http://127.0.0.1:8765/";
    private static final int FILE_CHOOSER = 7001;

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        setContentView(webView);
        configureWebView();

        try {
            copyAssetTree("frontend", new File(getFilesDir(), "frontend"));
            File pythonBytecode = new File(getFilesDir(), "python_bytecode");
            copyAssetTree("python_bytecode", pythonBytecode);

            File outputs = new File(getFilesDir(), "outputs");
            if (!outputs.exists()) outputs.mkdirs();

            File db = new File(getFilesDir(), "data/unified.db");
            File parent = db.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();

            Python py = Python.getInstance();
            PyObject bridge = py.getModule("android_server");
            bridge.callAttr(
                    "start_server",
                    new File(getFilesDir(), "frontend").getAbsolutePath(),
                    outputs.getAbsolutePath(),
                    db.getAbsolutePath(),
                    pythonBytecode.getAbsolutePath()
            );

            waitForServer();
        } catch (Exception e) {
            Toast.makeText(this, "Unified Studio startup failed: " + e.getMessage(), Toast.LENGTH_LONG).show();
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

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String scheme = uri.getScheme();
                if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {
                    if (uri.toString().startsWith(BASE_URL)) {
                        return false;
                    }
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, uri));
                    } catch (Exception ignored) {}
                    return true;
                }
                return false;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                    WebView view,
                    ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try {
                    startActivityForResult(params.createIntent(), FILE_CHOOSER);
                } catch (Exception e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });

        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                startActivity(intent);
            } catch (Exception ignored) {}
        });
    }

    private void waitForServer() {
        new Thread(() -> {
            final int maxAttempts = 60;
            for (int attempt = 0; attempt < maxAttempts; attempt++) {
                HttpURLConnection connection = null;
                try {
                    URL healthUrl = new URL(BASE_URL + "api/status");
                    connection = (HttpURLConnection) healthUrl.openConnection();
                    connection.setRequestMethod("GET");
                    connection.setConnectTimeout(1200);
                    connection.setReadTimeout(1200);
                    int status = connection.getResponseCode();
                    if (status == HttpURLConnection.HTTP_OK) {
                        runOnUiThread(() -> {
                            if (webView != null && !isFinishing()) {
                                webView.loadUrl(BASE_URL);
                            }
                        });
                        return;
                    }
                } catch (Exception ignored) {
                } finally {
                    if (connection != null) connection.disconnect();
                }

                try {
                    Thread.sleep(500);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }

            runOnUiThread(() -> Toast.makeText(
                    MainActivity.this,
                    "Unified Studio server did not become ready. Check the bundled Python runtime.",
                    Toast.LENGTH_LONG
            ).show());
        }, "UnifiedStudioHealthCheck").start();
    }

    private void copyAssetTree(String assetPath, File destination) throws IOException {
        String[] children = getAssets().list(assetPath);
        if (children == null || children.length == 0) {
            copyAssetFile(assetPath, destination);
            return;
        }
        if (!destination.exists() && !destination.mkdirs()) {
            throw new IOException("Cannot create " + destination);
        }
        for (String child : children) {
            copyAssetTree(assetPath + "/" + child, new File(destination, child));
        }
    }

    private void copyAssetFile(String assetPath, File destination) throws IOException {
        File parent = destination.getParentFile();
        if (parent != null && !parent.exists()) parent.mkdirs();

        try (InputStream in = getAssets().open(assetPath);
             FileOutputStream out = new FileOutputStream(destination)) {
            byte[] buffer = new byte[8192];
            int n;
            while ((n = in.read(buffer)) != -1) {
                out.write(buffer, 0, n);
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER) {
            if (fileCallback != null) {
                Uri[] results = null;
                if (resultCode == RESULT_OK && data != null) {
                    if (data.getClipData() != null) {
                        int count = data.getClipData().getItemCount();
                        results = new Uri[count];
                        for (int i = 0; i < count; i++) {
                            results[i] = data.getClipData().getItemAt(i).getUri();
                        }
                    } else if (data.getData() != null) {
                        results = new Uri[]{data.getData()};
                    }
                }
                fileCallback.onReceiveValue(results);
                fileCallback = null;
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
