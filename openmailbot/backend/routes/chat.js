const express = require('express');
const router = express.Router();
const chatController = require('../controllers/chatController');
const auth = require('../middleware/auth');

/**
 * Chat Pipeline Routes
 * All routes require authentication
 */

// Health check (no auth required)
router.get('/health', chatController.healthCheck);

// Chat with thread (requires authentication)
router.post('/thread', auth, chatController.chatWithThread);

// Get chat history for thread
router.get('/thread/:threadId', auth, chatController.getThreadChatHistory);

// Search within thread
router.post('/search', auth, chatController.searchThread);

module.exports = router;
