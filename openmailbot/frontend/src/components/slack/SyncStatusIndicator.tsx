'use client'

import { CheckCircle, XCircle, Loader2, Clock } from 'lucide-react';

interface SyncStatusIndicatorProps {
  status: 'idle' | 'syncing' | 'success' | 'error';
  lastSyncedAt?: string;
  error?: string;
}

export default function SyncStatusIndicator({ status, lastSyncedAt, error }: SyncStatusIndicatorProps) {
  const getTimeAgo = (date?: string) => {
    if (!date) return 'Never';
    const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
    
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  if (status === 'syncing') {
    return (
      <div className="flex items-center gap-2 text-blue-600">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm font-medium">Syncing...</span>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex items-center gap-2 text-red-600">
        <XCircle className="w-4 h-4" />
        <span className="text-sm font-medium">Sync failed</span>
        {error && <span className="text-xs text-red-500">({error})</span>}
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="flex items-center gap-2 text-green-600">
        <CheckCircle className="w-4 h-4" />
        <span className="text-sm font-medium">Synced {getTimeAgo(lastSyncedAt)}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-gray-500">
      <Clock className="w-4 h-4" />
      <span className="text-sm font-medium">Last synced: {getTimeAgo(lastSyncedAt)}</span>
    </div>
  );
}
