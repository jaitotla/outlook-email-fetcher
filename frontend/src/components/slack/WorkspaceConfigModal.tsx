'use client'

import { useState, useEffect } from 'react';
import { X, ArrowLeft, Save, RefreshCw } from 'lucide-react';
import { slackApi, type SlackWorkspace, type SlackChannel, type SlackDM } from '@/lib/api/slack';
import ChannelSelector from './ChannelSelector';
import SyncConfigPanel from './SyncConfigPanel';
import FileTypeSettings from './FileTypeSettings';

interface WorkspaceConfigModalProps {
  workspace: SlackWorkspace;
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;
}

export default function WorkspaceConfigModal({ workspace, isOpen, onClose, onSave }: WorkspaceConfigModalProps) {
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [dms, setDMs] = useState<SlackDM[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [config, setConfig] = useState(workspace);

  useEffect(() => {
    if (isOpen) {
      loadChannels();
      setConfig(workspace);
    }
  }, [isOpen, workspace]);

  const loadChannels = async () => {
    setIsLoading(true);
    try {
      const data = await slackApi.getChannels(workspace.workspaceId);
      setChannels(data.channels || []);
      setDMs(data.dms || []);
    } catch (error) {
      console.error('Failed to load channels:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await slackApi.updateSyncConfig(workspace.workspaceId, {
        syncConfig: config.syncConfig,
        fileProcessing: config.fileProcessing,
      });
      onSave();
      onClose();
    } catch (error) {
      console.error('Failed to save config:', error);
      alert('Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSyncNow = async () => {
    setIsSyncing(true);
    try {
      await slackApi.syncWorkspace(workspace.workspaceId);
      alert('Sync started successfully!');
    } catch (error) {
      console.error('Failed to sync:', error);
      alert('Failed to start sync');
    } finally {
      setIsSyncing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">{workspace.workspaceName}</h2>
              <p className="text-sm text-gray-600">Configure workspace settings</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-6 h-6 text-gray-600" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
            </div>
          ) : (
            <div className="space-y-6">
              {/* Channels & DMs */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Channels & Direct Messages</h3>
                <ChannelSelector
                  channels={channels}
                  dms={dms}
                  selectedChannels={config.syncConfig.selectedChannels}
                  selectedDMs={config.syncConfig.selectedDMs}
                  dmSelection={config.syncConfig.dmSelection}
                  includePublicChannels={config.syncConfig.includePublicChannels}
                  includePrivateChannels={config.syncConfig.includePrivateChannels}
                  includeDMs={config.syncConfig.includeDMs}
                  onChange={(updates) => {
                    setConfig({
                      ...config,
                      syncConfig: { ...config.syncConfig, ...updates },
                    });
                  }}
                />
              </div>

              {/* Sync Settings */}
              <SyncConfigPanel
                syncConfig={config.syncConfig}
                onChange={(updates) => {
                  setConfig({
                    ...config,
                    syncConfig: { ...config.syncConfig, ...updates },
                  });
                }}
              />

              {/* File Processing */}
              <FileTypeSettings
                fileProcessing={config.fileProcessing}
                onChange={(updates) => {
                  setConfig({
                    ...config,
                    fileProcessing: { ...config.fileProcessing, ...updates },
                  });
                }}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
          <button
            onClick={handleSyncNow}
            disabled={isSyncing}
            className="flex items-center gap-2 bg-gray-200 hover:bg-gray-300 disabled:bg-gray-100 text-gray-700 px-6 py-2 rounded-lg font-medium transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
            {isSyncing ? 'Syncing...' : 'Sync Now'}
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-6 py-2 text-gray-700 hover:bg-gray-100 rounded-lg font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-2 rounded-lg font-medium transition-colors"
            >
              <Save className="w-4 h-4" />
              {isSaving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
