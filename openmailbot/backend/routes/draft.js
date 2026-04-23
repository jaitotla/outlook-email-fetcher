const express = require('express');
const router = express.Router();
const draftController = require('../controllers/draftController');
const auth = require('../middleware/auth');

/**
 * Draft Generation Routes
 * All routes require authentication except health check
 */

// Health check (no auth required)
router.get('/health', draftController.healthCheck);

// Generate draft with attachments (requires authentication)
router.post('/with-attachments', auth, draftController.draftWithAttachments);

// Get user's draft preferences
router.get('/preferences', auth, draftController.getDraftPreferences);

// Save user's draft preferences
router.post('/preferences', auth, draftController.saveDraftPreferences);

module.exports = router;
