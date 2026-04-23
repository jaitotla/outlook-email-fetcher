const passport = require('passport');
const GoogleStrategy = require('passport-google-oauth20').Strategy;
const MicrosoftStrategy = require('passport-microsoft').Strategy;
const SlackStrategy = require('passport-slack-oauth2').Strategy;
const User = require('../models/User');

// Serialize user for session
passport.serializeUser((user, done) => {
  done(null, user.id);
});

// Deserialize user from session
passport.deserializeUser(async (id, done) => {
  try {
    const user = await User.findById(id);
    done(null, user);
  } catch (error) {
    done(error, null);
  }
});

// Google OAuth Strategy
passport.use(new GoogleStrategy({
  clientID: process.env.GOOGLE_CLIENT_ID,
  clientSecret: process.env.GOOGLE_CLIENT_SECRET,
  callbackURL: process.env.GOOGLE_CALLBACK_URL
}, async (accessToken, refreshToken, profile, done) => {
  try {
    // Check if user exists
    let user = await User.findOne({ email: profile.emails[0].value });
    
    if (user) {
      // Update Google tokens
      user.googleAccessToken = accessToken;
      user.googleRefreshToken = refreshToken;
      await user.save();
    } else {
      // Create new user
      user = await User.create({
        email: profile.emails[0].value,
        firstName: profile.name.givenName,
        lastName: profile.name.familyName,
        googleId: profile.id,
        googleAccessToken: accessToken,
        googleRefreshToken: refreshToken,
        role: 'solo',
        provider: 'google'
      });
    }
    
    return done(null, user);
  } catch (error) {
    return done(error, null);
  }
}));

// Microsoft OAuth Strategy (for Outlook)
passport.use(new MicrosoftStrategy({
  clientID: process.env.MICROSOFT_CLIENT_ID,
  clientSecret: process.env.MICROSOFT_CLIENT_SECRET,
  callbackURL: process.env.MICROSOFT_CALLBACK_URL,
  scope: ['user.read', 'mail.read', 'mail.send']
}, async (accessToken, refreshToken, profile, done) => {
  try {
    // Check if user exists
    let user = await User.findOne({ email: profile.emails[0].value });
    
    if (user) {
      // Update Microsoft tokens
      user.microsoftAccessToken = accessToken;
      user.microsoftRefreshToken = refreshToken;
      await user.save();
    } else {
      // Create new user
      user = await User.create({
        email: profile.emails[0].value,
        firstName: profile.name.givenName,
        lastName: profile.name.familyName,
        microsoftId: profile.id,
        microsoftAccessToken: accessToken,
        microsoftRefreshToken: refreshToken,
        role: 'solo',
        provider: 'microsoft'
      });
    }
    
    return done(null, user);
  } catch (error) {
    return done(error, null);
  }
}));

// Slack OAuth Strategy
passport.use(new SlackStrategy({
  clientID: process.env.SLACK_CLIENT_ID,
  clientSecret: process.env.SLACK_CLIENT_SECRET,
  callbackURL: process.env.SLACK_CALLBACK_URL,
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
  ],
  skipUserProfile: false,
  passReqToCallback: true
}, async (req, accessToken, refreshToken, params, profile, done) => {
  try {
    // User must be authenticated to connect Slack
    if (!req.user) {
      return done(new Error('User must be logged in to connect Slack'), null);
    }

    const user = await User.findById(req.user._id);
    
    if (!user) {
      return done(new Error('User not found'), null);
    }

    // Check if workspace already connected
    const existingWorkspace = user.slackWorkspaces?.find(
      ws => ws.workspaceId === profile.team.id
    );

    if (existingWorkspace) {
      // Update tokens
      existingWorkspace.accessToken = accessToken;
      existingWorkspace.refreshToken = refreshToken;
      existingWorkspace.botToken = params.bot?.token || existingWorkspace.botToken;
      existingWorkspace.lastSyncedAt = new Date();
    } else {
      // Add new workspace
      if (!user.slackWorkspaces) {
        user.slackWorkspaces = [];
      }
      
      user.slackWorkspaces.push({
        workspaceId: profile.team.id,
        workspaceName: profile.team.name,
        accessToken: accessToken,
        refreshToken: refreshToken,
        botToken: params.bot?.token,
        connectedAt: new Date(),
        syncConfig: {
          enabled: true,
          syncDays: 7,
          selectedChannels: [],
          selectedDMs: [],
          includePublicChannels: true,
          includePrivateChannels: false,
          includeDMs: false,
          dmSelection: 'selected',
          autoSync: true,
          syncInterval: 3600
        },
        fileProcessing: {
          processPDFs: true,
          processDocs: true,
          processImages: false,
          maxFileSize: 10485760
        }
      });
    }

    await user.save();
    return done(null, user);
  } catch (error) {
    return done(error, null);
  }
}));

module.exports = passport;
