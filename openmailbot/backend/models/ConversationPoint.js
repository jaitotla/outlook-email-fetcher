const mongoose = require('mongoose');

const conversationPointSchema = new mongoose.Schema({
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
  streamType: {
    type: String,
    enum: ['email', 'slack', 'whatsapp', 'teams'],
    required: true,
    index: true
  },
  date: {
    type: Date,
    required: true,
    index: true
  },
  summary: {
    type: String,
    required: true
  },
  points: [{
    text: String,
    importance: {
      type: String,
      enum: ['high', 'medium', 'low'],
      default: 'medium'
    },
    actionable: {
      type: Boolean,
      default: false
    }
  }],
  topics: [{
    type: String,
    index: true
  }],
  sentiment: {
    overall: {
      type: String,
      enum: ['positive', 'neutral', 'negative', 'mixed']
    },
    score: Number
  },
  participants: [{
    id: String,
    name: String,
    email: String
  }],
  sourceMetadata: {
    // Reference to the actual source document
    metadataId: mongoose.Schema.Types.ObjectId,
    metadataType: String // 'EmailMetadata', 'SlackMetadata', etc.
  },
  embeddings: {
    vectorId: String, // ID in Pinecone/FAISS
    embedded: {
      type: Boolean,
      default: false
    }
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

// Compound indexes for efficient querying
conversationPointSchema.index({ userId: 1, streamType: 1, date: -1 });
conversationPointSchema.index({ tenantId: 1, topics: 1 });
conversationPointSchema.index({ userId: 1, 'embeddings.embedded': 1 });

// Update timestamp on save
conversationPointSchema.pre('save', function(next) {
  this.updatedAt = new Date();
  next();
});

module.exports = mongoose.model('ConversationPoint', conversationPointSchema);
