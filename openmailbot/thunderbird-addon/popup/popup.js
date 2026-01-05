/**
 * OpenMailBot - Thunderbird Popup Script
 */

// DOM Elements
const elements = {
  loading: document.getElementById('loading'),
  error: document.getElementById('error'),
  errorMessage: document.getElementById('errorMessage'),
  retryBtn: document.getElementById('retryBtn'),
  content: document.getElementById('content'),
  results: document.getElementById('results'),
  resultsTitle: document.getElementById('resultsTitle'),
  resultsContent: document.getElementById('resultsContent'),
  replyContext: document.getElementById('replyContext'),
  contextInput: document.getElementById('contextInput'),
  toneSelect: document.getElementById('toneSelect'),
  
  // Buttons
  summarizeBtn: document.getElementById('summarizeBtn'),
  generateReplyBtn: document.getElementById('generateReplyBtn'),
  findRelatedBtn: document.getElementById('findRelatedBtn'),
  sentimentBtn: document.getElementById('sentimentBtn'),
  generateBtn: document.getElementById('generateBtn'),
  cancelBtn: document.getElementById('cancelBtn'),
  settingsBtn: document.getElementById('settingsBtn')
};

let currentTabId = null;
let currentAction = null;

// Initialize
async function init() {
  try {
    // Get current tab
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    currentTabId = tabs[0].id;
    
    // Load settings and set tone
    const settings = await browser.runtime.sendMessage({ action: 'getSettings' });
    if (settings.tone) {
      elements.toneSelect.value = settings.tone;
    }
    
    // Check if configured
    if (!settings.isConfigured) {
      showWarning('Please configure OpenMailBot in settings first.');
    }
  } catch (error) {
    showError('Failed to initialize: ' + error.message);
  }
}

// Show/Hide UI States
function showLoading(message = 'Processing...') {
  elements.loading.querySelector('p').textContent = message;
  elements.loading.classList.remove('hidden');
  elements.content.classList.add('hidden');
  elements.error.classList.add('hidden');
}

function showError(message) {
  elements.errorMessage.textContent = message;
  elements.error.classList.remove('hidden');
  elements.loading.classList.add('hidden');
  elements.content.classList.add('hidden');
}

function showWarning(message) {
  showResults('⚠️ Notice', message);
}

function showContent() {
  elements.loading.classList.add('hidden');
  elements.error.classList.add('hidden');
  elements.content.classList.remove('hidden');
}

function showResults(title, content) {
  elements.resultsTitle.textContent = title;
  elements.resultsContent.innerHTML = content;
  elements.results.classList.remove('hidden');
  elements.replyContext.classList.add('hidden');
  showContent();
}

function hideResults() {
  elements.results.classList.add('hidden');
}

// Summarize Email
elements.summarizeBtn.addEventListener('click', async () => {
  showLoading('Generating summary...');
  currentAction = 'summarize';
  
  try {
    const response = await browser.runtime.sendMessage({
      action: 'summarize',
      tabId: currentTabId
    });
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    showResults('📝 Email Summary', response);
  } catch (error) {
    showError(error.message);
  }
});

// Generate Reply - Show Context Input
elements.generateReplyBtn.addEventListener('click', () => {
  hideResults();
  elements.replyContext.classList.remove('hidden');
  elements.contextInput.value = '';
  elements.contextInput.focus();
});

// Generate Reply - Execute
elements.generateBtn.addEventListener('click', async () => {
  const context = elements.contextInput.value.trim();
  const tone = elements.toneSelect.value;
  
  // Save tone preference
  await browser.runtime.sendMessage({
    action: 'saveSettings',
    settings: { tone }
  });
  
  showLoading('Generating reply...');
  currentAction = 'generateReply';
  
  try {
    const response = await browser.runtime.sendMessage({
      action: 'generateReply',
      tabId: currentTabId,
      context: context
    });
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    const html = `
      <div style="margin-bottom: 12px;">
        <strong>Generated Reply (${tone}):</strong>
      </div>
      <div style="background: white; padding: 12px; border-radius: 6px; border: 1px solid #ddd;">
        ${response.replace(/\n/g, '<br>')}
      </div>
      <div style="margin-top: 12px; font-size: 12px; color: #666;">
        💡 Copy this text and paste it into your reply
      </div>
    `;
    
    showResults('✍️ AI-Generated Reply', html);
  } catch (error) {
    showError(error.message);
  }
});

// Cancel Reply Generation
elements.cancelBtn.addEventListener('click', () => {
  elements.replyContext.classList.add('hidden');
  showContent();
});

// Find Related Emails
elements.findRelatedBtn.addEventListener('click', async () => {
  showLoading('Finding related emails...');
  currentAction = 'findRelated';
  
  try {
    const response = await browser.runtime.sendMessage({
      action: 'findRelated',
      tabId: currentTabId
    });
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    if (!response || response.length === 0) {
      showResults('🔍 Related Emails', 'No related emails found.');
      return;
    }
    
    const html = `
      <ul class="related-list">
        ${response.map(email => `
          <li class="related-item">
            <strong>${email.subject || 'No Subject'}</strong>
            <small>From: ${email.from || 'Unknown'} | Similarity: ${Math.round(email.score * 100)}%</small>
          </li>
        `).join('')}
      </ul>
    `;
    
    showResults('🔍 Related Emails', html);
  } catch (error) {
    showError(error.message);
  }
});

// Analyze Sentiment
elements.sentimentBtn.addEventListener('click', async () => {
  showLoading('Analyzing sentiment...');
  currentAction = 'analyzeSentiment';
  
  try {
    const response = await browser.runtime.sendMessage({
      action: 'analyzeSentiment',
      tabId: currentTabId
    });
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    const sentimentClass = response.label === 'positive' ? 'sentiment-positive' :
                          response.label === 'negative' ? 'sentiment-negative' :
                          'sentiment-neutral';
    
    const emoji = response.label === 'positive' ? '😊' :
                 response.label === 'negative' ? '😟' :
                 '😐';
    
    const html = `
      <div style="text-align: center; padding: 20px;">
        <div style="font-size: 48px; margin-bottom: 16px;">${emoji}</div>
        <div>
          <span class="sentiment-badge ${sentimentClass}">
            ${response.label.toUpperCase()}
          </span>
        </div>
        <div style="margin-top: 12px; font-size: 14px; color: #666;">
          Confidence: ${Math.round(response.score * 100)}%
        </div>
      </div>
    `;
    
    showResults('😊 Sentiment Analysis', html);
  } catch (error) {
    showError(error.message);
  }
});

// Retry Button
elements.retryBtn.addEventListener('click', () => {
  if (currentAction) {
    elements[currentAction + 'Btn'].click();
  } else {
    init();
  }
});

// Settings Button
elements.settingsBtn.addEventListener('click', () => {
  browser.runtime.openOptionsPage();
});

// Initialize on load
init();
