'use client'

import { useState, useEffect } from 'react';
import { Search, Hash, Lock, MessageSquare, Check } from 'lucide-react';
import type { SlackChannel, SlackDM } from '@/lib/api/slack';

interface ChannelSelectorProps {
  channels: SlackChannel[];
  dms: SlackDM[];
  selectedChannels: string[];
  selectedDMs: string[];
  dmSelection: 'all' | 'selected';
  includePublicChannels: boolean;
  includePrivateChannels: boolean;
  includeDMs: boolean;
  onChange: (updates: {
    selectedChannels?: string[];
    selectedDMs?: string[];
    dmSelection?: 'all' | 'selected';
    includePublicChannels?: boolean;
    includePrivateChannels?: boolean;
    includeDMs?: boolean;
  }) => void;
}

export default function ChannelSelector({
  channels,
  dms,
  selectedChannels,
  selectedDMs,
  dmSelection,
  includePublicChannels,
  includePrivateChannels,
  includeDMs,
  onChange,
}: ChannelSelectorProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState<'channels' | 'dms'>('channels');

  const publicChannels = channels.filter(c => !c.is_private);
  const privateChannels = channels.filter(c => c.is_private);

  const filteredPublicChannels = publicChannels.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredPrivateChannels = privateChannels.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredDMs = dms.filter(dm =>
    (dm.user_name || dm.user).toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleChannelToggle = (channelId: string) => {
    const newSelected = selectedChannels.includes(channelId)
      ? selectedChannels.filter(id => id !== channelId)
      : [...selectedChannels, channelId];
    onChange({ selectedChannels: newSelected });
  };

  const handleDMToggle = (dmId: string) => {
    const newSelected = selectedDMs.includes(dmId)
      ? selectedDMs.filter(id => id !== dmId)
      : [...selectedDMs, dmId];
    onChange({ selectedDMs: newSelected });
  };

  const handleSelectAllChannels = () => {
    const allChannelIds = [
      ...(includePublicChannels ? publicChannels.map(c => c.id) : []),
      ...(includePrivateChannels ? privateChannels.map(c => c.id) : []),
    ];
    onChange({ selectedChannels: allChannelIds });
  };

  const handleDeselectAllChannels = () => {
    onChange({ selectedChannels: [] });
  };

  const handleSelectAllDMs = () => {
    onChange({ selectedDMs: dms.map(dm => dm.id) });
  };

  const handleDeselectAllDMs = () => {
    onChange({ selectedDMs: [] });
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('channels')}
          className={`flex-1 px-6 py-3 font-medium transition-colors ${
            activeTab === 'channels'
              ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
          }`}
        >
          Channels ({channels.length})
        </button>
        <button
          onClick={() => setActiveTab('dms')}
          className={`flex-1 px-6 py-3 font-medium transition-colors ${
            activeTab === 'dms'
              ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
          }`}
        >
          Direct Messages ({dms.length})
        </button>
      </div>

      {/* Search */}
      <div className="p-4 border-b border-gray-200">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder={activeTab === 'channels' ? 'Search channels...' : 'Search DMs...'}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600"
          />
        </div>
      </div>

      {/* Channels Tab */}
      {activeTab === 'channels' && (
        <div className="p-4">
          <div className="flex gap-2 mb-4">
            <button
              onClick={handleSelectAllChannels}
              className="px-3 py-1.5 text-sm bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors"
            >
              Select All
            </button>
            <button
              onClick={handleDeselectAllChannels}
              className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Deselect All
            </button>
          </div>

          <div className="space-y-4 max-h-96 overflow-y-auto">
            {/* Public Channels */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  id="includePublic"
                  checked={includePublicChannels}
                  onChange={(e) => onChange({ includePublicChannels: e.target.checked })}
                  className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-600"
                />
                <label htmlFor="includePublic" className="font-medium text-gray-700">
                  Public Channels
                </label>
              </div>
              {includePublicChannels && (
                <div className="ml-6 space-y-2">
                  {filteredPublicChannels.map(channel => (
                    <label
                      key={channel.id}
                      className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedChannels.includes(channel.id)}
                        onChange={() => handleChannelToggle(channel.id)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-600"
                      />
                      <Hash className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-900">{channel.name}</span>
                      {channel.num_members && (
                        <span className="text-sm text-gray-500 ml-auto">
                          {channel.num_members} members
                        </span>
                      )}
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Private Channels */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  id="includePrivate"
                  checked={includePrivateChannels}
                  onChange={(e) => onChange({ includePrivateChannels: e.target.checked })}
                  className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-600"
                />
                <label htmlFor="includePrivate" className="font-medium text-gray-700">
                  Private Channels
                </label>
              </div>
              {includePrivateChannels && (
                <div className="ml-6 space-y-2">
                  {filteredPrivateChannels.map(channel => (
                    <label
                      key={channel.id}
                      className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedChannels.includes(channel.id)}
                        onChange={() => handleChannelToggle(channel.id)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-600"
                      />
                      <Lock className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-900">{channel.name}</span>
                      {channel.num_members && (
                        <span className="text-sm text-gray-500 ml-auto">
                          {channel.num_members} members
                        </span>
                      )}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* DMs Tab */}
      {activeTab === 'dms' && (
        <div className="p-4">
          <div className="space-y-4">
            {/* DM Selection Mode */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="dmSelection"
                    checked={dmSelection === 'all'}
                    onChange={() => onChange({ dmSelection: 'all', includeDMs: true })}
                    className="w-4 h-4 text-blue-600 focus:ring-2 focus:ring-blue-600"
                  />
                  <div>
                    <div className="font-medium text-gray-900">All Direct Messages</div>
                    <div className="text-sm text-gray-600">
                      Sync all DMs automatically
                    </div>
                  </div>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="dmSelection"
                    checked={dmSelection === 'selected'}
                    onChange={() => onChange({ dmSelection: 'selected', includeDMs: true })}
                    className="w-4 h-4 text-blue-600 focus:ring-2 focus:ring-blue-600"
                  />
                  <div>
                    <div className="font-medium text-gray-900">Selected Direct Messages</div>
                    <div className="text-sm text-gray-600">
                      Choose specific DMs to sync
                    </div>
                  </div>
                </label>
              </div>
            </div>

            {/* Selected DMs List */}
            {dmSelection === 'selected' && (
              <>
                <div className="flex gap-2">
                  <button
                    onClick={handleSelectAllDMs}
                    className="px-3 py-1.5 text-sm bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors"
                  >
                    Select All
                  </button>
                  <button
                    onClick={handleDeselectAllDMs}
                    className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                  >
                    Deselect All
                  </button>
                </div>

                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {filteredDMs.map(dm => (
                    <label
                      key={dm.id}
                      className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedDMs.includes(dm.id)}
                        onChange={() => handleDMToggle(dm.id)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-600"
                      />
                      <MessageSquare className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-900">{dm.user_name || dm.user}</span>
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
