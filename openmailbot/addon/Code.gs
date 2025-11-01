/**
 * OpenMailBot Gmail Add-on
 * Conversational AI interface inside Gmail
 */

// Configuration
const BACKEND_API_URL = 'https://api.openmailbot.com'; // Update with your backend URL

/**
 * Runs when the add-on is installed
 */
function onInstall(e) {
  onOpen(e);
}

/**
 * Runs when Gmail is opened
 */
function onOpen(e) {
  // No-op for Gmail add-ons
}

/**
 * Main entry point - triggered when user opens an email
 */
function onGmailMessageOpen(e) {
  const accessToken = e.messageMetadata.accessToken;
  const messageId = e.messageMetadata.messageId;
  
  // Check if user is onboarded
  const userSettings = getUserSettings();
  
  if (!userSettings || !userSettings.onboarded) {
    return buildOnboardingCard();
  }
  
  return buildMainCard(messageId, accessToken);
}

/**
 * Build the main card with AI assistant interface
 */
function buildMainCard(messageId, accessToken) {
  const card = CardService.newCardBuilder();
  const section = CardService.newCardSection();
  
  section.setHeader('🤖 OpenMailBot');
  
  // Quick Actions
  section.addWidget(
    CardService.newButtonSet()
      .addButton(CardService.newTextButton()
        .setText('📝 Summarize Thread')
        .setOnClickAction(CardService.newAction()
          .setFunctionName('summarizeThread')
          .setParameters({messageId: messageId})))
      .addButton(CardService.newTextButton()
        .setText('✍️ Generate Reply')
        .setOnClickAction(CardService.newAction()
          .setFunctionName('generateReply')
          .setParameters({messageId: messageId})))
  );
  
  // Chat Input
  section.addWidget(
    CardService.newTextInput()
      .setFieldName('userQuery')
      .setTitle('Ask about this email')
      .setHint('e.g., "What are the key points?" or "Draft a professional reply"')
      .setMultiline(true)
  );
  
  section.addWidget(
    CardService.newTextButton()
      .setText('Send')
      .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
      .setOnClickAction(CardService.newAction()
        .setFunctionName('handleUserQuery')
        .setParameters({messageId: messageId}))
  );
  
  // Related Threads
  section.addWidget(
    CardService.newTextButton()
      .setText('🔗 Related Threads')
      .setOnClickAction(CardService.newAction()
        .setFunctionName('showRelatedThreads')
        .setParameters({messageId: messageId}))
  );
  
  // Settings
  section.addWidget(
    CardService.newTextButton()
      .setText('⚙️ Settings')
      .setOnClickAction(CardService.newAction()
        .setFunctionName('showSettings'))
  );
  
  card.addSection(section);
  return card.build();
}

/**
 * Build onboarding card
 */
function buildOnboardingCard() {
  const card = CardService.newCardBuilder();
  const section = CardService.newCardSection();
  
  section.setHeader('Welcome to OpenMailBot! 🎉');
  
  section.addWidget(
    CardService.newTextParagraph()
      .setText('Let\'s set up your AI email assistant. This will take about 2 minutes.')
  );
  
  // Step 1: Choose Vector DB
  section.addWidget(
    CardService.newSelectionInput()
      .setType(CardService.SelectionInputType.DROPDOWN)
      .setTitle('Vector Database')
      .setFieldName('vectorDb')
      .addItem('Pinecone (Cloud)', 'pinecone', true)
      .addItem('Local (FAISS)', 'local', false)
  );
  
  // Pinecone API Key (conditional)
  section.addWidget(
    CardService.newTextInput()
      .setFieldName('pineconeApiKey')
      .setTitle('Pinecone API Key (if using Pinecone)')
      .setHint('Enter your Pinecone API key')
  );
  
  // Step 2: Choose LLM
  section.addWidget(
    CardService.newSelectionInput()
      .setType(CardService.SelectionInputType.DROPDOWN)
      .setTitle('Language Model')
      .setFieldName('llmProvider')
      .addItem('OpenAI', 'openai', true)
      .addItem('Google Gemini', 'gemini', false)
      .addItem('Ollama (Local)', 'ollama', false)
  );
  
  // LLM API Key
  section.addWidget(
    CardService.newTextInput()
      .setFieldName('llmApiKey')
      .setTitle('LLM API Key')
      .setHint('Enter your OpenAI or Gemini API key')
  );
  
  // Step 3: Choose Tone
  section.addWidget(
    CardService.newSelectionInput()
      .setType(CardService.SelectionInputType.DROPDOWN)
      .setTitle('Default Tone')
      .setFieldName('tone')
      .addItem('Professional', 'professional', true)
      .addItem('Semi-Professional', 'semi-professional', false)
      .addItem('Casual', 'casual', false)
      .addItem('Personal', 'personal', false)
  );
  
  section.addWidget(
    CardService.newTextButton()
      .setText('Complete Setup')
      .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
      .setOnClickAction(CardService.newAction()
        .setFunctionName('completeOnboarding'))
  );
  
  card.addSection(section);
  return card.build();
}

