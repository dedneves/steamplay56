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

public class BlockedAdapter extends RecyclerView.Adapter<BlockedAdapter.ViewHolder> {

    private List<String> blockedIPs = new ArrayList<>();
    private OnUnblockListener unblockListener;

    public interface OnUnblockListener {
        void onUnblock(String ip);
    }

    public BlockedAdapter(OnUnblockListener listener) {
        this.unblockListener = listener;
    }

    public void setBlocked(Set<String> ips) {
        this.blockedIPs = new ArrayList<>(ips);
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_blocked, parent, false);
        return new ViewHolder(v);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        String ip = blockedIPs.get(position);
        holder.ipText.setText(ip);
        holder.unblockBtn.setOnClickListener(v -> {
            if (unblockListener != null) unblockListener.onUnblock(ip);
        });
    }

    @Override
    public int getItemCount() { return blockedIPs.size(); }

    static class ViewHolder extends RecyclerView.ViewHolder {
        TextView ipText, unblockBtn;

        ViewHolder(View v) {
            super(v);
            ipText = v.findViewById(R.id.blockedIp);
            unblockBtn = v.findViewById(R.id.btnUnblock);
        }
    }
}
