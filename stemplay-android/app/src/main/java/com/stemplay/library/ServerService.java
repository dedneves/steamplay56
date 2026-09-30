package com.stemplay.library;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.content.res.AssetManager;
import android.net.wifi.WifiManager;
import android.os.Binder;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import androidx.core.app.NotificationCompat;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLDecoder;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

public class ServerService extends Service {

    private static final String CHANNEL_ID = "stemplay_server";
    private static final int NOTIFICATION_ID = 1;
    private static final String ALLOWED_PROXY_PREFIX =
        "https://stemplay-videos.s3.us-east-2.amazonaws.com/";

    private LibraryServer server;
    private final IBinder binder = new LocalBinder();
    private VisitorTracker visitorTracker;
    private final Set<String> blockedIPs = ConcurrentHashMap.newKeySet();
    private String localUrl = "";
    private int port = 8080;

    private S3Scanner s3Scanner;
    private volatile String cachedHtml = null;
    private volatile List<String> cachedPdfs = new ArrayList<>();
    private volatile boolean scanComplete = false;
    private String htmlTemplate = null;
    private OnScanListener scanListener;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public interface OnScanListener {
        void onScanProgress(String message);
        void onScanComplete(int pdfCount);
        void onScanError(String error);
    }

    public class LocalBinder extends Binder {
        ServerService getService() { return ServerService.this; }
    }

    @Override
    public IBinder onBind(Intent intent) { return binder; }

    @Override
    public void onCreate() {
        super.onCreate();
        visitorTracker = new VisitorTracker();
        s3Scanner = new S3Scanner();
        createNotificationChannel();
        htmlTemplate = loadAsset("stemplay_library.html");
        // Sobe a notificacao imediatamente: sem isso o Android mata/fecha
        // o service iniciado via startForegroundService (crash em 8+).
        ensureForeground("Servidor parado");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        ensureForeground(isRunning() ? "Servidor ativo" : "Servidor parado");
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (server != null) server.shutdown();
        if (s3Scanner != null) s3Scanner.shutdown();
    }

    public void setOnScanListener(OnScanListener listener) {
        this.scanListener = listener;
    }

    public boolean startServer() {
        if (server != null && server.isActive()) return true;
        // Tenta a porta padrao 8080; se estiver ocupada usa uma porta livre.
        int[] candidatas = new int[]{8080, findFreePort()};
        for (int p : candidatas) {
            try {
                LibraryServer s = new LibraryServer(p);
                s.launch();
                server = s;
                port = p;
                localUrl = "http://" + getLocalIpAddress() + ":" + port;
                ensureForeground("Servidor ativo em " + localUrl);
                startScan();
                return true;
            } catch (IOException e) {
                server = null;
            }
        }
        return false;
    }

    public void stopServer() {
        if (server != null) {
            server.shutdown();
            server = null;
        }
        localUrl = "";
        ensureForeground("Servidor parado");
    }

    public boolean isRunning() {
        return server != null && server.isActive();
    }

    public String getUrl() { return localUrl; }
    public int getPort() { return port; }
    public VisitorTracker getVisitorTracker() { return visitorTracker; }
    public Set<String> getBlockedIPs() { return blockedIPs; }
    public boolean isScanComplete() { return scanComplete; }
    public int getPdfCount() { return cachedPdfs.size(); }

    public boolean blockIP(String ip) {
        boolean novo = blockedIPs.add(ip);
        visitorTracker.remove(ip);
        if (server != null) server.killConnections(ip);
        return novo;
    }

    public void unblockIP(String ip) {
        blockedIPs.remove(ip);
    }

    public boolean isBlocked(String ip) {
        return blockedIPs.contains(ip);
    }

    public void startScan() {
        if (s3Scanner.isScanning()) return;
        scanComplete = false;

        s3Scanner.scan(new S3Scanner.ScanCallback() {
            @Override
            public void onProgress(String message) {
                if (scanListener != null) scanListener.onScanProgress(message);
            }

            @Override
            public void onComplete(List<String> pdfUrls) {
                cachedPdfs = pdfUrls;
                scanComplete = true;
                regenerateHtml();
                if (scanListener != null) {
                    scanListener.onScanComplete(pdfUrls.size());
                }
            }

            @Override
            public void onError(String error) {
                scanComplete = true;
                if (scanListener != null) scanListener.onScanError(error);
            }
        });
    }

    private void regenerateHtml() {
        if (htmlTemplate == null || cachedPdfs == null) return;
        String json = LibraryGenerator.generateJson(cachedPdfs);
        cachedHtml = htmlTemplate.replace("{courses_json}", json);
    }

