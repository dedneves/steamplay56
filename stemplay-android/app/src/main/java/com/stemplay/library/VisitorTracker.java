package com.stemplay.library;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

public class VisitorTracker {

    private final ConcurrentHashMap<String, VisitorInfo> visitors = new ConcurrentHashMap<>();
    private OnVisitorChangedListener listener;

    public interface OnVisitorChangedListener {
        void onVisitorsChanged(List<VisitorInfo> visitors);
    }

    public void setOnVisitorChangedListener(OnVisitorChangedListener l) {
        this.listener = l;
    }

    public void track(String ip, String page, String userAgent) {
        String type = ip.startsWith("192.168.") || ip.startsWith("10.") || ip.startsWith("172.")
            ? "LOCAL" : "REDE";
        visitors.put(ip, new VisitorInfo(ip, page, userAgent, type, System.currentTimeMillis()));
        notifyListener();
    }

    public void remove(String ip) {
        visitors.remove(ip);
        notifyListener();
    }

    public List<VisitorInfo> getActive() {
        long now = System.currentTimeMillis();
        long timeout = 60_000;
        List<VisitorInfo> active = new ArrayList<>();
        Iterator<ConcurrentHashMap.Entry<String, VisitorInfo>> it = visitors.entrySet().iterator();
        while (it.hasNext()) {
            ConcurrentHashMap.Entry<String, VisitorInfo> entry = it.next();
            if (now - entry.getValue().getLastSeen() < timeout) {
                active.add(entry.getValue());
            } else {
                it.remove();
            }
        }
        Collections.sort(active, (a, b) -> Long.compare(b.getLastSeen(), a.getLastSeen()));
        return active;
    }

    public int getCount() {
        return getActive().size();
    }

    private void notifyListener() {
        if (listener != null) {
            listener.onVisitorsChanged(getActive());
        }
    }

    public static class VisitorInfo {
        private final String ip;
        private final String page;
        private final String userAgent;
        private final String type;
        private final long lastSeen;

        public VisitorInfo(String ip, String page, String userAgent, String type, long lastSeen) {
            this.ip = ip;
            this.page = page;
            this.userAgent = userAgent;
            this.type = type;
            this.lastSeen = lastSeen;
        }

        public String getIp() { return ip; }
        public String getPage() { return page; }
        public String getUserAgent() { return userAgent; }
        public String getType() { return type; }
        public long getLastSeen() { return lastSeen; }

        public String getTimeAgo() {
            long seconds = (System.currentTimeMillis() - lastSeen) / 1000;
            if (seconds < 5) return "agora";
            if (seconds < 60) return seconds + "s atras";
            if (seconds < 3600) return (seconds / 60) + "min atras";
            return (seconds / 3600) + "h atras";
        }

        public String getShortUA() {
            if (userAgent == null || userAgent.isEmpty()) return "Desconhecido";
            if (userAgent.contains("Chrome") && userAgent.contains("Mobile")) return "Chrome Mobile";
            if (userAgent.contains("Firefox")) return "Firefox";
            if (userAgent.contains("Safari") && !userAgent.contains("Chrome")) return "Safari";
            if (userAgent.contains("Samsung")) return "Samsung Browser";
            if (userAgent.contains("Edg")) return "Edge";
            if (userAgent.contains("Opera") || userAgent.contains("OPR")) return "Opera";
            return "Navegador";
        }
    }
}
