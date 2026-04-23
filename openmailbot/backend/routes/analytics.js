const express = require('express');
const router = express.Router();
const { authenticateToken } = require('./auth');
const User = require('../models/User');
const EmailMetadata = require('../models/EmailMetadata');
const Group = require('../models/Group');

// Get personal analytics
router.get('/personal', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    const { startDate, endDate } = req.query;
    
    const dateFilter = {};
    if (startDate) dateFilter.$gte = new Date(startDate);
    if (endDate) dateFilter.$lte = new Date(endDate);
    
    const query = { 
      userId: currentUser.id,
      tenantId: currentUser.tenantId
    };
    
    if (Object.keys(dateFilter).length > 0) {
      query.timestamp = dateFilter;
    }
    
    // Email volume
    const emailVolume = await EmailMetadata.aggregate([
      { $match: query },
      {
        $group: {
          _id: { $dateToString: { format: '%Y-%m-%d', date: '$timestamp' } },
          sent: { $sum: { $cond: [{ $eq: ['$from', currentUser.email] }, 1, 0] } },
          received: { $sum: { $cond: [{ $ne: ['$from', currentUser.email] }, 1, 0] } }
        }
      },
      { $sort: { _id: 1 } }
    ]);
    
    // Average response time (simplified)
    const avgResponseTime = await EmailMetadata.aggregate([
      { $match: { ...query, from: currentUser.email } },
      {
        $group: {
          _id: null,
          avgTime: { $avg: '$responseTime' }
        }
      }
    ]);
    
    // Top contacts
    const topContacts = await EmailMetadata.aggregate([
      { $match: query },
      {
        $project: {
          contact: {
            $cond: [
              { $eq: ['$from', currentUser.email] },
              { $arrayElemAt: ['$to', 0] },
              '$from'
            ]
          }
        }
      },
      {
        $group: {
          _id: '$contact',
          count: { $sum: 1 }
        }
      },
      { $sort: { count: -1 } },
      { $limit: 10 }
    ]);
    
    // Pending replies
    const pendingReplies = await EmailMetadata.countDocuments({
      ...query,
      from: { $ne: currentUser.email },
      replied: false
    });
    
    res.json({
      emailVolume,
      avgResponseTime: avgResponseTime[0]?.avgTime || 0,
      topContacts,
      pendingReplies
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get group analytics (manager/admin)
router.get('/group/:groupId', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (!['admin', 'manager'].includes(currentUser.role)) {
      return res.status(403).json({ error: 'Manager or admin access required' });
    }
    
    const group = await Group.findOne({ id: req.params.groupId });
    
    if (!group) {
      return res.status(404).json({ error: 'Group not found' });
    }
    
    const { startDate, endDate } = req.query;
    
    const dateFilter = {};
    if (startDate) dateFilter.$gte = new Date(startDate);
    if (endDate) dateFilter.$lte = new Date(endDate);
    
    const query = {
      userId: { $in: group.members },
      tenantId: currentUser.tenantId
    };
    
    if (Object.keys(dateFilter).length > 0) {
      query.timestamp = dateFilter;
    }
    
    // Group email volume
    const emailVolume = await EmailMetadata.aggregate([
      { $match: query },
      {
        $group: {
          _id: { $dateToString: { format: '%Y-%m-%d', date: '$timestamp' } },
          count: { $sum: 1 }
        }
      },
      { $sort: { _id: 1 } }
    ]);
    
    // Average response time by member
    const avgResponseTimeByMember = await EmailMetadata.aggregate([
      { $match: query },
      {
        $group: {
          _id: '$userId',
          avgTime: { $avg: '$responseTime' }
        }
      }
    ]);
    
    // Sentiment trends (placeholder - requires sentiment analysis)
    const sentimentTrends = await EmailMetadata.aggregate([
      { $match: query },
      {
        $group: {
          _id: '$sentiment',
          count: { $sum: 1 }
        }
      }
    ]);
    
    res.json({
      emailVolume,
      avgResponseTimeByMember,
      sentimentTrends
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get company-wide analytics (admin only)
router.get('/company', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (currentUser.role !== 'admin') {
      return res.status(403).json({ error: 'Admin access required' });
    }
    
    const { startDate, endDate } = req.query;
    
    const dateFilter = {};
    if (startDate) dateFilter.$gte = new Date(startDate);
    if (endDate) dateFilter.$lte = new Date(endDate);
    
    const query = { tenantId: currentUser.tenantId };
    
    if (Object.keys(dateFilter).length > 0) {
      query.timestamp = dateFilter;
    }
    
    // Total email volume
    const totalEmailVolume = await EmailMetadata.countDocuments(query);
    
    // Volume by department/group
    const groups = await Group.find({ tenantId: currentUser.tenantId, active: true });
    
    const volumeByGroup = await Promise.all(
      groups.map(async (group) => {
        const count = await EmailMetadata.countDocuments({
          ...query,
          userId: { $in: group.members }
        });
        return {
          groupName: group.name,
          count
        };
      })
    );
    
    // Tone distribution (placeholder)
    const toneDistribution = await EmailMetadata.aggregate([
      { $match: query },
      {
        $group: {
          _id: '$tone',
          count: { $sum: 1 }
        }
      }
    ]);
    
    // Average response time company-wide
    const avgResponseTime = await EmailMetadata.aggregate([
      { $match: query },
      {
        $group: {
          _id: null,
          avgTime: { $avg: '$responseTime' }
        }
      }
    ]);
    
    res.json({
      totalEmailVolume,
      volumeByGroup,
      toneDistribution,
      avgResponseTime: avgResponseTime[0]?.avgTime || 0
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
