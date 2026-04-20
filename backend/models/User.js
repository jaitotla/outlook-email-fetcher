const mongoose = require('mongoose');
const { v4: uuidv4 } = require('uuid');

const userSchema = new mongoose.Schema({
  id: {
    type: String,
    default: uuidv4,
    unique: true
  },
  tenantId: {
    type: String,
    ref: 'Tenant',
    index: true
  },
  firstName: {
    type: String,
    required: true
  },
  lastName: {
    type: String,
    required: true
  },
  dob: {
    type: Date
  },
  country: {
    type: String
  },
  city: {
    type: String
  },
  email: {
    type: String,
    required: true,
    unique: true,
    lowercase: true,
    trim: true
  },
  role: {
    type: String,
    enum: ['admin', 'manager', 'employee', 'solo'],
    default: 'solo'
  },
  provider: {
    type: String,
    enum: ['google', 'microsoft'],
    required: true
  },
  googleId: String,
  googleAccessToken: String,
  googleRefreshToken: String,
  microsoftId: String,
  microsoftAccessToken: String,
  microsoftRefreshToken: String,
  slackWorkspaces: [{
    workspaceId: String,
    workspaceName: String,
    accessToken: String,
    refreshToken: String,
    botToken: String,
    connectedAt: Date,
    lastSyncedAt: Date,
    syncConfig: {
      enabled: Boolean,
      syncDays: {
        type: Number,
        default: 7
      },
      selectedChannels: [String],
      selectedDMs: [String],
      includePublicChannels: Boolean,
      includePrivateChannels: Boolean,
      includeDMs: Boolean,
      dmSelection: {
        type: String,
        enum: ['all', 'selected'],
        default: 'selected'
      },
      autoSync: Boolean,
      syncInterval: {
        type: Number,
        default: 3600 // seconds
      }
    },
    fileProcessing: {
      processPDFs: {
        type: Boolean,
        default: true
      },
      processDocs: {
        type: Boolean,
        default: true
      },
      processImages: {
        type: Boolean,
        default: false
      },
      maxFileSize: {
        type: Number,
        default: 10485760 // 10MB
      }
    }
  }],
  settings: {
    llmProvider: {
      type: String,
      enum: ['openai', 'gemini', 'ollama'],
      default: 'openai'
    },
    llmApiKey: String,
    vectorDb: {
      type: String,
      enum: ['pinecone', 'local'],
      default: 'pinecone'
    },
    pineconeApiKey: String,
    tone: {
      type: String,
      enum: ['professional', 'semi-professional', 'casual', 'personal'],
      default: 'professional'
    }
  },
  onboarded: {
    type: Boolean,
    default: false
  },
  active: {
    type: Boolean,
    default: true
  }
}, {
  timestamps: true
});

// Index for faster queries
userSchema.index({ email: 1, tenantId: 1 });

module.exports = mongoose.model('User', userSchema);
