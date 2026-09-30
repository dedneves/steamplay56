package com.stemplay.library;

import android.Manifest;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.IBinder;
import android.view.View;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.switchmaterial.SwitchMaterial;
import com.google.zxing.BarcodeFormat;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.qrcode.QRCodeWriter;

import java.util.Collections;
import java.util.List;
import java.util.Timer;
import java.util.TimerTask;

public class MainActivity extends AppCompatActivity {

    private static final int REQ_NOTIF = 101;

    private ServerService serverService;
    private boolean bound = false;
    private SwitchMaterial serverSwitch;
    private TextView statusText, portText, urlText, visitorCount, noVisitorsText, noBlockedText;
    private TextView scanStatusText, pdfCountText;
    private View statusDot;
    private ImageView qrImage;
    private RecyclerView visitorList, blockedList;
    private VisitorAdapter visitorAdapter;
    private BlockedAdapter blockedAdapter;
    private Timer refreshTimer;

    private final ServiceConnection connection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder service) {
            ServerService.LocalBinder binder = (ServerService.LocalBinder) service;
            serverService = binder.getService();
            bound = true;
            serverService.setOnScanListener(new ServerService.OnScanListener() {
                @Override
                public void onScanProgress(String message) {
                    runOnUiThread(() -> { if (!isFinishing()) scanStatusText.setText(message); });
                }
                @Override
                public void onScanComplete(int pdfCount) {
                    runOnUiThread(() -> {
                        if (isFinishing()) return;
                        scanStatusText.setText(pdfCount + " PDFs encontrados");
                        pdfCountText.setText(pdfCount + " PDFs");
                    });
                }
                @Override
                public void onScanError(String error) {
                    runOnUiThread(() -> { if (!isFinishing()) scanStatusText.setText("Erro: " + error); });
                }
            });
            // Adapters agora apontam para os conjuntos reais do servico
            setupRecyclerViews();
            setupSwitchHandler();
            updateUI();
            startRefreshTimer();
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            bound = false;
            serverService = null;
            stopRefreshTimer();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        initViews();
        setupRecyclerViews();
        setupSwitchHandler();
        setupListeners();

        if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIF);
        }

        Intent intent = new Intent(this, ServerService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
        bindService(intent, connection, Context.BIND_AUTO_CREATE);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopRefreshTimer();
        if (bound) {
            try { unbindService(connection); } catch (Exception ignored) {}
            bound = false;
        }
    }

    private void initViews() {
        serverSwitch = findViewById(R.id.serverSwitch);
        statusText = findViewById(R.id.statusText);
        portText = findViewById(R.id.portText);
        urlText = findViewById(R.id.urlText);
        visitorCount = findViewById(R.id.visitorCount);
        noVisitorsText = findViewById(R.id.noVisitorsText);
        noBlockedText = findViewById(R.id.noBlockedText);
        statusDot = findViewById(R.id.statusDot);
        qrImage = findViewById(R.id.qrImage);
        visitorList = findViewById(R.id.visitorList);
        blockedList = findViewById(R.id.blockedList);
        scanStatusText = findViewById(R.id.scanStatusText);
        pdfCountText = findViewById(R.id.pdfCountText);
    }

    private void setupRecyclerViews() {
        visitorAdapter = new VisitorAdapter(
            bound && serverService != null ? serverService.getBlockedIPs() : Collections.emptySet(),
            ip -> {
                if (bound && serverService != null) {
                    serverService.blockIP(ip);
                    Toast.makeText(this, "IP bloqueado e conexoes derrubadas: " + ip,
                        Toast.LENGTH_SHORT).show();
                    updateVisitorList();
                    updateBlockedList();
                }
            }
        );
        visitorList.setLayoutManager(new LinearLayoutManager(this));
        visitorList.setAdapter(visitorAdapter);

        blockedAdapter = new BlockedAdapter(ip -> {
            if (bound && serverService != null) {
                serverService.unblockIP(ip);
                Toast.makeText(this, "IP desbloqueado: " + ip, Toast.LENGTH_SHORT).show();
                updateVisitorList();
                updateBlockedList();
            }
        });
        blockedList.setLayoutManager(new LinearLayoutManager(this));
        blockedList.setAdapter(blockedAdapter);
    }

    private void setupSwitchHandler() {
        serverSwitch.setOnCheckedChangeListener((buttonView, isChecked) -> {
            if (!bound || serverService == null) return;
            if (isChecked) {
                boolean ok = false;
                try { ok = serverService.startServer(); } catch (Exception e) {
                    Toast.makeText(this, "Erro ao iniciar: " + e.getMessage(), Toast.LENGTH_LONG).show();
                }
                if (ok) {
                    updateUI();
                    Toast.makeText(this, "Servidor iniciado!", Toast.LENGTH_SHORT).show();
                } else {
                    serverSwitch.setChecked(false);
                    Toast.makeText(this, "Erro ao iniciar servidor (porta ocupada?)", Toast.LENGTH_SHORT).show();
                }
            } else {
                serverService.stopServer();
                updateUI();
                Toast.makeText(this, "Servidor parado", Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void setupListeners() {
        findViewById(R.id.btnCopyUrl).setOnClickListener(v -> {
            if (bound && serverService != null) {
                android.content.ClipboardManager cm = (android.content.ClipboardManager)
                    getSystemService(Context.CLIPBOARD_SERVICE);
                android.content.ClipData clip = android.content.ClipData.newPlainText("url", serverService.getUrl());
                cm.setPrimaryClip(clip);
                Toast.makeText(this, "Link copiado!", Toast.LENGTH_SHORT).show();
            }
        });

        findViewById(R.id.btnShare).setOnClickListener(v -> {
            if (bound && serverService != null && serverService.isRunning()) {
                Intent shareIntent = new Intent(Intent.ACTION_SEND);
                shareIntent.setType("text/plain");
                shareIntent.putExtra(Intent.EXTRA_SUBJECT, "StemPlay Library");
                shareIntent.putExtra(Intent.EXTRA_TEXT,
                    "Acesse a biblioteca StemPlay (reader Steamplay 2):\n" + serverService.getUrl() +
                    "\n\nEscaneie o QR Code ou acesse pelo navegador no mesmo Wi-Fi.");
                startActivity(Intent.createChooser(shareIntent, "Compartilhar link"));
            }
        });

        findViewById(R.id.btnOpenBrowser).setOnClickListener(v -> {
            if (bound && serverService != null && serverService.isRunning()) {
                try {
                    Intent browserIntent = new Intent(Intent.ACTION_VIEW,
                        Uri.parse(serverService.getUrl()));
                    startActivity(browserIntent);
                } catch (Exception e) {
                    Toast.makeText(this, "Nenhum navegador disponivel", Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    private void updateUI() {
        if (!bound || serverService == null) return;
        boolean running = serverService.isRunning();
        serverSwitch.setOnCheckedChangeListener(null);
        serverSwitch.setChecked(running);
        setupSwitchHandler();

        if (running) {
            statusText.setText("Servidor ativo");
            statusText.setTextColor(getColor(R.color.status_online));
            portText.setText("Porta: " + serverService.getPort());
            urlText.setText(serverService.getUrl());
            statusDot.getBackground().setTint(getColor(R.color.status_online));
            generateQR(serverService.getUrl());
            if (serverService.isScanComplete()) {
                scanStatusText.setText(serverService.getPdfCount() + " PDFs encontrados");
                pdfCountText.setText(serverService.getPdfCount() + " PDFs");
            } else {
                scanStatusText.setText("Escaneando S3...");
                pdfCountText.setText("...");
            }
        } else {
            statusText.setText("Servidor parado");
            statusText.setTextColor(getColor(R.color.dark_text2));
            portText.setText("Porta: ---");
            urlText.setText("Ligue o servidor para acessar");
            statusDot.getBackground().setTint(getColor(R.color.status_offline));
            qrImage.setImageBitmap(null);
            scanStatusText.setText("Ligue o servidor para escanear");
            pdfCountText.setText("0 PDFs");
        }

        updateVisitorList();
        updateBlockedList();
    }

    private void generateQR(String url) {
        try {
            QRCodeWriter writer = new QRCodeWriter();
            BitMatrix matrix = writer.encode(url, BarcodeFormat.QR_CODE, 400, 400);
            int width = matrix.getWidth();
            int height = matrix.getHeight();
            Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.RGB_565);
            for (int x = 0; x < width; x++) {
                for (int y = 0; y < height; y++) {
                    bitmap.setPixel(x, y, matrix.get(x, y) ? Color.BLACK : Color.WHITE);
                }
            }
            qrImage.setImageBitmap(bitmap);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void updateVisitorList() {
        if (!bound || serverService == null) return;
        List<VisitorTracker.VisitorInfo> active = serverService.getVisitorTracker().getActive();
        visitorAdapter.setVisitors(active);
        visitorCount.setText(String.valueOf(active.size()));
        noVisitorsText.setVisibility(active.isEmpty() ? View.VISIBLE : View.GONE);
        visitorList.setVisibility(active.isEmpty() ? View.GONE : View.VISIBLE);
    }

    private void updateBlockedList() {
        if (!bound || serverService == null) return;
        blockedAdapter.setBlocked(serverService.getBlockedIPs());
        noBlockedText.setVisibility(serverService.getBlockedIPs().isEmpty() ? View.VISIBLE : View.GONE);
        blockedList.setVisibility(serverService.getBlockedIPs().isEmpty() ? View.GONE : View.VISIBLE);
    }

    private void startRefreshTimer() {
        stopRefreshTimer();
        refreshTimer = new Timer();
        refreshTimer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                runOnUiThread(() -> {
                    if (isFinishing() || !bound) return;
                    updateVisitorList();
                    updateBlockedList();
                });
            }
        }, 2000, 3000);
    }

    private void stopRefreshTimer() {
        if (refreshTimer != null) {
            refreshTimer.cancel();
            refreshTimer = null;
        }
    }
}
