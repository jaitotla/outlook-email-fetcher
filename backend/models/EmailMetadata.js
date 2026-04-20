const mongoose = require('mongoose');
const { v4: uuidv4 } = require('uuid');

const emailMetadataSchema = new mongoose.Schema({
  id: {
    type: String,
    default: uuidv4,
    unique: true
  },
  tenantId: {
    type: String,
    ref: 'Tenant',
    required: true,
    index: true
  },
  userId: {
    type: String,
    ref: 'User',
    required: true,
    index: true
  },
  messageId: {
    type: String,
    required: true,
    unique: true
  },
  threadId: {
    type: String,
    required: true,
    index: true
  },
  subject: {
    type: String,
    required: true
  },
  from: {
    type: String,
    required: true
  },
  to: [{
    type: String
  }],
  cc: [{
    type: String
  }],
  bcc: [{
    type: String
  }],
  timestamp: {
    type: Date,
    required: true
  },
  labels: [{
    type: String
  }],
  embeddingId: {
    type: String
  },
  summary: {
    type: String
  },
  snippet: {
    type: String
  },
  provider: {
    type: String,
    enum: ['google', 'microsoft'],
    required: true
  }
}, {
  timestamps: true
});

// Indexes for faster queries
emailMetadataSchema.index({ userId: 1, timestamp: -1 });
emailMetadataSchema.index({ tenantId: 1, threadId: 1 });
emailMetadataSchema.index({ messageId: 1 });

module.exports = mongoose.model('EmailMetadata', emailMetadataSchema);
