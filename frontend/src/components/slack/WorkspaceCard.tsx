'use client'

import { useState } from 'react';
import { Slack, Calendar, Settings, Trash2, RefreshCw } from 'lucide-react';
import type { SlackWorkspace } from '@/lib/api/slack';

interface WorkspaceCardProps {
  workspace: SlackWorkspace;
  onConfigure: (workspaceId: string) => void;
  onSync: (workspaceId: string) => void;
  onDisconnect: (workspaceId: string) => void;
}

export default function WorkspaceCard({ workspace, onConfigure, onSync, onDisconnect }: WorkspaceCardProps) {
  const [isSyncing, setIsSyncing] = useState(false);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await onSync(workspace.workspaceId);
    } finally {
      setIsSyncing(false);
    }
  };

  const getTimeAgo = (date?: string) => {
    if (!date) return 'Never';
    const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
    
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const channelCount = workspace.syncConfig.selectedChannels?.length || 0;
  const dmCount = workspace.syncConfig.dmSelection === 'all' ? 'All' : workspace.syncConfig.selectedDMs?.length || 0;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-[#4A154B] rounded-lg flex items-center justify-center">
            <Slack className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-lg">{workspace.workspaceName}</h3>
            <div className="flex items-center gap-1 text-sm text-gray-500">
              <div className={`w-2 h-2 rounded-full ${workspace.syncConfig.enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
              {workspace.syncConfig.enabled ? 'Active' : 'Paused'}
            </div>
          </div>
        </div>
        <button
          onClick={() => onDisconnect(workspace.workspaceId)}
          className="text-gray-400 hover:text-red-600 transition-colors"
          title="Disconnect workspace"
        >
          <Trash2 className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-2 mb-4 text-sm">
        <div className="flex items-center gap-2 text-gray-600">
          <span className="font-medium">{channelCount}</span> channels
          <span className="text-gray-400">•</span>
          <span className="font-medium">{dmCount}</span> {workspace.syncConfig.dmSelection === 'all' ? 'DMs' : 'selected DMs'}
        </div>
        <div className="flex items-center gap-2 text-gray-500">
          <Calendar className="w-4 h-4" />
          Last synced: {getTimeAgo(workspace.lastSyncedAt)}
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onConfigure(workspace.workspaceId)}
          className="flex-1 flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg font-medium transition-colors"
        >
          <Settings className="w-4 h-4" />
          Configure
        </button>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          Sync
        </button>
      </div>
    </div>
  );
}
