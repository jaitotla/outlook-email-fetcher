const axios = require('axios');
const User = require('../models/User');

// Agent API URL (Python FastAPI service)
const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

/**
 * Generate email draft with attachments
 * POST /api/draft/with-attachments
 * 
 * Body:
 * {
 *   "user_id": "user@example.com",
 *   "thread_id": "gmail_thread_id",
 *   "user_preferences": {
 *     "name": "John Doe",
 *     "position": "Manager",
 *     "tone": "professional",
 *     "custom_instructions": "Include bullet points"
 *   }
 * }
 */
exports.draftWithAttachments = async (req, res) => {
  try {
    const { user_id, thread_id, user_preferences } = req.body;

    // Validation
    if (!user_id || !thread_id) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: user_id, thread_id'
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

    console.log(`📝 Draft request - User: ${user_id}, Thread: ${thread_id}`);

    // Call Python draft pipeline service
    const response = await axios.post(
      `${AGENT_API_URL}/draft-with-attachments`,
      {
        user_id,
        thread_id,
        user_preferences: user_preferences || {}
      },
      {
        timeout: 180000 // 3 minutes timeout for draft generation
      }
    );

    if (!response.data.success) {
      return res.status(500).json({
        success: false,
        error: response.data.error || 'Draft generation failed'
      });
    }

    return res.json({
      success: true,
      response: response.data.draft_content,
      processing_info: response.data.processing_info || null,
      thread_id,
      user_id
    });

  } catch (error) {
    console.error('❌ Draft error:', error.message);

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
        error: 'Draft generation error',
        details: error.response.data?.error || error.message
      });
    }

    return res.status(500).json({
      success: false,
      error: 'Failed to generate draft',
      details: error.message
    });
  }
};

/**
 * Get draft preferences for a user
 * GET /api/draft/preferences
 */
exports.getDraftPreferences = async (req, res) => {
  try {
    const { userId } = req.query;

    if (!userId) {
      return res.status(400).json({
        success: false,
        error: 'Missing required parameter: userId'
      });
    }

    // Fetch user and return draft preferences
    const user = await User.findOne({ email: userId });

    if (!user) {
      return res.status(404).json({
        success: false,
        error: 'User not found'
      });
    }

    return res.json({
      success: true,
      preferences: {
        name: user.firstName || 'User',
        position: user.position || 'Professional',
        tone: user.draftTone || 'professional and concise',
        custom_instructions: user.customInstructions || ''
      }
    });

  } catch (error) {
    console.error('❌ Get preferences error:', error.message);
    return res.status(500).json({
      success: false,
      error: 'Failed to retrieve preferences',
      details: error.message
    });
  }
};

/**
 * Save draft preferences for a user
 * POST /api/draft/preferences
 */
exports.saveDraftPreferences = async (req, res) => {
  try {
    const { userId, preferences } = req.body;

    if (!userId || !preferences) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: userId, preferences'
      });
    }

    // Update user preferences
    const user = await User.findOneAndUpdate(
      { email: userId },
      {
        firstName: preferences.name,
        position: preferences.position,
        draftTone: preferences.tone,
        customInstructions: preferences.custom_instructions
      },
      { new: true }
    );

    if (!user) {
      return res.status(404).json({
        success: false,
        error: 'User not found'
      });
    }

    return res.json({
      success: true,
      message: 'Draft preferences saved successfully',
      preferences: {
        name: user.firstName,
        position: user.position,
        tone: user.draftTone,
        custom_instructions: user.customInstructions
      }
    });

  } catch (error) {
    console.error('❌ Save preferences error:', error.message);
    return res.status(500).json({
      success: false,
      error: 'Failed to save preferences',
      details: error.message
    });
  }
};

/**
 * Health check for draft service
 * GET /api/draft/health
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
      error: 'Draft service unavailable',
      agent_url: AGENT_API_URL,
      details: error.message
    });
  }
};
