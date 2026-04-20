/**
 * OpenMailBot - Zoho Mail Extension
 * Main entry point for the extension
 */

// Configuration
const CONFIG = {
  BACKEND_URL: 'https://api.openmailbot.com',
  AGENT_URL: 'https://agent.openmailbot.com'
};

/**
 * Initialize extension when installed
 */
ZMAIL.extension.onLoad = async function() {
  console.log('OpenMailBot extension loaded');
  
  // Check if user is configured
  const settings = await getSettings();
  if (!settings || !settings.isConfigured) {
    showOnboarding();
  }
};

/**
 * Handle message selection
 */
ZMAIL.extension.onMessageSelect = async function(message) {
  console.log('Message selected:', message.id);
  updateUI(message);
};

/**
 * Update UI with AI assistant interface
 */
async function updateUI(message) {
  const panel = document.getElementById('openmailbot-panel');
  if (!panel) return;
  
  panel.innerHTML = `
    <div class="openmailbot-header">
      <h2>🤖 OpenMailBot</h2>
    </div>
    
    <div class="openmailbot-actions">
      <button onclick="summarizeEmail('${message.id}')" class="btn-primary">
        📝 Summarize Thread
      </button>
      <button onclick="generateReply('${message.id}')" class="btn-primary">
        ✍️ Generate Reply
      </button>
      <button onclick="findRelated('${message.id}')" class="btn-secondary">
        🔗 Find Related
      </button>
      <button onclick="analyzeSentiment('${message.id}')" class="btn-secondary">
        😊 Analyze Sentiment
      </button>
    </div>
    
    <div class="openmailbot-chat">
      <h3>Ask about this email</h3>
      <textarea id="userQuery" placeholder="e.g., What are the action items?"></textarea>
      <button onclick="handleQuery('${message.id}')" class="btn-filled">Send</button>
    </div>
    
    <div id="openmailbot-results" class="openmailbot-results"></div>
  `;
}

/**
 * Get user settings
 */
async function getSettings() {
  try {
    const response = await ZMAIL.storage.get(['apiKey', 'userId', 'llmProvider', 'tone', 'isConfigured']);
    return response;
  } catch (error) {
    console.error('Error getting settings:', error);
    return null;
  }
}

/**
 * Get email data
 */
async function getEmailData(messageId) {
  try {
    const message = await ZMAIL.messages.get(messageId);
    return {
      id: message.id,
      subject: message.subject,
      from: message.from,
      to: message.to,
      cc: message.cc,
      body: message.body,
      date: message.date,
      threadId: message.threadId
    };
  } catch (error) {
    console.error('Error getting email data:', error);
    throw error;
  }
}

/**
 * Call backend API
 */
