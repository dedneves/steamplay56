package com.stemplay.library;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

public class VisitorAdapter extends RecyclerView.Adapter<VisitorAdapter.ViewHolder> {

    private List<VisitorTracker.VisitorInfo> visitors = new ArrayList<>();
    private Set<String> blockedIPs;
    private OnBlockListener blockListener;

    public interface OnBlockListener {
        void onBlock(String ip);
    }

    public VisitorAdapter(Set<String> blockedIPs, OnBlockListener listener) {
        this.blockedIPs = blockedIPs;
        this.blockListener = listener;
    }

    public void setVisitors(List<VisitorTracker.VisitorInfo> visitors) {
        this.visitors = visitors;
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_visitor, parent, false);
        return new ViewHolder(v);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        VisitorTracker.VisitorInfo visitor = visitors.get(position);
        holder.ipText.setText(visitor.getIp());
        holder.infoText.setText(visitor.getType() + " · " + visitor.getShortUA() + " · " + visitor.getTimeAgo());

        if (blockedIPs.contains(visitor.getIp())) {
            holder.blockBtn.setText("Bloqueado");
            holder.blockBtn.setEnabled(false);
        } else {
            holder.blockBtn.setText("Bloquear");
            holder.blockBtn.setEnabled(true);
            holder.blockBtn.setOnClickListener(v -> {
                if (blockListener != null) blockListener.onBlock(visitor.getIp());
            });
        }
    }

    @Override
    public int getItemCount() { return visitors.size(); }

    static class ViewHolder extends RecyclerView.ViewHolder {
        TextView ipText, infoText;
        TextView blockBtn;

        ViewHolder(View v) {
            super(v);
            ipText = v.findViewById(R.id.visitorIp);
            infoText = v.findViewById(R.id.visitorInfo);
            blockBtn = v.findViewById(R.id.btnBlockIp);
        }
    }
}
