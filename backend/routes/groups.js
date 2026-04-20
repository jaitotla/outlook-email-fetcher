const express = require('express');
const router = express.Router();
const { authenticateToken } = require('./auth');
const Group = require('../models/Group');
const User = require('../models/User');

// Get all groups for tenant
router.get('/', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    const groups = await Group.find({ 
      tenantId: currentUser.tenantId,
      active: true 
    }).populate('managerId', 'firstName lastName email');
    
    res.json(groups);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create group (admin/manager only)
router.post('/', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (!['admin', 'manager'].includes(currentUser.role)) {
      return res.status(403).json({ error: 'Admin or manager access required' });
    }
    
    const { name, managerId, members } = req.body;
    
    const group = await Group.create({
      tenantId: currentUser.tenantId,
      name,
      managerId,
      members: members || []
    });
    
    res.status(201).json(group);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get group by ID
router.get('/:id', authenticateToken, async (req, res) => {
  try {
    const group = await Group.findOne({ id: req.params.id })
      .populate('managerId', 'firstName lastName email')
      .populate('members', 'firstName lastName email');
    
    if (!group) {
      return res.status(404).json({ error: 'Group not found' });
    }
    
    res.json(group);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update group
router.put('/:id', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (!['admin', 'manager'].includes(currentUser.role)) {
      return res.status(403).json({ error: 'Admin or manager access required' });
    }
    
    const { name, managerId, members } = req.body;
    
    const group = await Group.findOneAndUpdate(
      { id: req.params.id },
      { name, managerId, members },
      { new: true }
    );
    
    if (!group) {
      return res.status(404).json({ error: 'Group not found' });
    }
    
    res.json(group);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Delete group
router.delete('/:id', authenticateToken, async (req, res) => {
  try {
    const currentUser = await User.findOne({ id: req.user.userId });
    
    if (currentUser.role !== 'admin') {
      return res.status(403).json({ error: 'Admin access required' });
    }
    
    const group = await Group.findOneAndUpdate(
      { id: req.params.id },
      { active: false },
      { new: true }
    );
    
    if (!group) {
      return res.status(404).json({ error: 'Group not found' });
    }
    
    res.json({ message: 'Group deleted successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
