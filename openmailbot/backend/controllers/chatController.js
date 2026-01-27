const axios = require('axios');
const User = require('../models/User');
const EmailMetadata = require('../models/EmailMetadata');

// Agent API URL (Python FastAPI service)
const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

/**
 * Chat with an email thread using RAG pipeline
 * POST /api/chat/thread
 * 
 * Body:
 * {
 *   "user_id": "user@example.com",
 *   "thread_id": "gmail_thread_id",
 *   "question": "What is the main topic?"
 * }
 */
exports.chatWithThread = async (req, res) => {
  try {
    const { user_id, thread_id, question } = req.body;

    // Validation
    if (!user_id || !thread_id || !question) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: user_id, thread_id, question'
      });
    }

    // Optional: Verify user exists
    try {
      const user = await User.findOne({ email: user_id });
      if (!user) {
        return res.status(404).json({
          success: false,
          error: 'User not found'
        });
      }
    } catch (dbError) {
      // Continue anyway if DB check fails
      console.warn('User verification skipped:', dbError.message);
    }

    console.log(`🤖 Chat request - User: ${user_id}, Thread: ${thread_id}, Question: ${question}`);

    // Call Python chat pipeline service
    const response = await axios.post(
      `${AGENT_API_URL}/chat-with-thread`,
      {
        user_id,
        thread_id,
        question
      },
      {
        timeout: 120000 // 2 minutes timeout for RAG processing
      }
    );

    if (!response.data.success) {
      return res.status(500).json({
        success: false,
        error: response.data.error || 'Chat pipeline failed'
      });
    }

    return res.json({
      success: true,
      answer: response.data.answer,
      processing_info: response.data.processing_info || null,
      thread_id,
      user_id
    });

  } catch (error) {
    console.error('❌ Chat error:', error.message);

    // Handle different error types
    if (error.code === 'ECONNREFUSED') {
      return res.status(503).json({
        success: false,
        error: 'Python agent service unavailable. Please ensure the agent is running.',
        details: error.message
      });
    }

    if (error.response?.status === 500) {
      return res.status(500).json({
        success: false,
        error: 'Chat pipeline error',
        details: error.response.data?.error || error.message
      });
    }

    return res.status(500).json({
      success: false,
      error: 'Failed to process chat request',
      details: error.message
    });
  }
};

/**
 * Get chat history for a thread
 * GET /api/chat/thread/:threadId
 */
exports.getThreadChatHistory = async (req, res) => {
  try {
    const { threadId } = req.params;
    const { userId } = req.query;

    if (!threadId || !userId) {
      return res.status(400).json({
        success: false,
        error: 'Missing required parameters: threadId, userId'
      });
    }

    // This can be extended to fetch chat history from database if needed
    return res.json({
      success: true,
      message: 'Chat history feature coming soon',
      threadId,
      userId
    });

  } catch (error) {
    console.error('❌ Get chat history error:', error.message);
    return res.status(500).json({
      success: false,
      error: 'Failed to retrieve chat history',
      details: error.message
    });
  }
};

/**
 * Search within a thread
 * POST /api/chat/search
 * 
 * Body:
 * {
 *   "user_id": "user@example.com",
 *   "thread_id": "gmail_thread_id",
 *   "query": "search query"
 * }
 */
exports.searchThread = async (req, res) => {
  try {
    const { user_id, thread_id, query } = req.body;

    if (!user_id || !thread_id || !query) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: user_id, thread_id, query'
      });
    }

    console.log(`🔍 Search request - User: ${user_id}, Thread: ${thread_id}, Query: ${query}`);

    // For search, we use the same chat pipeline with a reformatted question
    const response = await axios.post(
      `${AGENT_API_URL}/chat-with-thread`,
      {
        user_id,
        thread_id,
        question: `Find and return all information about: ${query}`
      },
      {
        timeout: 60000
      }
    );

    if (!response.data.success) {
      return res.status(500).json({
        success: false,
        error: response.data.error || 'Search failed'
      });
    }

    return res.json({
      success: true,
      results: response.data.answer,
      query,
      thread_id,
      user_id
    });

  } catch (error) {
    console.error('❌ Search error:', error.message);
    return res.status(500).json({
      success: false,
      error: 'Search failed',
      details: error.message
    });
  }
};

/**
 * Health check for chat service
 * GET /api/chat/health
 */
exports.healthCheck = async (req, res) => {
  try {
    const agentHealth = await axios.get(`${AGENT_API_URL}/health`, {
      timeout: 5000
    });

    return res.json({
      success: true,
      status: 'healthy',
      agent_status: agentHealth.data.status,
      agent_url: AGENT_API_URL
    });

  } catch (error) {
    return res.status(503).json({
      success: false,
      status: 'unhealthy',
      error: 'Chat service unavailable',
      agent_url: AGENT_API_URL,
      details: error.message
    });
  }
};