async function callAPI(endpoint, data) {
  const settings = await getSettings();
  
  try {
    const response = await fetch(CONFIG.AGENT_URL + endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${settings.apiKey}`
      },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
}

/**
 * Summarize email thread
 */
async function summarizeEmail(messageId) {
  showLoading('Generating summary...');
  
  try {
    const emailData = await getEmailData(messageId);
    const response = await callAPI('/api/summarize', {
      messageId: messageId,
      emailData: emailData
    });
    
    showResults('📝 Email Summary', response.summary);
  } catch (error) {
    showError('Failed to summarize: ' + error.message);
  }
}

/**
 * Generate AI reply
 */
async function generateReply(messageId) {
  showLoading('Generating reply...');
  
  try {
    const settings = await getSettings();
    const emailData = await getEmailData(messageId);
    
    const response = await callAPI('/api/generate-reply', {
      messageId: messageId,
      emailData: emailData,
      tone: settings.tone || 'professional'
    });
    
    showReplyOptions(messageId, response.reply);
  } catch (error) {
    showError('Failed to generate reply: ' + error.message);
  }
}

/**
 * Show reply with insert options
 */
function showReplyOptions(messageId, replyText) {
  const resultsDiv = document.getElementById('openmailbot-results');
  
  resultsDiv.innerHTML = `
    <div class="result-card">
      <h3>✍️ AI-Generated Reply</h3>
      <div class="reply-preview">
        ${replyText.replace(/\n/g, '<br>')}
      </div>
      <div class="reply-actions">
        <button onclick="insertReply('${messageId}', 'reply')" class="btn-primary">
          📝 Insert into Reply
        </button>
        <button onclick="insertReply('${messageId}', 'replyAll')" class="btn-primary">
          📝 Insert into Reply All
        </button>
        <button onclick="copyToClipboard(\`${replyText.replace(/`/g, '\\`')}\`)" class="btn-secondary">
          📋 Copy to Clipboard
        </button>
      </div>
      <p class="hint">💡 Click above to insert directly into compose window</p>
    </div>
  `;
}

/**
 * Insert reply into Zoho Mail compose window
 */
async function insertReply(messageId, replyType) {
  showLoading('Opening compose window...');
  
  try {
    // Get the AI-generated reply text
    const replyText = document.querySelector('.reply-preview').innerText;
    const emailData = await getEmailData(messageId);
    
    // Create compose options
    const composeOptions = {
      type: replyType,  // 'reply' or 'replyAll'
      messageId: messageId,
      subject: 'Re: ' + emailData.subject,
      body: replyText,
      format: 'html'
    };
    
    // Open compose window with pre-filled content
    await ZMAIL.composer.open(composeOptions);
    
    showResults('✅ Success', 'Reply inserted into compose window! You can now review and send.');
  } catch (error) {
    showError('Failed to insert reply: ' + error.message);
  }
}

/**
 * Find related emails
 */
async function findRelated(messageId) {
  showLoading('Finding related emails...');
  
  try {
    const emailData = await getEmailData(messageId);
    const response = await callAPI('/api/related-threads', {
      messageId: messageId,
      subject: emailData.subject,
      from: emailData.from
    });
    
    if (!response.threads || response.threads.length === 0) {
      showResults('🔗 Related Emails', 'No related emails found.');
      return;
    }
    
    const html = `
      <ul class="related-list">
        ${response.threads.map(thread => `
          <li class="related-item">
            <strong>${thread.subject}</strong>
            <small>From: ${thread.from} | Similarity: ${Math.round(thread.score * 100)}%</small>
          </li>
        `).join('')}
      </ul>
    `;
    
    showResults('🔗 Related Emails', html);
  } catch (error) {
    showError('Failed to find related emails: ' + error.message);
  }
}

/**
 * Analyze sentiment
 */
async function analyzeSentiment(messageId) {
  showLoading('Analyzing sentiment...');
  
  try {
    const emailData = await getEmailData(messageId);
    const response = await callAPI('/api/analyze-sentiment', {
      content: emailData.body
    });
    
    const emoji = response.label === 'positive' ? '😊' :
                 response.label === 'negative' ? '😟' : '😐';
    
    const html = `
      <div class="sentiment-result">
        <div class="sentiment-emoji">${emoji}</div>
        <div class="sentiment-label">${response.label.toUpperCase()}</div>
        <div class="sentiment-score">Confidence: ${Math.round(response.score * 100)}%</div>
      </div>
    `;
    
    showResults('😊 Sentiment Analysis', html);
  } catch (error) {
    showError('Failed to analyze sentiment: ' + error.message);
  }
}

/**
 * Handle user query
 */
async function handleQuery(messageId) {
  const query = document.getElementById('userQuery').value.trim();
  if (!query) {
    showError('Please enter a question.');
    return;
  }
  
  showLoading('Processing your question...');
  
  try {
    const emailData = await getEmailData(messageId);
    const response = await callAPI('/api/query', {
      messageId: messageId,
      emailData: emailData,
      query: query
    });
    
    showResults('💬 Answer', response.answer);
    document.getElementById('userQuery').value = '';
  } catch (error) {
    showError('Failed to process query: ' + error.message);
  }
}

/**
 * UI Helper functions
 */
function showLoading(message) {
  const resultsDiv = document.getElementById('openmailbot-results');
  resultsDiv.innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      <p>${message}</p>
    </div>
  `;
}

function showResults(title, content) {
  const resultsDiv = document.getElementById('openmailbot-results');
  resultsDiv.innerHTML = `
    <div class="result-card">
      <h3>${title}</h3>
      <div class="result-content">${content}</div>
    </div>
  `;
}

function showError(message) {
  const resultsDiv = document.getElementById('openmailbot-results');
  resultsDiv.innerHTML = `
    <div class="error-card">
      <p>❌ ${message}</p>
    </div>
  `;
}

function showOnboarding() {
  const panel = document.getElementById('openmailbot-panel');
  panel.innerHTML = `
    <div class="onboarding">
      <h2>Welcome to OpenMailBot! 🤖</h2>
      <p>Please configure your settings to get started.</p>
      <button onclick="openSettings()" class="btn-primary">Configure Settings</button>
    </div>
  `;
}

function openSettings() {
  ZMAIL.extension.openSettings();
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showResults('✅ Copied', 'Reply text copied to clipboard!');
  }).catch(err => {
    showError('Failed to copy: ' + err.message);
  });
}

// Export functions for Zoho Mail extension API
window.openmailbot = {
  summarizeEmail,
  generateReply,
  insertReply,
  findRelated,
  analyzeSentiment,
  handleQuery
};
