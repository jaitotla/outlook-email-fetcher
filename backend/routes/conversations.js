const express = require('express');
const router = express.Router();
const ConversationPoint = require('../models/ConversationPoint');
const { isAuthenticated } = require('../middleware/auth');

/**
 * Save a conversation point (called by Python agent)
 */
router.post('/points', async (req, res) => {
  try {
    const conversationPoint = new ConversationPoint(req.body);
    await conversationPoint.save();
    
    res.json({
      success: true,
      id: conversationPoint._id
    });
  } catch (error) {
    console.error('Error saving conversation point:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get conversation points with filters
 */
router.get('/points', isAuthenticated, async (req, res) => {
  try {
    const { streamType, startDate, endDate, topics, actionable } = req.query;
    
    const query = {
      userId: req.user._id
    };
    
    if (streamType) {
      query.streamType = streamType;
    }
    
    if (startDate || endDate) {
      query.date = {};
      if (startDate) query.date.$gte = new Date(startDate);
      if (endDate) query.date.$lte = new Date(endDate);
    }
    
    if (topics) {
      query.topics = { $in: topics.split(',') };
    }
    
    if (actionable === 'true') {
      query['points.actionable'] = true;
    }
    
    const points = await ConversationPoint.find(query)
      .sort({ date: -1 })
      .limit(100);
    
    res.json({ points });
  } catch (error) {
    console.error('Error fetching conversation points:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get conversation points by topic
 */
router.get('/points/by-topic/:topic', isAuthenticated, async (req, res) => {
  try {
    const { topic } = req.params;
    const { streamType } = req.query;
    
    const query = {
      userId: req.user._id,
      topics: topic
    };
    
    if (streamType) {
      query.streamType = streamType;
    }
    
    const points = await ConversationPoint.find(query)
      .sort({ date: -1 })
      .limit(50);
    
    res.json({ points });
  } catch (error) {
    console.error('Error fetching points by topic:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get all topics across streams
 */
router.get('/topics', isAuthenticated, async (req, res) => {
  try {
    const topics = await ConversationPoint.aggregate([
      { $match: { userId: req.user._id } },
      { $unwind: '$topics' },
      { $group: {
        _id: '$topics',
        count: { $sum: 1 },
        streams: { $addToSet: '$streamType' },
        lastSeen: { $max: '$date' }
      }},
      { $sort: { count: -1 } },
      { $limit: 100 }
    ]);
    
    res.json({ topics });
  } catch (error) {
    console.error('Error fetching topics:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
