/**
 * OpenMailBot - Thunderbird Options/Settings Script
 */

// DOM Elements
const elements = {
  backendUrl: document.getElementById('backendUrl'),
  agentUrl: document.getElementById('agentUrl'),
  userId: document.getElementById('userId'),
  llmProvider: document.getElementById('llmProvider'),
  llmModel: document.getElementById('llmModel'),
  tone: document.getElementById('tone'),
  vectorDb: document.getElementById('vectorDb'),
  embeddingProvider: document.getElementById('embeddingProvider'),
  backendStatus: document.getElementById('backendStatus'),
  agentStatus: document.getElementById('agentStatus'),
  checkConnectionBtn: document.getElementById('checkConnectionBtn'),
  saveBtn: document.getElementById('saveBtn'),
  resetBtn: document.getElementById('resetBtn'),
  message: document.getElementById('message')
};

// Default settings
const defaults = {
  backendUrl: 'http://localhost:5000',
  agentUrl: 'http://localhost:8000',
  userId: '',
  llmProvider: 'openai',
  llmModel: 'gpt-4',
  tone: 'professional',
  vectorDb: 'faiss',
  embeddingProvider: 'openai',
  isConfigured: false
};

// Model options for each provider
const modelOptions = {
  openai: [
    { value: 'gpt-4', label: 'GPT-4' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
  ],
  anthropic: [
    { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
    { value: 'claude-3-haiku', label: 'Claude 3 Haiku' }
  ],
  ollama: [
    { value: 'llama2', label: 'Llama 2' },
    { value: 'mistral', label: 'Mistral' }
  ]
};

// Load settings
async function loadSettings() {
  try {
    const settings = await browser.storage.local.get(Object.keys(defaults));
    
    // Use defaults if not set
    const config = { ...defaults, ...settings };
    
    elements.backendUrl.value = config.backendUrl;
    elements.agentUrl.value = config.agentUrl;
    elements.userId.value = config.userId || '';
    elements.llmProvider.value = config.llmProvider;
    elements.llmModel.value = config.llmModel;
    elements.tone.value = config.tone;
    elements.vectorDb.value = config.vectorDb;
    elements.embeddingProvider.value = config.embeddingProvider;
    
    updateModelOptions(config.llmProvider);
  } catch (error) {
    showMessage('Error loading settings: ' + error.message, 'error');
  }
}

// Update model dropdown based on provider
function updateModelOptions(provider) {
  const options = modelOptions[provider] || modelOptions.openai;
  const currentValue = elements.llmModel.value;
  
  elements.llmModel.innerHTML = options
    .map(opt => `<option value="${opt.value}">${opt.label}</option>`)
    .join('');
  
  // Try to preserve selection if it exists in new options
  if (options.find(opt => opt.value === currentValue)) {
    elements.llmModel.value = currentValue;
  }
}

// Save settings
async function saveSettings() {
  try {
    const settings = {
      backendUrl: elements.backendUrl.value.trim(),
      agentUrl: elements.agentUrl.value.trim(),
      userId: elements.userId.value.trim(),
      llmProvider: elements.llmProvider.value,
      llmModel: elements.llmModel.value,
      tone: elements.tone.value,
      vectorDb: elements.vectorDb.value,
      embeddingProvider: elements.embeddingProvider.value,
      isConfigured: true
    };
    
    await browser.storage.local.set(settings);
    showMessage('Settings saved successfully!', 'success');
  } catch (error) {
    showMessage('Error saving settings: ' + error.message, 'error');
  }
}

// Reset to defaults
async function resetSettings() {
  if (confirm('Are you sure you want to reset all settings to defaults?')) {
    try {
      await browser.storage.local.set(defaults);
      await loadSettings();
      showMessage('Settings reset to defaults', 'success');
    } catch (error) {
      showMessage('Error resetting settings: ' + error.message, 'error');
    }
  }
}

// Check connection status
async function checkConnection() {
  elements.checkConnectionBtn.disabled = true;
  elements.checkConnectionBtn.textContent = 'Checking...';
  
  // Check backend
  updateStatus('backendStatus', 'checking', 'Checking...');
  try {
    const backendResponse = await fetch(elements.backendUrl.value + '/health', {
      method: 'GET',
      timeout: 5000
    });
    
    if (backendResponse.ok) {
      updateStatus('backendStatus', 'connected', 'Connected');
    } else {
      updateStatus('backendStatus', 'disconnected', 'Error: ' + backendResponse.status);
    }
  } catch (error) {
    updateStatus('backendStatus', 'disconnected', 'Disconnected');
  }
  
  // Check agent
  updateStatus('agentStatus', 'checking', 'Checking...');
  try {
    const agentResponse = await fetch(elements.agentUrl.value + '/health', {
      method: 'GET',
      timeout: 5000
    });
    
    if (agentResponse.ok) {
      updateStatus('agentStatus', 'connected', 'Connected');
    } else {
      updateStatus('agentStatus', 'disconnected', 'Error: ' + agentResponse.status);
    }
  } catch (error) {
    updateStatus('agentStatus', 'disconnected', 'Disconnected');
  }
  
  elements.checkConnectionBtn.disabled = false;
  elements.checkConnectionBtn.textContent = 'Test Connection';
}

// Update status indicator
function updateStatus(elementId, className, text) {
  const element = document.getElementById(elementId);
  element.className = 'status-indicator ' + className;
  element.textContent = text;
}

// Show message
function showMessage(text, type) {
  elements.message.textContent = text;
  elements.message.className = 'message ' + type;
  elements.message.classList.remove('hidden');
  
  setTimeout(() => {
    elements.message.classList.add('hidden');
  }, 5000);
}

// Event Listeners
elements.llmProvider.addEventListener('change', (e) => {
  updateModelOptions(e.target.value);
});

elements.saveBtn.addEventListener('click', saveSettings);
elements.resetBtn.addEventListener('click', resetSettings);
elements.checkConnectionBtn.addEventListener('click', checkConnection);

// Initialize
loadSettings();
