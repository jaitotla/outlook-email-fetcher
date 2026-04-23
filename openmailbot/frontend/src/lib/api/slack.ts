/**
 * Slack API Client
 * All API calls for Slack workspace integration
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export interface SlackWorkspace {
  workspaceId: string;
  workspaceName: string;
  connectedAt: string;
  lastSyncedAt?: string;
  syncConfig: {
    enabled: boolean;
    syncDays: number;
    selectedChannels: string[];
    selectedDMs: string[];
    includePublicChannels: boolean;
    includePrivateChannels: boolean;
    includeDMs: boolean;
    dmSelection: 'all' | 'selected';
    autoSync: boolean;
    syncInterval: number;
  };
  fileProcessing: {
    processPDFs: boolean;
    processDocs: boolean;
    processImages: boolean;
    maxFileSize: number;
  };
}

export interface SlackChannel {
  id: string;
  name: string;
  is_private: boolean;
  is_member: boolean;
  num_members?: number;
}

export interface SlackDM {
  id: string;
  user: string;
  user_name?: string;
}

export interface SyncResult {
  success: boolean;
  message: string;
  result?: {
    channels_processed: number;
    dms_processed: number;
    messages_ingested: number;
    files_processed: number;
    errors: string[];
  };
}

class SlackAPI {
  /**
   * Initiate Slack OAuth flow
   */
  connect() {
    window.location.href = `${API_URL}/api/slack/auth`;
  }

  /**
   * Get all connected workspaces
   */
  async getWorkspaces(): Promise<{ workspaces: SlackWorkspace[] }> {
    const response = await fetch(`${API_URL}/api/slack/workspaces`, {
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch workspaces');
    }

    return response.json();
  }

  /**
   * Get channels for a workspace
   */
  async getChannels(workspaceId: string): Promise<{ channels: SlackChannel[]; dms: SlackDM[] }> {
    const response = await fetch(`${API_URL}/api/slack/workspaces/${workspaceId}/channels`, {
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch channels');
    }

    return response.json();
  }

  /**
   * Update workspace sync configuration
   */
  async updateSyncConfig(
    workspaceId: string,
    config: Partial<{
      syncConfig: Partial<SlackWorkspace['syncConfig']>;
      fileProcessing: Partial<SlackWorkspace['fileProcessing']>;
    }>
  ): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_URL}/api/slack/workspaces/${workspaceId}/config`, {
      method: 'PUT',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      throw new Error('Failed to update sync config');
    }

    return response.json();
  }

  /**
   * Trigger manual sync for a workspace
   */
  async syncWorkspace(workspaceId: string, syncDays?: number): Promise<SyncResult> {
    const response = await fetch(`${API_URL}/api/slack/workspaces/${workspaceId}/sync`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ syncDays }),
    });

    if (!response.ok) {
      throw new Error('Failed to sync workspace');
    }

    return response.json();
  }

  /**
   * Disconnect a workspace
   */
  async disconnectWorkspace(workspaceId: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_URL}/api/slack/workspaces/${workspaceId}`, {
      method: 'DELETE',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to disconnect workspace');
    }

    return response.json();
  }
}

export const slackApi = new SlackAPI();