/**
 * Complete onboarding
 */
function completeOnboarding(e) {
  const formInputs = e.formInput;
  
  const settings = {
    vectorDb: formInputs.vectorDb,
    pineconeApiKey: formInputs.pineconeApiKey || '',
    llmProvider: formInputs.llmProvider,
    llmApiKey: formInputs.llmApiKey,
    tone: formInputs.tone,
    onboarded: true
  };
  
  // Save to backend
  saveUserSettings(settings);
  
  // Show success notification
  const notification = CardService.newNotification()
    .setText('✅ Setup complete! You can now use OpenMailBot.');
  
  return CardService.newActionResponseBuilder()
    .setNotification(notification)
    .setStateChanged(true)
    .build();
}

/**
 * Summarize the current email thread
 */
function summarizeThread(e) {
  const messageId = e.parameters.messageId;
  const accessToken = ScriptApp.getOAuthToken();
  
  try {
    // Get email content
    const emailData = getEmailData(messageId, accessToken);
    
    // Call backend API
    const response = callBackendAPI('/api/summarize', {
      messageId: messageId,
      emailData: emailData
    });
    
    // Show summary
    return showResultCard('Summary', response.summary);
  } catch (error) {
    return showErrorCard('Failed to summarize: ' + error.message);
  }
}

/**
 * Generate a reply to the current email
 */
function generateReply(e) {
  const messageId = e.parameters.messageId;
  const accessToken = ScriptApp.getOAuthToken();
  
  try {
    // Get email content
    const emailData = getEmailData(messageId, accessToken);
    
    // Call backend API
    const response = callBackendAPI('/api/generate-reply', {
      messageId: messageId,
      emailData: emailData
    });
    
    // Show reply draft
    return showReplyCard(response.reply);
  } catch (error) {
    return showErrorCard('Failed to generate reply: ' + error.message);
  }
}

/**
 * Handle user's custom query
 */
function handleUserQuery(e) {
  const messageId = e.parameters.messageId;
  const userQuery = e.formInput.userQuery;
  const accessToken = ScriptApp.getOAuthToken();
  
  if (!userQuery) {
    return showErrorCard('Please enter a question.');
  }
  
  try {
    // Get email content
    const emailData = getEmailData(messageId, accessToken);
    
    // Call backend API
    const response = callBackendAPI('/api/query', {
      messageId: messageId,
      emailData: emailData,
      query: userQuery
    });
    
    // Show answer
    return showResultCard('Answer', response.answer);
  } catch (error) {
    return showErrorCard('Failed to process query: ' + error.message);
  }
}

/**
 * Show related threads
 */
function showRelatedThreads(e) {
  const messageId = e.parameters.messageId;
  
  try {
    const response = callBackendAPI('/api/related-threads', {
      messageId: messageId
    });
    
    const card = CardService.newCardBuilder();
    const section = CardService.newCardSection();
    section.setHeader('Related Threads');
    
    if (response.threads && response.threads.length > 0) {
      response.threads.forEach(thread => {
        section.addWidget(
          CardService.newKeyValue()
            .setTopLabel(thread.subject)
            .setContent(thread.snippet)
        );
      });
    } else {
      section.addWidget(
        CardService.newTextParagraph()
          .setText('No related threads found.')
      );
    }
    
    card.addSection(section);
    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().pushCard(card.build()))
      .build();
  } catch (error) {
    return showErrorCard('Failed to find related threads: ' + error.message);
  }
}

/**
 * Show settings card
 */
function showSettings(e) {
  const settings = getUserSettings();
  
  const card = CardService.newCardBuilder();
  const section = CardService.newCardSection();
  section.setHeader('Settings');
  
  section.addWidget(
    CardService.newSelectionInput()
      .setType(CardService.SelectionInputType.DROPDOWN)
      .setTitle('Vector Database')
      .setFieldName('vectorDb')
      .addItem('Pinecone (Cloud)', 'pinecone', settings.vectorDb === 'pinecone')
      .addItem('Local (FAISS)', 'local', settings.vectorDb === 'local')
  );
  
  section.addWidget(
    CardService.newSelectionInput()
      .setType(CardService.SelectionInputType.DROPDOWN)
      .setTitle('Language Model')
      .setFieldName('llmProvider')
      .addItem('OpenAI', 'openai', settings.llmProvider === 'openai')
      .addItem('Google Gemini', 'gemini', settings.llmProvider === 'gemini')
      .addItem('Ollama (Local)', 'ollama', settings.llmProvider === 'ollama')
  );
  
  section.addWidget(
    CardService.newSelectionInput()
      .setType(CardService.SelectionInputType.DROPDOWN)
      .setTitle('Default Tone')
      .setFieldName('tone')
      .addItem('Professional', 'professional', settings.tone === 'professional')
      .addItem('Semi-Professional', 'semi-professional', settings.tone === 'semi-professional')
      .addItem('Casual', 'casual', settings.tone === 'casual')
      .addItem('Personal', 'personal', settings.tone === 'personal')
  );
  
  section.addWidget(
    CardService.newTextButton()
      .setText('Save Settings')
      .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
      .setOnClickAction(CardService.newAction()
        .setFunctionName('saveSettings'))
  );
  
  card.addSection(section);
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(card.build()))
    .build();
}

