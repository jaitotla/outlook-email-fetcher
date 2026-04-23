const mongoose = require('mongoose');
const { v4: uuidv4 } = require('uuid');

const tenantSchema = new mongoose.Schema({
  id: {
    type: String,
    default: uuidv4,
    unique: true
  },
  name: {
    type: String,
    required: true
  },
  type: {
    type: String,
    enum: ['enterprise', 'standalone'],
    default: 'standalone'
  },
  domain: {
    type: String,
    lowercase: true,
    trim: true
  },
  settings: {
    llmProvider: {
      type: String,
      enum: ['openai', 'gemini', 'ollama'],
      default: 'openai'
    },
    vectorDb: {
      type: String,
      enum: ['pinecone', 'local'],
      default: 'pinecone'
    }
  },
  active: {
    type: Boolean,
    default: true
  }
}, {
  timestamps: true
});

module.exports = mongoose.model('Tenant', tenantSchema);