    private String getHtml() {
        if (cachedHtml != null) return cachedHtml;
        if (htmlTemplate != null) return htmlTemplate.replace("{courses_json}", "[]");
        return "<h1>Carregando...</h1>";
    }

    private String loadAsset(String filename) {
        try {
            AssetManager am = getAssets();
            InputStream is = am.open(filename);
            java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
            byte[] buffer = new byte[16384];
            int n;
            while ((n = is.read(buffer)) != -1) bos.write(buffer, 0, n);
            is.close();
            return bos.toString("UTF-8");
        } catch (IOException e) {
            return "<h1>Erro ao carregar: " + filename + "</h1>";
        }
    }

    private int findFreePort() {
        try {
            java.net.ServerSocket ss = new java.net.ServerSocket(0);
            int p = ss.getLocalPort();
            ss.close();
            return p;
        } catch (IOException e) {
            return 8080;
        }
    }

    private String getLocalIpAddress() {
        try {
            WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wm != null) {
                int ip = wm.getConnectionInfo().getIpAddress();
                if (ip != 0) {
                    return String.format(java.util.Locale.US, "%d.%d.%d.%d",
                        (ip & 0xff), (ip >> 8 & 0xff), (ip >> 16 & 0xff), (ip >> 24 & 0xff));
                }
            }
        } catch (Exception ignored) {}
        try {
            java.util.Enumeration<java.net.NetworkInterface> en = java.net.NetworkInterface.getNetworkInterfaces();
            String fallback = null;
            while (en.hasMoreElements()) {
                java.net.NetworkInterface ni = en.nextElement();
                if (!ni.isUp() || ni.isLoopback() || ni.isVirtual()) continue;
                java.util.Enumeration<java.net.InetAddress> eia = ni.getInetAddresses();
                while (eia.hasMoreElements()) {
                    java.net.InetAddress ia = eia.nextElement();
                    if (ia instanceof java.net.Inet4Address && !ia.isLoopbackAddress()) {
                        if (ia.isSiteLocalAddress()) return ia.getHostAddress();
                        if (fallback == null) fallback = ia.getHostAddress();
                    }
                }
            }
            if (fallback != null) return fallback;
        } catch (Exception e) {
            e.printStackTrace();
        }
        return "127.0.0.1";
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "StemPlay Server", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Servidor local StemPlay");
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private void ensureForeground(String text) {
        try {
            Intent intent = new Intent(this, MainActivity.class);
            PendingIntent pi = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE);
            Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("StemPlay Library")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_menu_share)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            } else {
                startForeground(NOTIFICATION_ID, notification);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    /**
     * Servidor HTTP minimo com registro de conexoes por IP, heartbeat (/__hb),
     * bloqueio imediato (fecha o socket do IP banido) e proxy /pdf do bucket S3.
     */
    private class LibraryServer {

        private final int port;
        private java.net.ServerSocket serverSocket;
        private volatile boolean running = false;
        private final Map<String, CopyOnWriteArrayList<java.net.Socket>> conexoes =
            new ConcurrentHashMap<>();

        LibraryServer(int port) { this.port = port; }

        void launch() throws IOException {
            serverSocket = new java.net.ServerSocket();
            serverSocket.setReuseAddress(true);
            serverSocket.bind(new InetSocketAddress(port));
            running = true;
            Thread t = new Thread(this::runLoop, "StemPlay-Server");
            t.setDaemon(true);
            t.start();
        }

        void shutdown() {
            running = false;
            try { if (serverSocket != null) serverSocket.close(); } catch (IOException ignored) {}
            for (CopyOnWriteArrayList<java.net.Socket> list : conexoes.values()) {
                for (java.net.Socket s : list) {
                    try { s.close(); } catch (IOException ignored) {}
                }
            }
            conexoes.clear();
        }

        boolean isActive() { return running && serverSocket != null && !serverSocket.isClosed(); }

        void killConnections(String ip) {
            CopyOnWriteArrayList<java.net.Socket> list = conexoes.get(ip);
            if (list == null) return;
            for (java.net.Socket s : list) {
                try { s.close(); } catch (IOException ignored) {}
            }
        }

        private void runLoop() {
            while (running) {
                try {
                    java.net.Socket client = serverSocket.accept();
                    client.setSoTimeout(15000);
                    new Thread(() -> handleClient(client)).start();
                } catch (IOException e) {
                    if (running) e.printStackTrace();
                }
            }
        }

        private void registrar(String ip, java.net.Socket s) {
            conexoes.computeIfAbsent(ip, k -> new CopyOnWriteArrayList<>()).add(s);
        }

        private void desregistrar(String ip, java.net.Socket s) {
            CopyOnWriteArrayList<java.net.Socket> list = conexoes.get(ip);
            if (list != null) list.remove(s);
        }

        private void handleClient(java.net.Socket socket) {
            String clientIP = null;
            try {
                clientIP = socket.getInetAddress().getHostAddress();
                registrar(clientIP, socket);

                java.io.BufferedReader reader = new java.io.BufferedReader(
                    new java.io.InputStreamReader(socket.getInputStream(), "UTF-8"));
                String requestLine = reader.readLine();
                if (requestLine == null) return;

                String[] parts = requestLine.split(" ");
                if (parts.length < 2) return;

                String full = parts[1];
                String path = full.split("\\?")[0];
                String query = full.contains("?") ? full.substring(full.indexOf('?') + 1) : "";

                String line;
                String userAgent = "";
                while ((line = reader.readLine()) != null && !line.isEmpty()) {
                    if (line.toLowerCase().startsWith("user-agent:")) {
                        userAgent = line.substring(11).trim();
                    }
                }

                if (path.equals("/favicon.ico") || path.equals("/robots.txt")) {
                    sendResponse(socket, 200, "text/plain", "");
                    return;
                }

                boolean blocked = blockedIPs.contains(clientIP);

                if (path.equals("/__hb")) {
                    if (blocked) sendResponse(socket, 403, "text/plain", "blocked");
                    else {
                        visitorTracker.track(clientIP, "/reader", userAgent);
                        sendResponse(socket, 200, "text/plain", "ok");
                    }
                    return;
                }

                if (blocked) {
                    sendResponse(socket, 403, "text/plain; charset=utf-8",
                        "Voce foi bloqueado pelo administrador da StemPlay Library.");
                    return;
                }

                visitorTracker.track(clientIP, path, userAgent);

                if (path.equals("/") || path.equals("/index.html") || path.equals("/stemplay_library.html")) {
                    sendResponse(socket, 200, "text/html; charset=utf-8", getHtml());
                } else if (path.equals("/pdf")) {
                    proxyPdf(socket, query);
                } else {
                    sendResponse(socket, 404, "text/plain", "Not Found");
                }
            } catch (Exception e) {
                // conexao derrubada por ban ou cliente foi embora: normal
            } finally {
                if (clientIP != null) desregistrar(clientIP, socket);
                try { socket.close(); } catch (IOException ignored) {}
            }
        }

        private void sendResponse(java.net.Socket socket, int statusCode, String contentType, String body) throws IOException {
            String statusText;
            switch (statusCode) {
                case 200: statusText = "OK"; break;
                case 403: statusText = "Forbidden"; break;
                case 502: statusText = "Bad Gateway"; break;
                default: statusText = "Not Found";
            }
            byte[] bodyBytes = body.getBytes("UTF-8");
            String header = "HTTP/1.1 " + statusCode + " " + statusText + "\r\n"
                + "Content-Type: " + contentType + "\r\n"
                + "Content-Length: " + bodyBytes.length + "\r\n"
                + "Connection: close\r\n"
                + "Access-Control-Allow-Origin: *\r\n"
                + "\r\n";
            OutputStream os = socket.getOutputStream();
            os.write(header.getBytes("UTF-8"));
            os.write(bodyBytes);
            os.flush();
        }

        private void proxyPdf(java.net.Socket socket, String query) {
            String key = "";
            for (String kv : query.split("&")) {
                if (kv.startsWith("key=")) {
                    try { key = URLDecoder.decode(kv.substring(4), "UTF-8"); } catch (Exception ignored) {}
                    break;
                }
            }
            if (!key.startsWith(ALLOWED_PROXY_PREFIX)) {
                try { sendResponse(socket, 403, "text/plain", "Chave de arquivo nao permitida."); } catch (IOException ignored) {}
                return;
            }
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(key).openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(20000);
                conn.setReadTimeout(30000);
                conn.setInstanceFollowRedirects(true);
                int code = conn.getResponseCode();
                if (code != 200) {
                    sendResponse(socket, 502, "text/plain", "Falha no proxy S3: HTTP " + code);
                    return;
                }
                String header = "HTTP/1.1 200 OK\r\n"
                    + "Content-Type: application/pdf\r\n"
                    + "Connection: close\r\n"
                    + "Access-Control-Allow-Origin: *\r\n"
                    + "\r\n";
                OutputStream os = socket.getOutputStream();
                os.write(header.getBytes("UTF-8"));
                InputStream is = conn.getInputStream();
                byte[] buf = new byte[16384];
                int n;
                while ((n = is.read(buf)) != -1) os.write(buf, 0, n);
                os.flush();
                is.close();
            } catch (Exception e) {
                try { sendResponse(socket, 502, "text/plain", "Falha no proxy S3: " + e.getMessage()); } catch (IOException ignored) {}
            } finally {
                if (conn != null) conn.disconnect();
            }
        }
    }
}