/**
 * Save settings
 */
function saveSettings(e) {
  const formInputs = e.formInput;
  
  const settings = getUserSettings();
  settings.vectorDb = formInputs.vectorDb;
  settings.llmProvider = formInputs.llmProvider;
  settings.tone = formInputs.tone;
  
  saveUserSettings(settings);
  
  const notification = CardService.newNotification()
    .setText('✅ Settings saved successfully.');
  
  return CardService.newActionResponseBuilder()
    .setNotification(notification)
    .build();
}

/**
 * Show result card
 */
function showResultCard(title, content) {
  const card = CardService.newCardBuilder();
  const section = CardService.newCardSection();
  section.setHeader(title);
  
  section.addWidget(
    CardService.newTextParagraph()
      .setText(content)
  );
  
  card.addSection(section);
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(card.build()))
    .build();
}

/**
 * Show reply card with option to insert into compose
 */
function showReplyCard(replyText) {
  const card = CardService.newCardBuilder();
  const section = CardService.newCardSection();
  section.setHeader('Generated Reply');
  
  section.addWidget(
    CardService.newTextParagraph()
      .setText(replyText)
  );
  
  section.addWidget(
    CardService.newTextButton()
      .setText('Copy to Clipboard')
      .setOnClickAction(CardService.newAction()
        .setFunctionName('copyToClipboard')
        .setParameters({text: replyText}))
  );
  
  card.addSection(section);
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(card.build()))
    .build();
}

/**
 * Show error card
 */
function showErrorCard(errorMessage) {
  const card = CardService.newCardBuilder();
  const section = CardService.newCardSection();
  section.setHeader('Error');
  
  section.addWidget(
    CardService.newTextParagraph()
      .setText('❌ ' + errorMessage)
  );
  
  card.addSection(section);
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(card.build()))
    .build();
}

/**
 * Get email data from Gmail API
 */
function getEmailData(messageId, accessToken) {
  const url = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${messageId}?format=full`;
  
  const response = UrlFetchApp.fetch(url, {
    headers: {
      Authorization: 'Bearer ' + accessToken
    },
    muteHttpExceptions: true
  });
  
  if (response.getResponseCode() !== 200) {
    throw new Error('Failed to fetch email data');
  }
  
  return JSON.parse(response.getContentText());
}

/**
 * Call backend API
 */
function callBackendAPI(endpoint, payload) {
  const userSettings = getUserSettings();
  const userEmail = Session.getActiveUser().getEmail();
  
  const response = UrlFetchApp.fetch(BACKEND_API_URL + endpoint, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'Authorization': 'Bearer ' + ScriptApp.getOAuthToken(),
      'X-User-Email': userEmail
    },
    payload: JSON.stringify({
      ...payload,
      settings: userSettings
    }),
    muteHttpExceptions: true
  });
  
  if (response.getResponseCode() !== 200) {
    throw new Error('Backend API error: ' + response.getContentText());
  }
  
  return JSON.parse(response.getContentText());
}

/**
 * Get user settings from Properties Service
 */
function getUserSettings() {
  const userProperties = PropertiesService.getUserProperties();
  const settingsJson = userProperties.getProperty('openMailBotSettings');
  
  if (!settingsJson) {
    return null;
  }
  
  return JSON.parse(settingsJson);
}

/**
 * Save user settings to Properties Service
 */
function saveUserSettings(settings) {
  const userProperties = PropertiesService.getUserProperties();
  userProperties.setProperty('openMailBotSettings', JSON.stringify(settings));
  
  // Also save to backend
  try {
    callBackendAPI('/api/settings', settings);
  } catch (error) {
    console.error('Failed to save settings to backend:', error);
  }
}

/**
 * Copy text to clipboard (notification workaround)
 */
function copyToClipboard(e) {
  const notification = CardService.newNotification()
    .setText('💡 Please manually copy the text from the card above.');
  
  return CardService.newActionResponseBuilder()
    .setNotification(notification)
    .build();
}
