'use client'

import type { SlackWorkspace } from '@/lib/api/slack';

interface SyncConfigPanelProps {
  syncConfig: SlackWorkspace['syncConfig'];
  onChange: (updates: Partial<SlackWorkspace['syncConfig']>) => void;
}

export default function SyncConfigPanel({ syncConfig, onChange }: SyncConfigPanelProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Sync Settings</h3>
      
      <div className="space-y-4">
        {/* Auto Sync Toggle */}
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-gray-900">Auto Sync</p>
            <p className="text-sm text-gray-600">Automatically sync messages at regular intervals</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={syncConfig.autoSync}
              onChange={(e) => onChange({ autoSync: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>

        {/* Sync Interval */}
        {syncConfig.autoSync && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Sync Interval (minutes)
            </label>
            <select
              value={syncConfig.syncInterval / 60}
              onChange={(e) => onChange({ syncInterval: parseInt(e.target.value) * 60 })}
              className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              <option value="15">Every 15 minutes</option>
              <option value="30">Every 30 minutes</option>
              <option value="60">Every hour</option>
              <option value="120">Every 2 hours</option>
              <option value="240">Every 4 hours</option>
              <option value="480">Every 8 hours</option>
              <option value="1440">Daily</option>
            </select>
          </div>
        )}

        {/* Sync Days */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            History to Sync (days)
          </label>
          <input
            type="number"
            value={syncConfig.syncDays}
            onChange={(e) => onChange({ syncDays: parseInt(e.target.value) || 7 })}
            min="1"
            max="365"
            className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
          />
          <p className="mt-1 text-sm text-gray-500">
            Number of days of message history to sync
          </p>
        </div>

        {/* Enable/Disable Sync */}
        <div className="pt-4 border-t">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900">Sync Enabled</p>
              <p className="text-sm text-gray-600">Enable or pause syncing for this workspace</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={syncConfig.enabled}
                onChange={(e) => onChange({ enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
