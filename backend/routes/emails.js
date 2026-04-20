const express = require('express');
const router = express.Router();
const { authenticateToken } = require('./auth');
const EmailMetadata = require('../models/EmailMetadata');
const User = require('../models/User');

// Get user's emails
router.get('/', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    const { page = 1, limit = 50, labels, search, startDate, endDate } = req.query;
    
    const query = {
      userId: currentUser.id,
      tenantId: currentUser.tenantId
    };
    
    if (labels) {
      query.labels = { $in: labels.split(',') };
    }
    
    if (search) {
      query.$or = [
        { subject: { $regex: search, $options: 'i' } },
        { from: { $regex: search, $options: 'i' } },
        { to: { $regex: search, $options: 'i' } }
      ];
    }
    
    if (startDate || endDate) {
      query.timestamp = {};
      if (startDate) query.timestamp.$gte = new Date(startDate);
      if (endDate) query.timestamp.$lte = new Date(endDate);
    }
    
    const emails = await EmailMetadata.find(query)
      .sort({ timestamp: -1 })
      .limit(parseInt(limit))
      .skip((parseInt(page) - 1) * parseInt(limit))
      .select('-embeddingId'); // Don't return embedding IDs
    
    const total = await EmailMetadata.countDocuments(query);
    
    res.json({
      emails,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total,
        pages: Math.ceil(total / parseInt(limit))
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get email by ID
router.get('/:id', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    const email = await EmailMetadata.findOne({
      id: req.params.id,
      userId: currentUser.id,
      tenantId: currentUser.tenantId
    });
    
    if (!email) {
      return res.status(404).json({ error: 'Email not found' });
    }
    
    res.json(email);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get emails by thread ID
router.get('/thread/:threadId', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    const emails = await EmailMetadata.find({
      threadId: req.params.threadId,
      userId: currentUser.id,
      tenantId: currentUser.tenantId
    }).sort({ timestamp: 1 });
    
    res.json(emails);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Mark email as read
router.patch('/:id/read', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    const email = await EmailMetadata.findOneAndUpdate(
      {
        id: req.params.id,
        userId: currentUser.id,
        tenantId: currentUser.tenantId
      },
      { read: true },
      { new: true }
    );
    
    if (!email) {
      return res.status(404).json({ error: 'Email not found' });
    }
    
    res.json(email);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Mark email as replied
router.patch('/:id/replied', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    const email = await EmailMetadata.findOneAndUpdate(
      {
        id: req.params.id,
        userId: currentUser.id,
        tenantId: currentUser.tenantId
      },
      { replied: true },
      { new: true }
    );
    
    if (!email) {
      return res.status(404).json({ error: 'Email not found' });
    }
    
    res.json(email);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Add labels to email
router.patch('/:id/labels', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    const { labels } = req.body;
    
    if (!Array.isArray(labels)) {
      return res.status(400).json({ error: 'Labels must be an array' });
    }
    
    const email = await EmailMetadata.findOneAndUpdate(
      {
        id: req.params.id,
        userId: currentUser.id,
        tenantId: currentUser.tenantId
      },
      { $addToSet: { labels: { $each: labels } } },
      { new: true }
    );
    
    if (!email) {
      return res.status(404).json({ error: 'Email not found' });
    }
    
    res.json(email);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
