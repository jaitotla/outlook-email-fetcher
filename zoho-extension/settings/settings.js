/**
 * OpenMailBot - Zoho Mail Extension Settings
 */

// Load saved settings when page loads
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
});

// Handle form submission
document.getElementById('settingsForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  await saveSettings();
});

/**
 * Load settings from storage
 */
async function loadSettings() {
  try {
    const settings = await ZMAIL.storage.get([
      'apiKey',
      'userId',
      'llmProvider',
      'tone',
      'backendUrl',
      'isConfigured'
    ]);
    
    if (settings) {
      document.getElementById('apiKey').value = settings.apiKey || '';
      document.getElementById('userId').value = settings.userId || '';
      document.getElementById('llmProvider').value = settings.llmProvider || 'openai';
      document.getElementById('tone').value = settings.tone || 'professional';
      document.getElementById('backendUrl').value = settings.backendUrl || 'https://api.openmailbot.com';
    }
  } catch (error) {
    console.error('Error loading settings:', error);
    showStatus('Failed to load settings', 'error');
  }
}

/**
 * Save settings to storage
 */
async function saveSettings() {
  try {
    const settings = {
      apiKey: document.getElementById('apiKey').value.trim(),
      userId: document.getElementById('userId').value.trim(),
      llmProvider: document.getElementById('llmProvider').value,
      tone: document.getElementById('tone').value,
      backendUrl: document.getElementById('backendUrl').value.trim(),
      isConfigured: true
    };
    
    // Validate API key
    if (!settings.apiKey) {
      showStatus('API Key is required', 'error');
      return;
    }
    
    // Save to Zoho Mail storage
    await ZMAIL.storage.set(settings);
    
    showStatus('Settings saved successfully! ✓', 'success');
    
    // Reload extension after 1 second
    setTimeout(() => {
      ZMAIL.extension.reload();
    }, 1000);
    
  } catch (error) {
    console.error('Error saving settings:', error);
    showStatus('Failed to save settings: ' + error.message, 'error');
  }
}

/**
 * Show status message
 */
function showStatus(message, type) {
  const statusDiv = document.getElementById('statusMessage');
  statusDiv.textContent = message;
  statusDiv.className = 'status-message ' + type;
  statusDiv.style.display = 'block';
  
  if (type === 'success') {
    setTimeout(() => {
      statusDiv.style.display = 'none';
    }, 3000);
  }
}
