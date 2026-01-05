const mongoose = require('mongoose');

const slackMetadataSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
    index: true
  },
  tenantId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Tenant',
    required: true,
    index: true
  },
  workspaceId: {
    type: String,
    required: true,
    index: true
  },
  workspaceName: String,
  channelId: {
    type: String,
    index: true
  },
  channelName: String,
  channelType: {
    type: String,
    enum: ['public_channel', 'private_channel', 'im', 'mpim'],
    index: true
  },
  messageType: {
    type: String,
    enum: ['channel_message', 'direct_message', 'thread_reply'],
    required: true,
    index: true
  },
  threadTs: String, // Thread timestamp for threaded messages
  isThreadParent: Boolean,
  date: {
    type: Date,
    required: true,
    index: true
  },
  dateRange: {
    start: Date,
    end: Date
  },
  messages: [{
    ts: String,
    userId: String,
    userName: String,
    text: String,
    timestamp: Date,
    reactions: [{
      emoji: String,
      count: Number,
      users: [String]
    }],
    attachments: [{
      type: String, // 'file', 'link', 'image'
      name: String,
      url: String,
      mimeType: String,
      size: Number,
      extractedText: String,
      ocrText: String,
      processed: Boolean
    }]
  }],
  conversationPointId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'ConversationPoint'
  },
  linkedEmailThreads: [{
    type: mongoose.Schema.Types.ObjectId,
    ref: 'EmailMetadata'
  }],
  rawData: {
    type: mongoose.Schema.Types.Mixed,
    select: false // Don't include by default
  },
  syncStatus: {
    lastSyncedAt: Date,
    status: {
      type: String,
      enum: ['pending', 'processing', 'completed', 'failed'],
      default: 'pending'
    },
    error: String
  },
  createdAt: {
    type: Date,
    default: Date.now
  },
  updatedAt: {
    type: Date,
    default: Date.now
  }
});

// Compound indexes
slackMetadataSchema.index({ userId: 1, workspaceId: 1, date: -1 });
slackMetadataSchema.index({ userId: 1, channelId: 1, date: -1 });
slackMetadataSchema.index({ tenantId: 1, messageType: 1 });
slackMetadataSchema.index({ 'syncStatus.status': 1 });

// Update timestamp
slackMetadataSchema.pre('save', function(next) {
  this.updatedAt = new Date();
  next();
});

module.exports = mongoose.model('SlackMetadata', slackMetadataSchema);
