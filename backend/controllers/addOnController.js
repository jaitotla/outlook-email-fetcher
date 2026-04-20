const axios = require('axios');
const EmailMetadata = require('../models/EmailMetadata');
const User = require('../models/User');

// Agent API URL (Python FastAPI service)
const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

// Summarize email thread
exports.summarize = async (req, res) => {
  try {
    const { threadId, userId } = req.body;
    
    if (!threadId || !userId) {
      return res.status(400).json({ error: 'threadId and userId required' });
    }
    
    const user = await User.findOne({ id: userId });
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Get thread emails
    const emails = await EmailMetadata.find({
      threadId,
      userId,
      tenantId: user.tenantId
    }).sort({ timestamp: 1 });
    
    if (emails.length === 0) {
      return res.status(404).json({ error: 'Thread not found' });
    }
    
    // Call Python agent for summarization
    const response = await axios.post(`${AGENT_API_URL}/api/summarize`, {
      emails: emails.map(e => ({
        from: e.from,
        to: e.to,
        subject: e.subject,
        timestamp: e.timestamp,
        content: e.content
      })),
      userId,
      tenantId: user.tenantId
    });
    
    res.json({
      summary: response.data.summary,
      threadId
    });
  } catch (error) {
    console.error('Summarize error:', error);
    res.status(500).json({ error: error.message });
  }
};

// Generate reply
exports.generateReply = async (req, res) => {
  try {
    const { emailId, userId, tone, context } = req.body;
    
    if (!emailId || !userId) {
      return res.status(400).json({ error: 'emailId and userId required' });
    }
    
    const user = await User.findOne({ id: userId });
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    const email = await EmailMetadata.findOne({
      id: emailId,
      userId,
      tenantId: user.tenantId
    });
    
    if (!email) {
      return res.status(404).json({ error: 'Email not found' });
    }
    
    // Get thread context
    const threadEmails = await EmailMetadata.find({
      threadId: email.threadId,
      userId,
      tenantId: user.tenantId
    }).sort({ timestamp: 1 });
    
    // Call Python agent for reply generation
    const response = await axios.post(`${AGENT_API_URL}/api/generate-reply`, {
      email: {
        from: email.from,
        to: email.to,
        subject: email.subject,
        content: email.content
      },
      threadContext: threadEmails.map(e => ({
        from: e.from,
        to: e.to,
        subject: e.subject,
        content: e.content,
        timestamp: e.timestamp
      })),
      tone: tone || user.settings.tone || 'professional',
      additionalContext: context,
      userId,
      tenantId: user.tenantId
    });
    
    res.json({
      reply: response.data.reply,
      emailId
    });
  } catch (error) {
    console.error('Generate reply error:', error);
    res.status(500).json({ error: error.message });
  }
};

// Handle natural language query
exports.handleQuery = async (req, res) => {
  try {
    const { query, userId, emailId } = req.body;
    
    if (!query || !userId) {
      return res.status(400).json({ error: 'query and userId required' });
    }
    
    const user = await User.findOne({ id: userId });
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Optional email context
    let emailContext = null;
    if (emailId) {
      emailContext = await EmailMetadata.findOne({
        id: emailId,
        userId,
        tenantId: user.tenantId
      });
    }
    
    // Call Python agent for RAG query
    const response = await axios.post(`${AGENT_API_URL}/api/rag`, {
      query,
      userId,
      tenantId: user.tenantId,
      emailContext: emailContext ? {
        from: emailContext.from,
        to: emailContext.to,
        subject: emailContext.subject,
        content: emailContext.content,
        timestamp: emailContext.timestamp
      } : null
    });
    
    res.json({
      answer: response.data.answer,
      sources: response.data.sources
    });
  } catch (error) {
    console.error('Query error:', error);
    res.status(500).json({ error: error.message });
  }
};

// Get related threads
exports.getRelatedThreads = async (req, res) => {
  try {
    const { threadId, userId } = req.body;
    
    if (!threadId || !userId) {
      return res.status(400).json({ error: 'threadId and userId required' });
    }
    
    const user = await User.findOne({ id: userId });
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Call Python agent to find related threads using vector similarity
    const response = await axios.post(`${AGENT_API_URL}/api/related-threads`, {
      threadId,
      userId,
      tenantId: user.tenantId
    });
    
    // Get email metadata for related threads
    const relatedThreadIds = response.data.relatedThreadIds || [];
    
    const relatedEmails = await EmailMetadata.find({
      threadId: { $in: relatedThreadIds },
      userId,
      tenantId: user.tenantId
    }).sort({ timestamp: -1 });
    
    // Group by thread
    const threadMap = {};
    relatedEmails.forEach(email => {
      if (!threadMap[email.threadId]) {
        threadMap[email.threadId] = [];
      }
      threadMap[email.threadId].push(email);
    });
    
    res.json({
      relatedThreads: Object.entries(threadMap).map(([tid, emails]) => ({
        threadId: tid,
        subject: emails[0].subject,
        participants: [...new Set(emails.flatMap(e => [e.from, ...e.to]))],
        lastUpdate: emails[0].timestamp,
        emailCount: emails.length
      }))
    });
  } catch (error) {
    console.error('Get related threads error:', error);
    res.status(500).json({ error: error.message });
  }
};
