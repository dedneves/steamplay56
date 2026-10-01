package com.stemplay.library;

import android.os.Handler;
import android.os.Looper;

import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserFactory;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class S3Scanner {

    private static final String S3_HOST = "https://stemplay-videos.s3.us-east-2.amazonaws.com";
    private static final String[] PDF_KEYWORDS = {"pdf", "course", "material", "content",
            "lesson", "class", "aula", "ebook", "book", "modul"};
    private static final String[] SKIP_PREFIXES = {"Annotations/", "Activities/"};
    private static final long FULL_REFRESH_MS = 24 * 3600_000L;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final AtomicBoolean scanning = new AtomicBoolean(false);
    private final File cacheFile;   // linhas: dir\turl
    private final File doneFile;    // 1a linha: #ts=<epoch>; depois: uma dir por linha

    public interface ScanCallback {
        void onProgress(String message);
        void onComplete(List<String> pdfUrls);
        void onError(String error);
    }

    public S3Scanner() { this(null); }

    public S3Scanner(File dir) {
        if (dir != null) {
            cacheFile = new File(dir, "s3_pdf_urls.txt");
            doneFile = new File(dir, "s3_dirs_done.txt");
        } else {
            cacheFile = null;
            doneFile = null;
        }
    }

    public boolean isScanning() { return scanning.get(); }

    /**
     * Varredura com cache incremental:
     * 1) se ja existe lista salva, entrega NA HORA (servidor disponivel em segundos);
     * 2) em paralelo, varre apenas as pastas ainda nao concluidas;
     * 3) a cada 24h (ou se a lista estava vazia) refaz tudo.
     * onComplete pode ser chamado duas vezes: cache imediato e resultado final.
     */
    public void scan(ScanCallback callback) {
        if (scanning.getAndSet(true)) return;
        executor.execute(() -> {
            LinkedHashSet<String> all = new LinkedHashSet<>();
            try {
                List<String> cached = loadCachedUrls();
                if (!cached.isEmpty()) {
                    all.addAll(cached);
                    final List<String> snapshot = new ArrayList<>(all);
                    mainHandler.post(() -> callback.onComplete(snapshot));
                    mainHandler.post(() -> callback.onProgress(
                            "Cache: " + snapshot.size() + " PDFs. Procurando novidades..."));
                }

                mainHandler.post(() -> callback.onProgress("Mapeando bucket S3..."));
                List<String> rootDirs = listDirectories("");
                long age = cacheAgeMs();
                boolean forceFull = cached.isEmpty() || age > FULL_REFRESH_MS;
                if (forceFull) {
                    markDoneClear();
                    truncateUrlCache();
                }

                List<String> targets = filterTargetDirs(rootDirs);
                Set<String> done = loadDoneDirs();
                List<String> pend = new ArrayList<>();
                for (String d : targets) {
                    if (!done.contains(d)) pend.add(d);
                }

                if (pend.isEmpty()) {
                    final List<String> snapshot = new ArrayList<>(all);
                    mainHandler.post(() -> callback.onProgress("Em dia (" + snapshot.size() + " PDFs)"));
                    mainHandler.post(() -> callback.onComplete(snapshot));
                    scanning.set(false);
                    return;
                }

                for (int i = 0; i < pend.size(); i++) {
                    String dir = pend.get(i);
                    final int idx = i + 1, tot = pend.size(), cnt = all.size();
                    mainHandler.post(() -> callback.onProgress(
                            idx + "/" + tot + " - " + dir.replace("/", "") + " (" + cnt + " PDFs)"));

                    List<String> pdfs = findAllPdfs(dir);
                    for (String u : pdfs) all.add(u);
                    appendUrlCache(dir, pdfs);
                    markDone(dir);
                    Thread.sleep(100);
                }

                final List<String> result = new ArrayList<>(all);
                mainHandler.post(() -> callback.onComplete(result));
                scanning.set(false);
            } catch (Exception e) {
                scanning.set(false);
                final List<String> cachedOnly = new ArrayList<>(all);
                mainHandler.post(() -> {
                    if (!cachedOnly.isEmpty()) callback.onComplete(cachedOnly);
                    else callback.onError(e.getMessage() != null ? e.getMessage() : "Erro desconhecido");
                });
            }
        });
    }

    private List<String> filterTargetDirs(List<String> rootDirs) {
        List<String> out = new ArrayList<>();
        for (String d : rootDirs) {
            String lower = d.toLowerCase().replaceAll("/$", "");
            for (String kw : PDF_KEYWORDS) {
                if (lower.contains(kw)) { out.add(d); break; }
            }
        }
        if (out.isEmpty()) {
            for (String d : rootDirs) {
                boolean skip = false;
                for (String prefix : SKIP_PREFIXES) {
                    if (d.startsWith(prefix)) { skip = true; break; }
                }
                if (!skip) out.add(d);
            }
        }
        return out;
    }

    // ---------------- persistencia do cache ----------------

    private List<String> loadCachedUrls() {
        List<String> urls = new ArrayList<>();
        if (cacheFile == null || !cacheFile.exists()) return urls;
        try (BufferedReader br = new BufferedReader(new FileReader(cacheFile))) {
            String line;
            while ((line = br.readLine()) != null) {
                int t = line.indexOf('\t');
                String u = t >= 0 ? line.substring(t + 1) : line;
                if (!u.trim().isEmpty()) urls.add(u.trim());
            }
        } catch (Exception ignored) {}
        return urls;
    }

    private void appendUrlCache(String dir, List<String> urls) {
        if (cacheFile == null || urls.isEmpty()) return;
        try (BufferedWriter bw = new BufferedWriter(new FileWriter(cacheFile, true))) {
            for (String u : urls) {
                bw.write(dir);
                bw.write('\t');
                bw.write(u);
                bw.newLine();
            }
        } catch (Exception ignored) {}
    }

    private void truncateUrlCache() {
        if (cacheFile != null && cacheFile.exists()) cacheFile.delete();
    }

    private long cacheAgeMs() {
        if (doneFile == null || !doneFile.exists()) return Long.MAX_VALUE;
        try (BufferedReader br = new BufferedReader(new FileReader(doneFile))) {
            String first = br.readLine();
            if (first != null && first.startsWith("#ts=")) {
                return System.currentTimeMillis() - Long.parseLong(first.substring(4).trim());
            }
        } catch (Exception ignored) {}
        return Long.MAX_VALUE;
    }

    private Set<String> loadDoneDirs() {
        Set<String> set = new HashSet<>();
        if (doneFile == null || !doneFile.exists()) return set;
        try (BufferedReader br = new BufferedReader(new FileReader(doneFile))) {
            String line;
            while ((line = br.readLine()) != null) {
                if (line.startsWith("#")) continue;
                if (!line.trim().isEmpty()) set.add(line.trim());
            }
        } catch (Exception ignored) {}
        return set;
    }

    private void markDone(String dir) {
        if (doneFile == null) return;
        try (BufferedWriter bw = new BufferedWriter(new FileWriter(doneFile, true))) {
            if (!doneFile.exists() || doneFile.length() == 0) {
                bw.write("#ts=" + System.currentTimeMillis());
                bw.newLine();
            }
            bw.write(dir);
            bw.newLine();
        } catch (Exception ignored) {}
    }

    private void markDoneClear() {
        if (doneFile != null && doneFile.exists()) doneFile.delete();
    }

    // ---------------- varredura S3 propriamente dita ----------------

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
        InputStream is = (code >= 400) ? conn.getErrorStream() : conn.getInputStream();
        if (is == null) throw new Exception("S3 HTTP " + code + ": resposta vazia");

        StringBuilder sb = new StringBuilder();
        byte[] buf = new byte[8192];
        int n;
        while ((n = is.read(buf)) != -1) sb.append(new String(buf, 0, n, "UTF-8"));
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
                if (text != null && !text.trim().isEmpty()) dirs.add(text.trim());
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
                    if (decoded.toLowerCase().endsWith(".pdf")) keys.add(S3_HOST + "/" + decoded);
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
