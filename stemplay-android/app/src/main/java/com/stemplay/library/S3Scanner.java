package com.stemplay.library;

import android.os.Handler;
import android.os.Looper;

import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserFactory;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class S3Scanner {

    private static final String S3_HOST = "https://stemplay-videos.s3.us-east-2.amazonaws.com";
    private static final String[] PDF_KEYWORDS = {"pdf", "course", "material", "content",
            "lesson", "class", "aula", "ebook", "book", "modul"};
    private static final String[] SKIP_PREFIXES = {"Annotations/", "Activities/"};

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final AtomicBoolean scanning = new AtomicBoolean(false);

    public interface ScanCallback {
        void onProgress(String message);
        void onComplete(List<String> pdfUrls);
        void onError(String error);
    }

    public boolean isScanning() { return scanning.get(); }

    public void scan(ScanCallback callback) {
        if (scanning.getAndSet(true)) return;
        executor.execute(() -> {
            try {
                List<String> result = doScan(callback);
                scanning.set(false);
                mainHandler.post(() -> callback.onComplete(result));
            } catch (Exception e) {
                scanning.set(false);
                mainHandler.post(() -> callback.onError(e.getMessage() != null ? e.getMessage() : "Erro desconhecido"));
            }
        });
    }

    private List<String> doScan(ScanCallback callback) throws Exception {
        mainHandler.post(() -> callback.onProgress("Mapeando bucket S3..."));

        List<String> rootDirs = listDirectories("");
        mainHandler.post(() -> callback.onProgress("Pastas raiz: " + rootDirs.size()));

        List<String> targetDirs = new ArrayList<>();
        for (String d : rootDirs) {
            String lower = d.toLowerCase().replaceAll("/$", "");
            boolean matches = false;
            for (String kw : PDF_KEYWORDS) {
                if (lower.contains(kw)) { matches = true; break; }
            }
            if (matches) targetDirs.add(d);
        }

        if (targetDirs.isEmpty()) {
            for (String d : rootDirs) {
                boolean skip = false;
                for (String prefix : SKIP_PREFIXES) {
                    if (d.startsWith(prefix)) { skip = true; break; }
                }
                if (!skip) targetDirs.add(d);
            }
        }

        final int totalDirs = targetDirs.size();
        mainHandler.post(() -> callback.onProgress("Varrendo " + totalDirs + " pastas..."));

        List<String> allPdfs = new ArrayList<>();
        for (int i = 0; i < targetDirs.size(); i++) {
            String dir = targetDirs.get(i);
            final int idx = i + 1;
            final int count = allPdfs.size();
            mainHandler.post(() -> callback.onProgress(idx + "/" + totalDirs + " - " + dir.replace("/", "") + " (" + count + " PDFs)"));

            List<String> pdfs = findAllPdfs(dir);
            allPdfs.addAll(pdfs);

            Thread.sleep(100);
        }

        return allPdfs;
    }

    private List<String> listDirectories(String prefix) throws Exception {
        StringBuilder sb = new StringBuilder(S3_HOST);
        sb.append("/?list-type=2&delimiter=/&max-keys=1000");
        if (!prefix.isEmpty()) {
            sb.append("&prefix=").append(URLEncoder.encode(prefix, "UTF-8"));
        }
        String xml = fetchXml(sb.toString());
        return parseCommonPrefixes(xml);
    }

    private List<String> findAllPdfs(String prefix) throws Exception {
        List<String> pdfs = new ArrayList<>();
        String continuationToken = null;

        while (true) {
            StringBuilder sb = new StringBuilder(S3_HOST);
            sb.append("/?list-type=2&prefix=").append(URLEncoder.encode(prefix, "UTF-8"));
            sb.append("&max-keys=1000");
            if (continuationToken != null) {
                sb.append("&continuation-token=").append(URLEncoder.encode(continuationToken, "UTF-8"));
            }

            String xml = fetchXml(sb.toString());
            pdfs.addAll(parsePdfKeys(xml));

            String[] next = parseContinuation(xml);
            if ("true".equals(next[0]) && next[1] != null && !next[1].isEmpty()) {
                continuationToken = next[1];
            } else {
                break;
            }
        }

        return pdfs;
    }

    private String fetchXml(String urlStr) throws Exception {
        URL url = new URL(urlStr);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        conn.setRequestProperty("User-Agent",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0");
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(30000);
        conn.setInstanceFollowRedirects(true);

        int code = conn.getResponseCode();
        InputStream is;
        if (code >= 400) {
            is = conn.getErrorStream();
        } else {
            is = conn.getInputStream();
        }

        if (is == null) throw new Exception("S3 HTTP " + code + ": resposta vazia");

        StringBuilder sb = new StringBuilder();
        byte[] buf = new byte[8192];
        int n;
        while ((n = is.read(buf)) != -1) {
            sb.append(new String(buf, 0, n, "UTF-8"));
        }
        is.close();
        conn.disconnect();

        if (code != 200) {
            String body = sb.length() > 300 ? sb.substring(0, 300) : sb.toString();
            throw new Exception("S3 HTTP " + code + ": " + body);
        }
        return sb.toString();
    }

    private List<String> parseCommonPrefixes(String xml) throws Exception {
        List<String> dirs = new ArrayList<>();
        XmlPullParserFactory factory = XmlPullParserFactory.newInstance();
        factory.setNamespaceAware(true);
        XmlPullParser parser = factory.newPullParser();
        parser.setInput(new InputStreamReader(new java.io.ByteArrayInputStream(xml.getBytes("UTF-8"))));

        boolean inPrefix = false;
        int event = parser.getEventType();
        while (event != XmlPullParser.END_DOCUMENT) {
            if (event == XmlPullParser.START_TAG && "Prefix".equals(parser.getName())) {
                inPrefix = true;
            } else if (event == XmlPullParser.TEXT && inPrefix) {
                String text = parser.getText();
                if (text != null && !text.trim().isEmpty()) {
                    dirs.add(text.trim());
                }
                inPrefix = false;
            } else if (event == XmlPullParser.END_TAG) {
                inPrefix = false;
            }
            event = parser.next();
        }
        return dirs;
    }

    private List<String> parsePdfKeys(String xml) throws Exception {
        List<String> keys = new ArrayList<>();
        XmlPullParserFactory factory = XmlPullParserFactory.newInstance();
        factory.setNamespaceAware(true);
        XmlPullParser parser = factory.newPullParser();
        parser.setInput(new InputStreamReader(new java.io.ByteArrayInputStream(xml.getBytes("UTF-8"))));

        boolean inKey = false;
        String currentKey = null;
        int event = parser.getEventType();
        while (event != XmlPullParser.END_DOCUMENT) {
            if (event == XmlPullParser.START_TAG && "Key".equals(parser.getName())) {
                inKey = true;
                currentKey = null;
            } else if (event == XmlPullParser.TEXT && inKey) {
                currentKey = parser.getText();
                inKey = false;
            } else if (event == XmlPullParser.END_TAG) {
                if ("Key".equals(parser.getName())) {
                    inKey = false;
                } else if ("Contents".equals(parser.getName()) && currentKey != null) {
                    // '+' em chave S3 vem literal; protege antes do decode
                    String decoded = java.net.URLDecoder.decode(
                            currentKey.replace("+", "%2B"), "UTF-8");
                    if (decoded.toLowerCase().endsWith(".pdf")) {
                        keys.add(S3_HOST + "/" + decoded);
                    }
                    currentKey = null;
                }
            }
            event = parser.next();
        }
        return keys;
    }

    private String[] parseContinuation(String xml) throws Exception {
        String isTruncated = "false";
        String nextToken = null;

        XmlPullParserFactory factory = XmlPullParserFactory.newInstance();
        factory.setNamespaceAware(true);
        XmlPullParser parser = factory.newPullParser();
        parser.setInput(new InputStreamReader(new java.io.ByteArrayInputStream(xml.getBytes("UTF-8"))));

        boolean inTag = false;
        String tagName = "";
        int event = parser.getEventType();
        while (event != XmlPullParser.END_DOCUMENT) {
            if (event == XmlPullParser.START_TAG) {
                inTag = true;
                tagName = parser.getName();
            } else if (event == XmlPullParser.TEXT && inTag) {
                String text = parser.getText();
                if (text != null && !text.trim().isEmpty()) {
                    if ("IsTruncated".equals(tagName)) isTruncated = text.trim().toLowerCase();
                    if ("NextContinuationToken".equals(tagName)) nextToken = text.trim();
                }
                inTag = false;
            } else if (event == XmlPullParser.END_TAG) {
                inTag = false;
            }
            event = parser.next();
        }
        return new String[]{isTruncated, nextToken};
    }

    public void shutdown() {
        executor.shutdownNow();
    }
}
