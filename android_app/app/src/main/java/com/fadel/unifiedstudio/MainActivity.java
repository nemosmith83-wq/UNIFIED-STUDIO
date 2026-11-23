package com.fadel.unifiedstudio;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebSettings;
import android.webkit.WebViewClient;
import android.webkit.JavascriptInterface;
import android.content.SharedPreferences;
import android.util.Base64;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.OutputStream;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private WebView web;
    private SharedPreferences prefs;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        prefs = getSharedPreferences("unified_studio", MODE_PRIVATE);
        web = new WebView(this);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(false);
        web.setWebViewClient(new WebViewClient());
        web.addJavascriptInterface(new Bridge(), "Android");
        setContentView(web);
        web.loadUrl("file:///android_asset/index.html");
    }

    public class Bridge {
        @JavascriptInterface public void saveKey(String key) {
            prefs.edit().putString("api_key", key == null ? "" : key.trim()).apply();
        }
        @JavascriptInterface public boolean hasKey() {
            return !prefs.getString("api_key", "").isEmpty();
        }
        @JavascriptInterface public void generate(String prompt, String callbackId) {
            worker.execute(() -> {
                String result;
                try {
                    String key = prefs.getString("api_key", "");
                    if (key.isEmpty()) throw new Exception("Add your AI API key in Settings first.");
                    URL url = new URL("https://api.openai.com/v1/chat/completions");
                    HttpURLConnection c = (HttpURLConnection) url.openConnection();
                    c.setRequestMethod("POST");
                    c.setConnectTimeout(20000);
                    c.setReadTimeout(90000);
                    c.setRequestProperty("Authorization", "Bearer " + key);
                    c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                    c.setDoOutput(true);
                    JSONObject body = new JSONObject();
                    body.put("model", "gpt-4o-mini");
                    body.put("messages", new org.json.JSONArray()
                        .put(new JSONObject().put("role","system").put("content","You are Unified Studio, a practical business content and IT support assistant. Produce useful, safe, clear results. For IT tickets, provide triage and suggested steps only; never claim you performed a repair."))
                        .put(new JSONObject().put("role","user").put("content",prompt)));
                    byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
                    try (OutputStream out = c.getOutputStream()) { out.write(bytes); }
                    int code = c.getResponseCode();
                    InputStream stream = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
                    ByteArrayOutputStream buffer = new ByteArrayOutputStream();
                    byte[] chunk = new byte[4096]; int n;
                    while ((n = stream.read(chunk)) != -1) buffer.write(chunk,0,n);
                    JSONObject response = new JSONObject(buffer.toString("UTF-8"));
                    if (code < 200 || code >= 300) {
                        JSONObject error = response.optJSONObject("error");
                        throw new Exception(error == null ? "AI request failed (HTTP " + code + ")" : error.optString("message","AI request failed"));
                    }
                    result = response.getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content");
                } catch (Exception e) { result = "ERROR: " + e.getMessage(); }
                final String output = result;
                runOnUiThread(() -> web.evaluateJavascript("window.onAIResult(" + JSONObject.quote(callbackId) + "," + JSONObject.quote(output) + ")", null));
            });
        }
    }

    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        worker.shutdownNow();
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
