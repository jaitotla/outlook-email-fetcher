const SlackMetadata = require('../models/SlackMetadata');
const ConversationPoint = require('../models/ConversationPoint');
const User = require('../models/User');

/**
 * Connect Slack workspace (handled by Passport OAuth)
 */
exports.connectWorkspace = async (req, res) => {
  try {
    // User is already authenticated via Passport
    // Slack tokens are already saved in user.slackWorkspaces
    const user = await User.findById(req.user._id);
    
    res.json({
      success: true,
      message: 'Slack workspace connected successfully',
      workspaces: user.slackWorkspaces
    });
  } catch (error) {
    console.error('Error connecting Slack workspace:', error);
    res.status(500).json({ error: error.message });
  }
};

/**
 * Get user's connected Slack workspaces
 */
exports.getWorkspaces = async (req, res) => {
  try {
    const user = await User.findById(req.user._id);
    
    const workspaces = (user.slackWorkspaces || []).map(ws => ({
      workspaceId: ws.workspaceId,
      workspaceName: ws.workspaceName,
      connectedAt: ws.connectedAt,
      lastSyncedAt: ws.lastSyncedAt,
      syncConfig: ws.syncConfig
    }));
    
    res.json({ workspaces });
  } catch (error) {
    console.error('Error fetching Slack workspaces:', error);
    res.status(500).json({ error: error.message });
  }
};

/**
 * Update Slack workspace sync configuration
 */
exports.updateSyncConfig = async (req, res) => {
  try {
    const { workspaceId } = req.params;
    const { syncConfig, fileProcessing } = req.body;
    
    const user = await User.findById(req.user._id);
    const workspace = user.slackWorkspaces.find(ws => ws.workspaceId === workspaceId);
    
    if (!workspace) {
      return res.status(404).json({ error: 'Workspace not found' });
    }
    
    if (syncConfig) {
      workspace.syncConfig = { ...workspace.syncConfig, ...syncConfig };
    }
    
    if (fileProcessing) {
      workspace.fileProcessing = { ...workspace.fileProcessing, ...fileProcessing };
    }
    
    await user.save();
    
    res.json({
      success: true,
      message: 'Sync configuration updated',
      syncConfig: workspace.syncConfig,
      fileProcessing: workspace.fileProcessing
    });
  } catch (error) {
    console.error('Error updating sync config:', error);
    res.status(500).json({ error: error.message });
  }
};

/**
 * Get available channels for a workspace
 */
exports.getChannels = async (req, res) => {
  try {
    const { workspaceId } = req.params;
    const user = await User.findById(req.user._id);
    const workspace = user.slackWorkspaces.find(ws => ws.workspaceId === workspaceId);
    
    if (!workspace) {
      return res.status(404).json({ error: 'Workspace not found' });
    }
    
    // Call Python agent to fetch channels from Slack API
    const axios = require('axios');
    const agentUrl = process.env.AGENT_URL || 'http://agent:8000';
    
    const response = await axios.post(`${agentUrl}/api/slack/channels`, {
      accessToken: workspace.accessToken
    });
    
    res.json({
      channels: response.data.channels,
      dms: response.data.dms
    });
  } catch (error) {
    console.error('Error fetching channels:', error);
    res.status(500).json({ error: error.message });
  }
};

/**
 * Trigger manual sync for a workspace
 */
exports.syncWorkspace = async (req, res) => {
  try {
    const { workspaceId } = req.params;
    const { syncDays } = req.body;
    
    const user = await User.findById(req.user._id);
    const workspace = user.slackWorkspaces.find(ws => ws.workspaceId === workspaceId);
    
    if (!workspace) {
      return res.status(404).json({ error: 'Workspace not found' });
    }
    
    // Call Python agent to ingest Slack data
    const axios = require('axios');
    const agentUrl = process.env.AGENT_URL || 'http://agent:8000';
    
    const response = await axios.post(`${agentUrl}/api/slack/ingest`, {
      userId: user._id.toString(),
      workspaceId: workspace.workspaceId,
      accessToken: workspace.accessToken,
      botToken: workspace.botToken,
      syncDays: syncDays || workspace.syncConfig.syncDays,
      selectedChannels: workspace.syncConfig.selectedChannels,
      selectedDMs: workspace.syncConfig.selectedDMs,
      includePublic: workspace.syncConfig.includePublicChannels,
      includePrivate: workspace.syncConfig.includePrivateChannels,
      includeDMs: workspace.syncConfig.includeDMs,
      fileConfig: workspace.fileProcessing
    });
    
    // Update last synced time
    workspace.lastSyncedAt = new Date();
    await user.save();
    
    res.json({
      success: true,
      message: 'Sync started successfully',
      result: response.data
    });
  } catch (error) {
    console.error('Error syncing workspace:', error);
    res.status(500).json({ error: error.message });
  }
};

/**
 * Disconnect a Slack workspace
 */
exports.disconnectWorkspace = async (req, res) => {
  try {
    const { workspaceId } = req.params;
    const user = await User.findById(req.user._id);
    
    user.slackWorkspaces = user.slackWorkspaces.filter(
      ws => ws.workspaceId !== workspaceId
    );
    
    await user.save();
    
    res.json({
      success: true,
      message: 'Workspace disconnected successfully'
    });
  } catch (error) {
    console.error('Error disconnecting workspace:', error);
    res.status(500).json({ error: error.message });
  }
};

/**
 * Save Slack metadata (called by Python agent)
 */
exports.saveMetadata = async (req, res) => {
  try {
    const metadata = new SlackMetadata(req.body);
    await metadata.save();
    
    res.json({
      success: true,
      id: metadata._id
    });
  } catch (error) {
    console.error('Error saving Slack metadata:', error);
    res.status(500).json({ error: error.message });
  }
};

/**
 * Get Slack conversation history
 */
exports.getConversations = async (req, res) => {
  try {
    const { workspaceId, channelId, startDate, endDate } = req.query;
    
    const query = {
      userId: req.user._id
    };
    
    if (workspaceId) query.workspaceId = workspaceId;
    if (channelId) query.channelId = channelId;
    if (startDate || endDate) {
      query.date = {};
      if (startDate) query.date.$gte = new Date(startDate);
      if (endDate) query.date.$lte = new Date(endDate);
    }
    
    const conversations = await SlackMetadata.find(query)
      .sort({ date: -1 })
      .limit(100)
      .select('-rawData -messages.attachments');
    
    res.json({ conversations });
  } catch (error) {
    console.error('Error fetching conversations:', error);
    res.status(500).json({ error: error.message });
  }
};
