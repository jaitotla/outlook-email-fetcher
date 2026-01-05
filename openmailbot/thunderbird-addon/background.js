/**
 * OpenMailBot - Thunderbird Add-on Background Script
 * Handles message processing and API communication
 */

// Configuration
const CONFIG = {
  BACKEND_URL: 'http://localhost:5000',
  AGENT_URL: 'http://localhost:8000'
};

// Initialize extension
browser.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'install') {
    console.log('OpenMailBot installed');
    await initializeSettings();
  }
});

// Initialize default settings
async function initializeSettings() {
  const defaults = {
    llmProvider: 'openai',
    llmModel: 'gpt-4',
    vectorDb: 'faiss',
    embeddingProvider: 'openai',
    tone: 'professional',
    backendUrl: CONFIG.BACKEND_URL,
    agentUrl: CONFIG.AGENT_URL,
    isConfigured: false
  };
  
  await browser.storage.local.set(defaults);
}

// Get settings
async function getSettings() {
  return await browser.storage.local.get([
    'llmProvider',
    'llmModel',
    'vectorDb',
    'embeddingProvider',
    'tone',
    'backendUrl',
    'agentUrl',
    'isConfigured',
    'userId',
    'apiKey'
  ]);
}

// Get current message
async function getCurrentMessage(tabId) {
  try {
    const messageHeader = await browser.messageDisplay.getDisplayedMessage(tabId);
    if (!messageHeader) {
      throw new Error('No message displayed');
    }
    
    const full = await browser.messages.getFull(messageHeader.id);
    return { header: messageHeader, full };
  } catch (error) {
    console.error('Error getting message:', error);
    throw error;
  }
}

// Extract email content
function extractContent(messageFull) {
  let content = '';
  
  if (messageFull.parts) {
    for (const part of messageFull.parts) {
      if (part.contentType === 'text/plain') {
        content = part.body || '';
        break;
      } else if (part.contentType === 'text/html' && !content) {
        // Fallback to HTML if no plain text
        content = part.body || '';
      }
    }
  }
  
  return content || messageFull.body || '';
}

// Summarize email thread
async function summarizeEmail(messageData) {
  const settings = await getSettings();
  
  const payload = {
    subject: messageData.header.subject,
    from: messageData.header.author,
    to: messageData.header.recipients,
    content: extractContent(messageData.full),
    timestamp: new Date(messageData.header.date).toISOString(),
    provider: settings.llmProvider,
    model: settings.llmModel
  };
  
  try {
    const response = await fetch(`${settings.agentUrl}/api/summarize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    return result.summary || 'Unable to generate summary';
  } catch (error) {
    console.error('Summarize error:', error);
    throw new Error('Failed to connect to OpenMailBot agent. Make sure it\'s running on ' + settings.agentUrl);
  }
}

// Generate reply
async function generateReply(messageData, userContext = '') {
  const settings = await getSettings();
  
  const payload = {
    subject: messageData.header.subject,
    from: messageData.header.author,
    to: messageData.header.recipients,
    content: extractContent(messageData.full),
    timestamp: new Date(messageData.header.date).toISOString(),
    context: userContext,
    tone: settings.tone,
    provider: settings.llmProvider,
    model: settings.llmModel
  };
  
  try {
    const response = await fetch(`${settings.agentUrl}/api/generate-reply`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    return result.reply || 'Unable to generate reply';
  } catch (error) {
    console.error('Generate reply error:', error);
    throw new Error('Failed to connect to OpenMailBot agent. Make sure it\'s running on ' + settings.agentUrl);
  }
}

// Find related emails
async function findRelatedEmails(messageData) {
  const settings = await getSettings();
  
  const payload = {
    subject: messageData.header.subject,
    content: extractContent(messageData.full),
    from: messageData.header.author,
    userId: settings.userId || 'default'
  };
  
  try {
    const response = await fetch(`${settings.agentUrl}/api/related-threads`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    return result.related_threads || [];
  } catch (error) {
    console.error('Find related error:', error);
    throw new Error('Failed to connect to OpenMailBot agent');
  }
}

// Analyze sentiment
async function analyzeSentiment(messageData) {
  const settings = await getSettings();
  
  const payload = {
    content: extractContent(messageData.full),
    provider: settings.llmProvider
  };
  
  try {
    const response = await fetch(`${settings.agentUrl}/api/analyze-sentiment`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    return result.sentiment || { label: 'neutral', score: 0.5 };
  } catch (error) {
    console.error('Sentiment analysis error:', error);
    throw new Error('Failed to analyze sentiment');
  }
}

// Handle messages from popup/options
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'summarize') {
    getCurrentMessage(message.tabId)
      .then(summarizeEmail)
      .then(sendResponse)
      .catch(error => sendResponse({ error: error.message }));
    return true; // Async response
  }
  
  if (message.action === 'generateReply') {
    getCurrentMessage(message.tabId)
      .then(data => generateReply(data, message.context))
      .then(sendResponse)
      .catch(error => sendResponse({ error: error.message }));
    return true;
  }
  
  if (message.action === 'findRelated') {
    getCurrentMessage(message.tabId)
      .then(findRelatedEmails)
      .then(sendResponse)
      .catch(error => sendResponse({ error: error.message }));
    return true;
  }
  
  if (message.action === 'analyzeSentiment') {
    getCurrentMessage(message.tabId)
      .then(analyzeSentiment)
      .then(sendResponse)
      .catch(error => sendResponse({ error: error.message }));
    return true;
  }
  
  if (message.action === 'getSettings') {
    getSettings()
      .then(sendResponse)
      .catch(error => sendResponse({ error: error.message }));
    return true;
  }
  
  if (message.action === 'saveSettings') {
    browser.storage.local.set(message.settings)
      .then(() => sendResponse({ success: true }))
      .catch(error => sendResponse({ error: error.message }));
    return true;
  }
});

// Context menu items
browser.menus.create({
  id: "summarize-email",
  title: "Summarize with OpenMailBot",
  contexts: ["message_list"]
});

browser.menus.create({
  id: "generate-reply",
  title: "Generate Reply with OpenMailBot",
  contexts: ["message_list"]
});

browser.menus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "summarize-email") {
    // Open popup or notification with summary
    console.log('Summarize clicked');
  } else if (info.menuItemId === "generate-reply") {
    console.log('Generate reply clicked');
  }
});

console.log('OpenMailBot background script loaded');
