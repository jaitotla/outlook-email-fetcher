const express = require('express');
const router = express.Router();
const { authenticateToken } = require('./auth');
const User = require('../models/User');
const Tenant = require('../models/Tenant');

// Get all users (admin only)
router.get('/', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (currentUser.role !== 'admin') {
      return res.status(403).json({ error: 'Admin access required' });
    }
    
    const users = await User.find({ tenantId: currentUser.tenantId })
      .select('-googleAccessToken -googleRefreshToken -microsoftAccessToken -microsoftRefreshToken -settings.llmApiKey -settings.pineconeApiKey');
    
    res.json(users);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get user by ID
router.get('/:id', authenticateToken, async (req, res) => {
  try {
    const user = await User.findOne({ id: req.params.id })
      .select('-googleAccessToken -googleRefreshToken -microsoftAccessToken -microsoftRefreshToken -settings.llmApiKey -settings.pineconeApiKey');
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    res.json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update user
router.put('/:id', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    // Only allow users to update themselves or admins to update anyone
    if (currentUser.id !== req.params.id && currentUser.role !== 'admin') {
      return res.status(403).json({ error: 'Unauthorized' });
    }
    
    const { firstName, lastName, dob, country, city } = req.body;
    const user = await User.findOneAndUpdate(
      { id: req.params.id },
      { firstName, lastName, dob, country, city },
      { new: true }
    ).select('-googleAccessToken -googleRefreshToken -microsoftAccessToken -microsoftRefreshToken -settings.llmApiKey -settings.pineconeApiKey');
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    res.json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Delete user (admin only)
router.delete('/:id', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (currentUser.role !== 'admin') {
      return res.status(403).json({ error: 'Admin access required' });
    }
    
    const user = await User.findOneAndUpdate(
      { id: req.params.id },
      { active: false },
      { new: true }
    );
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    res.json({ message: 'User deactivated successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
