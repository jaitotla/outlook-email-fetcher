const express = require('express');
const router = express.Router();
const { authenticateToken } = require('./auth');
const User = require('../models/User');
const Tenant = require('../models/Tenant');

// Get user settings
router.get('/', authenticateToken, async (req, res) => {
  try {
    const user = await User.findOne({ id: req.user.userId })
      .select('settings');
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Mask sensitive keys
    const settings = { ...user.settings };
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
});

// Update user settings
router.put('/', authenticateToken, async (req, res) => {
  try {
    const { llmProvider, vectorDb, tone, llmApiKey, pineconeApiKey, pineconeEnvironment } = req.body;
    
    const updateData = {};
    
    if (llmProvider) updateData['settings.llmProvider'] = llmProvider;
    if (vectorDb) updateData['settings.vectorDb'] = vectorDb;
    if (tone) updateData['settings.tone'] = tone;
    if (llmApiKey) updateData['settings.llmApiKey'] = llmApiKey;
    if (pineconeApiKey) updateData['settings.pineconeApiKey'] = pineconeApiKey;
    if (pineconeEnvironment) updateData['settings.pineconeEnvironment'] = pineconeEnvironment;
    
    const user = await User.findOneAndUpdate(
      { id: req.user.userId },
      updateData,
      { new: true }
    ).select('settings');
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Mask sensitive keys in response
    const settings = { ...user.settings };
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
