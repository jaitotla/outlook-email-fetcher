const express = require('express');
const router = express.Router();
const { authenticateToken } = require('./auth');
const User = require('../models/User');
const Tenant = require('../models/Tenant');

// ============================================================================
// Add-on Settings Endpoints (user_id based, for Gmail add-on)
// These endpoints are called from the Google Apps Script add-on
// TODO: Add Google ID token verification for production security
// ============================================================================

/**
 * Get user settings by user_id (email)
 * Called from Gmail add-on to sync settings
 * GET /api/settings?user_id=email@example.com
 */
router.get('/', async (req, res) => {
  try {
    const { user_id } = req.query;
    
    // If no user_id, try authenticated route
    if (!user_id && req.headers.authorization) {
      return authenticatedGetSettings(req, res);
    }
    
    if (!user_id) {
      return res.status(400).json({ error: 'user_id required' });
    }
    
    const user = await User.findOne({ email: user_id });
    
    if (!user) {
      // User doesn't exist yet - return defaults
      return res.json({
        settings: getDefaultSettings(),
        source: 'defaults'
      });
    }
    
    // Return full settings (add-on needs them for configuration)
    // API keys are stored encrypted in add-on's UserProperties
    res.json({
      settings: user.settings || getDefaultSettings(),
      source: 'database'
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * Save user settings from add-on
 * POST /api/settings
 * Body: { user_id: "email@example.com", settings: { ... } }
 */
router.post('/', async (req, res) => {
  try {
    const { user_id, settings } = req.body;
    
    if (!user_id) {
      return res.status(400).json({ error: 'user_id required' });
    }
    
    if (!settings) {
      return res.status(400).json({ error: 'settings required' });
    }
    
    // Validate settings structure
    const validatedSettings = validateAndSanitizeSettings(settings);
    
    // Upsert user with settings
    const user = await User.findOneAndUpdate(
      { email: user_id },
      { 
        $set: { settings: validatedSettings },
        $setOnInsert: { 
          email: user_id,
          id: user_id,
          createdAt: new Date()
        }
      },
      { new: true, upsert: true }
    );
    
    res.json({
      success: true,
      settings: user.settings
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get default settings object
 */
function getDefaultSettings() {
  return {
    mode: 'inbuilt',
    llm_provider: 'inbuilt',
    llm_api_key: '',
    llm_model: 'gpt-4o-mini',
    llm_base_url: '',
    embedding_provider: 'inbuilt',
    embedding_api_key: '',
    embedding_model: 'text-embedding-3-small',
    vector_provider: 'inbuilt',
    vector_url: '',
    vector_api_key: '',
    user_name: '',
    user_position: '',
    user_tone: 'professional',
    system_prompt: ''
  };
}

/**
 * Validate and sanitize settings from add-on
 * Prevents injection and ensures valid values
 */
function validateAndSanitizeSettings(settings) {
  const validProviders = {
    llm: ['openai', 'anthropic', 'gemini', 'ollama', 'inbuilt'],
    embedding: ['openai', 'nomic', 'gemini', 'sentence-transformers', 'inbuilt'],
    vector: ['pinecone', 'chroma', 'weaviate', 'inbuilt']
  };
  
  const validTones = ['professional', 'friendly', 'formal', 'casual'];
  const validModes = ['inbuilt', 'custom'];
  
  return {
    mode: validModes.includes(settings.mode) ? settings.mode : 'inbuilt',
    llm_provider: validProviders.llm.includes(settings.llm_provider) ? settings.llm_provider : 'inbuilt',
    llm_api_key: sanitizeApiKey(settings.llm_api_key),
    llm_model: sanitizeString(settings.llm_model, 50) || 'gpt-4o-mini',
    llm_base_url: sanitizeUrl(settings.llm_base_url),
    embedding_provider: validProviders.embedding.includes(settings.embedding_provider) ? settings.embedding_provider : 'inbuilt',
    embedding_api_key: sanitizeApiKey(settings.embedding_api_key),
    embedding_model: sanitizeString(settings.embedding_model, 50) || 'text-embedding-3-small',
    vector_provider: validProviders.vector.includes(settings.vector_provider) ? settings.vector_provider : 'inbuilt',
    vector_url: sanitizeUrl(settings.vector_url),
    vector_api_key: sanitizeApiKey(settings.vector_api_key),
    user_name: sanitizeString(settings.user_name, 100),
    user_position: sanitizeString(settings.user_position, 100),
    user_tone: validTones.includes(settings.user_tone) ? settings.user_tone : 'professional',
    system_prompt: sanitizeString(settings.system_prompt, 2000)
  };
}

function sanitizeString(str, maxLength) {
  if (!str || typeof str !== 'string') return '';
  return str.slice(0, maxLength).trim();
}

function sanitizeApiKey(key) {
  if (!key || typeof key !== 'string') return '';
  // Only allow alphanumeric, dashes, underscores (typical API key chars)
  return key.replace(/[^a-zA-Z0-9\-_]/g, '').slice(0, 200);
}

function sanitizeUrl(url) {
  if (!url || typeof url !== 'string') return '';
  // Basic URL validation
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol)) return '';
    return parsed.href.slice(0, 500);
  } catch {
    return '';
  }
}

// ============================================================================
// Authenticated Settings Endpoints (JWT based, for web frontend)
// ============================================================================

/**
 * Authenticated GET for web frontend
 */
async function authenticatedGetSettings(req, res) {
  try {
    const user = await User.findOne({ id: req.user.userId })
      .select('settings');
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Mask sensitive keys for web display
    const settings = { ...user.settings };
    if (settings.llm_api_key) {
      settings.llm_api_key = '***' + settings.llm_api_key.slice(-4);
    }
    if (settings.embedding_api_key) {
      settings.embedding_api_key = '***' + settings.embedding_api_key.slice(-4);
    }
    if (settings.vector_api_key) {
      settings.vector_api_key = '***' + settings.vector_api_key.slice(-4);
    }
    // Legacy field masking
    if (settings.llmApiKey) {
      settings.llmApiKey = '***' + settings.llmApiKey.slice(-4);
    }
    if (settings.pineconeApiKey) {
      settings.pineconeApiKey = '***' + settings.pineconeApiKey.slice(-4);
    }
    
    res.json(settings);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
}

// Update user settings (authenticated - for web frontend)
router.put('/', authenticateToken, async (req, res) => {
  try {
    const settings = req.body;
    
    // Validate and merge with existing
    const validatedSettings = validateAndSanitizeSettings(settings);
    
    const user = await User.findOneAndUpdate(
      { id: req.user.userId },
      { $set: { settings: validatedSettings } },
      { new: true }
    ).select('settings');
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Mask sensitive keys in response
    const responseSettings = { ...user.settings };
    if (responseSettings.llm_api_key) {
      responseSettings.llm_api_key = '***' + responseSettings.llm_api_key.slice(-4);
    }
    
    res.json(responseSettings);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get tenant settings (admin only)
router.get('/tenant', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (currentUser.role !== 'admin') {
      return res.status(403).json({ error: 'Admin access required' });
    }
    
    const tenant = await Tenant.findOne({ id: currentUser.tenantId })
      .select('settings');
    
    if (!tenant) {
      return res.status(404).json({ error: 'Tenant not found' });
    }
    
    res.json(tenant.settings);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update tenant settings (admin only)
router.put('/tenant', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (currentUser.role !== 'admin') {
      return res.status(403).json({ error: 'Admin access required' });
    }
    
    const { llmProvider, vectorDb } = req.body;
    
    const updateData = {};
    
    if (llmProvider) updateData['settings.llmProvider'] = llmProvider;
    if (vectorDb) updateData['settings.vectorDb'] = vectorDb;
    
    const tenant = await Tenant.findOneAndUpdate(
      { id: currentUser.tenantId },
      updateData,
      { new: true }
    ).select('settings');
    
    if (!tenant) {
      return res.status(404).json({ error: 'Tenant not found' });
    }
    
    res.json(tenant.settings);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
