const express = require('express');
const router = express.Router();
const passport = require('passport');
const slackController = require('../controllers/slackController');
const { isAuthenticated } = require('../middleware/auth');

/**
 * OAuth routes
 */
router.get(
  '/auth',
  isAuthenticated,
  passport.authenticate('slack', {
    scope: [
      'channels:history',
      'channels:read',
      'groups:history',
      'groups:read',
      'im:history',
      'im:read',
      'mpim:history',
      'mpim:read',
      'users:read',
      'users:read.email',
      'files:read',
      'links:read',
      'chat:write',
      'chat:write.public'
    ]
  })
);

router.get(
  '/auth/callback',
  passport.authenticate('slack', { failureRedirect: '/dashboard?error=slack-auth-failed' }),
  slackController.connectWorkspace
);

/**
 * Workspace management routes
 */
router.get('/workspaces', isAuthenticated, slackController.getWorkspaces);

router.get('/workspaces/:workspaceId/channels', isAuthenticated, slackController.getChannels);

router.put('/workspaces/:workspaceId/config', isAuthenticated, slackController.updateSyncConfig);

router.post('/workspaces/:workspaceId/sync', isAuthenticated, slackController.syncWorkspace);

router.delete('/workspaces/:workspaceId', isAuthenticated, slackController.disconnectWorkspace);

/**
 * Data routes (called by Python agent)
 */
router.post('/metadata', slackController.saveMetadata);

/**
 * Query routes
 */
router.get('/conversations', isAuthenticated, slackController.getConversations);

module.exports = router;
