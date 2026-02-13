/**
 * UNIFIED EMAIL MONITOR - Single Script Solution
 * Runs every 1 minute to capture ALL new emails and attachments
 * 
 * SETUP INSTRUCTIONS:
 * 1. Copy this entire script to your Google Apps Script project
 * 2. Set your FLASK_SERVER_URL in Script Properties
 * 3. Run setupEmailMonitor() ONCE
 * 4. Done! Script will automatically run every minute in the background
 * 
 * FEATURES:
 * - Captures emails in real-time (checks every 1 minute)
 * - Processes allowed attachments: .pdf, .csv, .pptx, .ppt
 * - Tracks processed emails to avoid duplicates
 * - Automatic error recovery
 * - Runs completely in background after setup
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

var CONFIG = {
  // File type filtering
  ALLOWED_EXTENSIONS: ['.pdf', '.csv', '.pptx', '.ppt'],
  
  // How often to check for new emails (in minutes)
  CHECK_INTERVAL_MINUTES: 1,
  
  // Maximum attachments to process per run (safety limit)
  MAX_ATTACHMENTS_PER_RUN: 50,
  
  // Property keys for tracking
  LAST_CHECK_TIME: "last_email_check_time",
  PROCESSED_MESSAGE_IDS: "processed_message_ids",
  
  // NOTE: Label colors are now handled in the main Gmail add-on script
  // Background monitor just applies existing labels without color logic
};

// ============================================================================
// MAIN MONITORING FUNCTION (Runs every 1 minute)
// ============================================================================

/**
 * UPDATED monitorEmails - Logs appear instantly
 * Replace your entire monitorEmails() function with this
 */
function monitorEmails() {
  var startTime = new Date();
  
  try {
    console.log("=== EMAIL MONITOR START ===");
    console.log("Time: " + startTime.toISOString());
    
    // Check server URL
    var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
    if (!flaskUrl) {
      console.log("❌ ERROR: FLASK_SERVER_URL not configured!");
      return;
    }
    console.log("✓ Server URL: " + flaskUrl.substring(0, 50) + "...");
    
    // Get last check time
    var lastCheckTime = getLastCheckTime();
    var now = new Date();
    console.log("✓ Last check: " + lastCheckTime.toISOString());
    console.log("✓ Current time: " + now.toISOString());
    
    // Get domain filters
    var filters = getDomainFilters();
    console.log("✓ Domain filters: " + filters.length);
    
    // Search for new emails
    console.log("");
    console.log("--- SEARCHING FOR NEW EMAILS ---");
    var newMessages = getNewEmailsSince(lastCheckTime);
    console.log("Found: " + newMessages.length + " new message(s)");
    
    if (newMessages.length === 0) {
      console.log("ℹ️  No new emails");
      updateLastCheckTime(now);
      console.log("=== COMPLETE (no emails) ===");
      return;
    }
    
    // Process stats
    var stats = {
      processed: 0,
      skipped: 0,
      filtered: 0,
      emailsSent: 0,
      attachmentsSent: 0,
      labelsApplied: 0,
      errors: 0
    };
    
    console.log("");
    console.log("--- PROCESSING MESSAGES ---");
    
    // Process each message
    for (var i = 0; i < newMessages.length; i++) {
      var message = newMessages[i];
      
      console.log("");
      console.log("Message " + (i + 1) + "/" + newMessages.length + ":");
      console.log("  Subject: " + message.getSubject());
      console.log("  From: " + message.getFrom());
      
      // Skip if already processed
      if (isMessageProcessed(message.getId())) {
        console.log("  ⊘ SKIPPED (already processed)");
        stats.skipped++;
        continue;
      }
      
      // Apply domain filter
      if (shouldFilterMessage(message)) {
        console.log("  🚫 FILTERED (domain exclusion)");
        stats.filtered++;
        markMessageProcessed(message.getId());
        continue;
      }
      
      // Process this message
      try {
        console.log("  → Processing...");
        
        var threadId = message.getThread().getId();
        
        // Send email to server for labeling
        try {
          var label = sendEmailToServer(threadId, message);
          stats.emailsSent++;
          if (label) {
            stats.labelsApplied++;
            console.log("  ✓ Email labeled: " + label);
          } else {
            console.log("  ✓ Email sent (no label assigned)");
          }
        } catch (emailError) {
          console.log("  ⚠️  Email send failed: " + emailError.message);
        }
        
        // Process attachments
        var attachments = message.getAttachments ? message.getAttachments() : [];
        console.log("  Attachments found: " + attachments.length);
        
        if (attachments.length > 0) {
          var allowedAtts = filterAllowedAttachments(attachments);
          console.log("  Allowed attachments: " + allowedAtts.length);
          
          if (allowedAtts.length > 0) {
            try {
              sendAttachmentsToServer(threadId, message, allowedAtts);
              stats.attachmentsSent += allowedAtts.length;
              console.log("  ✓ Uploaded " + allowedAtts.length + " attachment(s)");
            } catch (attError) {
              console.log("  ❌ Attachment upload failed: " + attError.message);
            }
          }
        }
        
        stats.processed++;
        markMessageProcessed(message.getId());
        console.log("  ✅ SUCCESS");
        
      } catch (msgError) {
        console.log("  ❌ ERROR: " + msgError.message);
        stats.errors++;
      }
    }
    
    // Update last check time
    updateLastCheckTime(now);
    
    // Summary
    var duration = (new Date() - startTime) / 1000;
    console.log("");
    console.log("=== SUMMARY ===");
    console.log("Total found: " + newMessages.length);
    console.log("Processed: " + stats.processed);
    console.log("Skipped: " + stats.skipped);
    console.log("Filtered: " + stats.filtered);
    console.log("Emails sent: " + stats.emailsSent);
    console.log("Labels applied: " + stats.labelsApplied);
    console.log("Attachments sent: " + stats.attachmentsSent);
    console.log("Errors: " + stats.errors);
    console.log("Duration: " + duration + "s");
    console.log("=== COMPLETE ===");;
    
  } catch (error) {
    console.log("");
    console.log("❌❌❌ CRITICAL ERROR ❌❌❌");
    console.log("Error: " + error.message);
    console.log("Stack: " + error.stack);
    
    // Update time to prevent loop
    try {
      updateLastCheckTime(new Date());
    } catch (e) {
      console.log("Failed to update time: " + e.message);
    }
  }
}

// ============================================================================
// UPDATED PROCESS MESSAGE WITH DETAILED LOGGING
// Replace your existing processMessage() function with this
// ============================================================================

/**
 * Process a single email message with detailed logging
 * Returns object with processing results
 */
function processMessageWithLogging(message, executionLog) {
  var messageId = message.getId();
  var thread = message.getThread();
  var threadId = thread.getId();
  
  var result = {
    emailSent: false,
    attachmentsSent: 0
  };
  
  executionLog.push("     Thread ID: " + threadId);
  
  // Step 1: Send email data to server
  try {
    executionLog.push("     → Sending email data to server...");
    sendEmailToServer(threadId, message);
    result.emailSent = true;
    executionLog.push("     ✓ Email data sent successfully");
  } catch (emailError) {
    executionLog.push("     ⚠️  Email send failed: " + emailError.message);
    // Continue to try attachments anyway
  }
  
  // Step 2: Process attachments
  var attachments = message.getAttachments ? message.getAttachments() : [];
  executionLog.push("     → Checking attachments...");
  executionLog.push("     Total blobs found: " + attachments.length);
  
  if (attachments.length === 0) {
    executionLog.push("     ℹ️  No attachments to process");
    return result;
  }
  
  // Filter allowed attachments
  var allowedAttachments = filterAllowedAttachmentsWithLogging(attachments, executionLog);
  
  if (allowedAttachments.length === 0) {
    executionLog.push("     ℹ️  No allowed attachments (all filtered)");
    return result;
  }
  
  executionLog.push("     → Allowed attachments: " + allowedAttachments.length);
  
  // Send attachments to server
  try {
    executionLog.push("     → Uploading attachments to server...");
    sendAttachmentsToServer(threadId, message, allowedAttachments);
    result.attachmentsSent = allowedAttachments.length;
    executionLog.push("     ✓ " + allowedAttachments.length + " attachment(s) uploaded");
  } catch (attError) {
    executionLog.push("     ❌ Attachment upload failed: " + attError.message);
    throw attError; // Re-throw to be caught by caller
  }
  
  return result;
}


// ============================================================================
// MESSAGE PROCESSING
// ============================================================================

/**
 * Process a single email message and its attachments
 * UPDATED: Apply domain filtering BEFORE processing
 * Returns statistics object
 */
function processMessage(message) {
  var messageId = message.getId();
  var thread = message.getThread();
  var threadId = thread.getId();
  
  // ⚠️ APPLY DOMAIN FILTER FIRST (ONLY IN BACKGROUND MONITOR)
  if (shouldFilterMessage(message)) {
    Logger.log("🚫 Message filtered - all participants from excluded domains");
    Logger.log("   Subject: " + message.getSubject());
    Logger.log("   From: " + message.getFrom());
    return { attachmentsSent: 0 }; // Skip this message completely
  }
  
  Logger.log("📧 Processing:");
  Logger.log("   Subject: " + message.getSubject());
  Logger.log("   From: " + message.getFrom());
  Logger.log("   Date: " + message.getDate());
  
  var stats = {
    attachmentsSent: 0,
    label: null
  };
  
  // Step 1: Send email data to server for labeling
  try {
    var label = sendEmailToServer(threadId, message);
    stats.label = label;
    Logger.log("   ✓ Email labeled: " + label);
  } catch (emailError) {
    Logger.log("   ⚠️ Failed to label email: " + emailError.message);
    // Continue to try attachments anyway
  }
  
  // Step 2: Process attachments
  var attachments = message.getAttachments ? message.getAttachments() : [];
  
  if (attachments.length === 0) {
    Logger.log("   No attachments");
    return stats;
  }
  
  Logger.log("   Found " + attachments.length + " attachment(s)");
  
  // Filter allowed attachments
  var allowedAttachments = filterAllowedAttachments(attachments);
  
  if (allowedAttachments.length === 0) {
    Logger.log("   All attachments filtered out");
    return stats;
  }
  
  Logger.log("   " + allowedAttachments.length + " allowed attachment(s)");
  
  // Send attachments to server
  try {
    sendAttachmentsToServer(threadId, message, allowedAttachments);
    stats.attachmentsSent = allowedAttachments.length;
    Logger.log("   ✓ " + allowedAttachments.length + " attachment(s) sent");
  } catch (attError) {
    Logger.log("   ⚠️ Failed to send attachments: " + attError.message);
  }
  
  return stats;
}

/**
 * Apply a label to Gmail thread
 * SIMPLIFIED: Just finds existing label and applies it (no creation or color logic)
 */
function applyLabelToThread(threadId, labelName) {
  if (!labelName || labelName.trim().length === 0) {
    return; // Skip empty labels
  }
  
  var thread = GmailApp.getThreadById(threadId);
  if (!thread) {
    Logger.log("⚠️ Thread not found: " + threadId);
    return;
  }
  
  // Find existing label (formatted for Gmail display)
  var formattedName = labelName.charAt(0).toUpperCase() + labelName.slice(1).toLowerCase();
  var label = findExistingLabel(formattedName);
  
  if (label) {
    thread.addLabel(label);
    Logger.log("✅ Applied existing label '" + formattedName + "' to thread");
  } else {
    Logger.log("⚠️ Label '" + formattedName + "' not found - may need to open Gmail add-on to create labels");
  }
}

/**
 * Find existing label by name (no creation)
 * SIMPLIFIED: Background monitor only finds existing labels
 */
function findExistingLabel(labelName) {
  if (!labelName || labelName.trim().length === 0) {
    return null;
  }
  
  try {
    var labels = GmailApp.getUserLabels();
    for (var i = 0; i < labels.length; i++) {
      if (labels[i].getName().toLowerCase() === labelName.toLowerCase()) {
        return labels[i];
      }
    }
    return null; // Not found
  } catch (error) {
    Logger.log("⚠️ Error finding label '" + labelName + "': " + error.message);
    return null;
  }
}

// REMOVED: Color logic moved to main script
// Background monitor no longer handles colors - just applies existing labels

/**
 * Filter attachments by allowed file extensions with logging
 */
function filterAllowedAttachmentsWithLogging(attachments, executionLog) {
  var allowed = [];
  
  for (var i = 0; i < attachments.length; i++) {
    var att = attachments[i];
    
    // Skip inline attachments (images in email body)
    if (att.isInline && att.isInline()) {
      executionLog.push("        ⊘ " + (att.getName ? att.getName() : "unnamed") + " (inline, skipped)");
      continue;
    }
    
    var filename = att.getName ? att.getName() : "";
    var lowerName = filename.toLowerCase();
    
    // Check if file has allowed extension
    var isAllowed = false;
    for (var j = 0; j < CONFIG.ALLOWED_EXTENSIONS.length; j++) {
      var ext = CONFIG.ALLOWED_EXTENSIONS[j];
      var extIndex = lowerName.lastIndexOf(ext);
      if (extIndex !== -1 && extIndex === lowerName.length - ext.length) {
        isAllowed = true;
        break;
      }
    }
    
    if (isAllowed) {
      allowed.push(att);
      var sizeKB = Math.round((att.getBytes ? att.getBytes().length : 0) / 1024);
      executionLog.push("        ✓ " + filename + " (" + sizeKB + " KB)");
    } else {
      executionLog.push("        ⊘ " + filename + " (file type not allowed)");
    }
  }
  
  return allowed;
}


/**
 * Display recent monitor execution logs
 * @param {number} count - Number of recent executions to show (default: 5)
 */
function viewRecentLogs(count) {
  count = count || 5;
  
  try {
    var logSheetId = PropertiesService.getScriptProperties().getProperty("LOG_SHEET_ID");
    if (!logSheetId) {
      Logger.log("No logs found. The monitor hasn't created a log sheet yet.");
      return;
    }
    
    var ss = SpreadsheetApp.openById(logSheetId);
    var sheet = ss.getSheetByName("Monitor Logs");
    
    if (!sheet) {
      Logger.log("No log sheet found.");
      return;
    }
    
    var lastRow = sheet.getLastRow();
    if (lastRow <= 1) {
      Logger.log("No execution logs yet.");
      return;
    }
    
    Logger.log("=== RECENT MONITOR EXECUTIONS ===");
    Logger.log("Sheet URL: " + ss.getUrl());
    Logger.log("");
    
    // Get all data
    var data = sheet.getDataRange().getValues();
    
    // Group by timestamp (find execution boundaries)
    var executions = [];
    var currentExecution = [];
    var currentTimestamp = null;
    
    for (var i = data.length - 1; i >= 1; i--) {
      var row = data[i];
      var timestamp = row[0];
      var logEntry = row[1];
      
      if (logEntry.indexOf("=== EMAIL MONITOR EXECUTION START ===") !== -1) {
        if (currentExecution.length > 0) {
          executions.push({
            timestamp: currentTimestamp,
            logs: currentExecution.reverse()
          });
          currentExecution = [];
        }
        currentTimestamp = timestamp;
      }
      
      currentExecution.push(logEntry);
      
      if (executions.length >= count) {
        break;
      }
    }
    
    // Add last execution if exists
    if (currentExecution.length > 0 && executions.length < count) {
      executions.push({
        timestamp: currentTimestamp,
        logs: currentExecution.reverse()
      });
    }
    
    // Display executions
    executions.reverse();
    for (var i = 0; i < executions.length; i++) {
      Logger.log("EXECUTION " + (i + 1) + " - " + executions[i].timestamp);
      Logger.log("─".repeat(60));
      Logger.log(executions[i].logs.join("\n"));
      Logger.log("");
    }
    
  } catch (error) {
    Logger.log("Error viewing logs: " + error.message);
  }
}
// ============================================================================
// SERVER COMMUNICATION
// ============================================================================

/**
 * Send email data to Flask server for labeling
 * Returns the label assigned to the email
 */
function sendEmailToServer(threadId, message) {
  var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  if (!flaskUrl) {
    throw new Error("FLASK_SERVER_URL not configured in Script Properties");
  }
  
  var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var endpoint = baseUrl + '/api/label-email';
  
  var userId = Session.getEffectiveUser().getEmail();
  
  var emailData = {
    message_id: message.getId(),
    from_address: message.getFrom(),
    to: message.getTo().split(',').map(function(e) { return e.trim(); }),
    subject: message.getSubject(),
    timestamp: message.getDate().toISOString(),
    body: message.getPlainBody ? message.getPlainBody() : (message.getBody ? message.getBody() : "")
  };
  
  var payload = {
    user_id: userId,
    thread_id: threadId,
    messages: [emailData]
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  var resp = UrlFetchApp.fetch(endpoint, options);
  var responseCode = resp.getResponseCode();
  
  if (responseCode !== 200) {
    throw new Error("Server returned " + responseCode + ": " + resp.getContentText());
  }
  
  // Parse response and extract label
  var responseData = JSON.parse(resp.getContentText());
  var label = responseData.label;
  
  // Apply label to the thread
  if (label) {
    try {
      applyLabelToThread(threadId, label);
    } catch (labelError) {
      Logger.log("⚠️ Failed to apply label: " + labelError.message);
      // Don't throw - labeling failure shouldn't block the process
    }
  }
  
  return label;
}

/**
 * Send attachments to Flask server
 */
function sendAttachmentsToServer(threadId, message, attachmentBlobs) {
  var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  if (!flaskUrl) {
    throw new Error("FLASK_SERVER_URL not configured in Script Properties");
  }
  
  var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var endpoint = baseUrl + '/api/store-attachments';
  
  var messageId = message.getId();
  var userId = Session.getEffectiveUser().getEmail();
  
  // Convert blobs to base64
  var attachments = attachmentBlobs.map(function(blob) {
    return {
      filename: blob.getName ? blob.getName() : "attachment",
      content: Utilities.base64Encode(blob.getBytes ? blob.getBytes() : blob.getBytes()),
      mime_type: blob.getContentType ? blob.getContentType() : "application/octet-stream"
    };
  });
  
  var payload = {
    user_id: userId,
    thread_id: threadId,
    message_id: messageId,
    attachments: attachments
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  var resp = UrlFetchApp.fetch(endpoint, options);
  var responseCode = resp.getResponseCode();
  
  if (responseCode !== 200) {
    throw new Error("Server returned " + responseCode + ": " + resp.getContentText());
  }
}

// ============================================================================
// EMAIL RETRIEVAL
// ============================================================================

/**
 * Get new emails since last check time
 */
function getNewEmailsSince(lastCheckTime) {
  try {
    // Add 10 second buffer to avoid missing emails due to timing
    var searchTime = new Date(lastCheckTime.getTime() - 10000);
    
    // Format date for Gmail search
    var dateStr = Utilities.formatDate(searchTime, Session.getScriptTimeZone(), "yyyy/MM/dd");
    
    // Search for emails after this date
    var query = "after:" + dateStr;
    
    var threads = GmailApp.search(query, 0, 100); // Max 100 threads
    
    // Get all messages from threads
    var allMessages = [];
    
    for (var i = 0; i < threads.length; i++) {
      var messages = threads[i].getMessages();
      
      // Only include messages newer than lastCheckTime
      for (var j = 0; j < messages.length; j++) {
        var msgDate = messages[j].getDate();
        if (msgDate > lastCheckTime) {
          allMessages.push(messages[j]);
        }
      }
    }
    
    // Sort by date (newest first)
    allMessages.sort(function(a, b) {
      return b.getDate().getTime() - a.getDate().getTime();
    });
    
    return allMessages;
    
  } catch (error) {
    Logger.log("Error searching Gmail: " + error.message);
    return [];
  }
}

// ============================================================================
// TRACKING AND PERSISTENCE
// ============================================================================

/**
 * Get last check time from properties
 */
function getLastCheckTime() {
  var props = PropertiesService.getScriptProperties();
  var timeStr = props.getProperty(CONFIG.LAST_CHECK_TIME);
  
  if (!timeStr) {
    // First run - start from 5 minutes ago
    var defaultTime = new Date(Date.now() - (5 * 60 * 1000));
    return defaultTime;
  }
  
  try {
    return new Date(timeStr);
  } catch (e) {
    Logger.log("Failed to parse last check time: " + e.message);
    return new Date(Date.now() - (5 * 60 * 1000));
  }
}

/**
 * Update last check time
 */
function updateLastCheckTime(time) {
  var props = PropertiesService.getScriptProperties();
  props.setProperty(CONFIG.LAST_CHECK_TIME, time.toISOString());
}

/**
 * Check if message was already processed
 */
function isMessageProcessed(messageId) {
  var processedIds = getProcessedMessageIds();
  return processedIds.indexOf(messageId) !== -1;
}

/**
 * Get list of processed message IDs
 */
function getProcessedMessageIds() {
  var props = PropertiesService.getScriptProperties();
  var processedJson = props.getProperty(CONFIG.PROCESSED_MESSAGE_IDS);
  
  if (!processedJson) {
    return [];
  }
  
  try {
    return JSON.parse(processedJson);
  } catch (e) {
    Logger.log("Failed to parse processed IDs: " + e.message);
    return [];
  }
}

/**
 * Mark message as processed
 */
function markMessageProcessed(messageId) {
  var processedIds = getProcessedMessageIds();
  
  // Add new ID
  processedIds.push(messageId);
  
  // Keep only last 2000 IDs (prevents storage bloat)
  if (processedIds.length > 2000) {
    processedIds = processedIds.slice(-2000);
  }
  
  // Save back to properties
  var props = PropertiesService.getScriptProperties();
  props.setProperty(CONFIG.PROCESSED_MESSAGE_IDS, JSON.stringify(processedIds));
}

/**
 * Clear all processed message tracking (for reset/testing)
 */
function clearProcessedMessages() {
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty(CONFIG.PROCESSED_MESSAGE_IDS);
  props.deleteProperty(CONFIG.LAST_CHECK_TIME);
  Logger.log("✅ Cleared all processed message tracking");
}

// ============================================================================
// SETUP AND TRIGGER MANAGEMENT
// ============================================================================

/**
 * SETUP FUNCTION - RUN THIS ONCE TO START THE MONITOR
 * This creates the trigger that runs every minute automatically
 */
function setupEmailMonitor() {
  Logger.log("=== Setting Up Email Monitor ===");
  
  // First, delete any existing triggers to avoid duplicates
  deleteAllMonitorTriggers();
  
  // Create new trigger that runs every minute
  ScriptApp.newTrigger('monitorEmails')
    .timeBased()
    .everyMinutes(CONFIG.CHECK_INTERVAL_MINUTES)
    .create();
  
  Logger.log("✅ Email monitor trigger created!");
  Logger.log("   Function: monitorEmails()");
  Logger.log("   Interval: Every " + CONFIG.CHECK_INTERVAL_MINUTES + " minute(s)");
  Logger.log("   Allowed files: " + CONFIG.ALLOWED_EXTENSIONS.join(", "));
  
  // Initialize last check time to now
  updateLastCheckTime(new Date());
  
  Logger.log("");
  Logger.log("🎉 Setup complete! Monitor is now active.");
  Logger.log("   The script will automatically check for new emails every minute.");
  Logger.log("   You don't need to do anything else.");
  Logger.log("");
  Logger.log("Running first check now...");
  
  // Run once immediately to test
  monitorEmails();
}

/**
 * Delete all monitor triggers
 */
function deleteAllMonitorTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  var deleteCount = 0;
  
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'monitorEmails') {
      ScriptApp.deleteTrigger(triggers[i]);
      deleteCount++;
    }
  }
  
  if (deleteCount > 0) {
    Logger.log("Deleted " + deleteCount + " existing trigger(s)");
  }
}

/**
 * Stop the email monitor (delete trigger)
 */
function stopEmailMonitor() {
  Logger.log("⚠️ Stopping email monitor...");
  deleteAllMonitorTriggers();
  Logger.log("✅ Email monitor stopped");
  Logger.log("   Run setupEmailMonitor() to start it again");
}

/**
 * Complete reset - stops monitor and clears all tracking
 */
function resetEmailMonitor() {
  Logger.log("⚠️⚠️⚠️ RESETTING EMAIL MONITOR ⚠️⚠️⚠️");
  
  // Stop the monitor
  deleteAllMonitorTriggers();
  
  // Clear all tracking data
  clearProcessedMessages();
  
  Logger.log("✅ Reset complete");
  Logger.log("   Run setupEmailMonitor() to start fresh");
}

// ============================================================================
// UTILITIES AND INFORMATION
// ============================================================================

/**
 * Get current monitor status and statistics
 * UPDATED: Shows active domain filters
 */
function getMonitorStatus() {
  Logger.log("╔════════════════════════════════════════════╗");
  Logger.log("║       EMAIL MONITOR STATUS                 ║");
  Logger.log("╚════════════════════════════════════════════╝");
  Logger.log("");
  
  // Check if monitor is active
  var triggers = ScriptApp.getProjectTriggers();
  var monitorTriggers = triggers.filter(function(t) {
    return t.getHandlerFunction() === 'monitorEmails';
  });
  
  if (monitorTriggers.length === 0) {
    Logger.log("❌ MONITOR IS NOT ACTIVE");
    Logger.log("   Run setupEmailMonitor() to start it");
    Logger.log("");
    return;
  }
  
  Logger.log("✅ MONITOR IS ACTIVE");
  Logger.log("");
  
  // Statistics
  Logger.log("📊 STATISTICS");
  Logger.log("─────────────────────────────────────────");
  var processedIds = getProcessedMessageIds();
  Logger.log("Messages processed: " + processedIds.length);
  
  var lastCheck = getLastCheckTime();
  Logger.log("Last check: " + lastCheck.toISOString());
  
  var nextCheck = new Date(Date.now() + CONFIG.CHECK_INTERVAL_MINUTES * 60000);
  Logger.log("Next check: ~" + nextCheck.toISOString());
  Logger.log("");
  
  // Configuration
  Logger.log("⚙️  CONFIGURATION");
  Logger.log("─────────────────────────────────────────");
  Logger.log("Check interval: Every " + CONFIG.CHECK_INTERVAL_MINUTES + " minute(s)");
  Logger.log("Allowed files: " + CONFIG.ALLOWED_EXTENSIONS.join(", "));
  Logger.log("Max attachments/run: " + CONFIG.MAX_ATTACHMENTS_PER_RUN);
  Logger.log("");
  
  // Domain Filters (NEW)
  Logger.log("🔒 DOMAIN FILTERS");
  Logger.log("─────────────────────────────────────────");
  var filters = getDomainFilters();
  if (filters.length > 0) {
    Logger.log("Active filters: " + filters.length);
    filters.forEach(function(domain) {
      Logger.log("  • " + domain + " (EXCLUDED)");
    });
    Logger.log("");
    Logger.log("ℹ️  Emails where ALL participants are from");
    Logger.log("   these domains will be skipped.");
  } else {
    Logger.log("No filters active");
    Logger.log("All emails will be monitored and sent to server");
  }
  Logger.log("");
  
  // Triggers
  Logger.log("🔧 TRIGGERS");
  Logger.log("─────────────────────────────────────────");
  Logger.log("Active monitor triggers: " + monitorTriggers.length);
  Logger.log("Total project triggers: " + triggers.length);
  Logger.log("");
}

/**
 * Test the monitor manually (doesn't require trigger)
 */
function testMonitor() {
  Logger.log("=== MANUAL TEST RUN ===");
  Logger.log("This will run the monitor once without waiting for the trigger");
  Logger.log("");
  monitorEmails();
}

/**
 * List all active triggers in the project
 */
function listAllTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  
  Logger.log("=== ALL PROJECT TRIGGERS ===");
  Logger.log("Total: " + triggers.length);
  Logger.log("");
  
  for (var i = 0; i < triggers.length; i++) {
    var trigger = triggers[i];
    Logger.log("Trigger " + (i + 1) + ":");
    Logger.log("  Function: " + trigger.getHandlerFunction());
    Logger.log("  Type: " + trigger.getEventType());
    Logger.log("  ID: " + trigger.getUniqueId());
    Logger.log("");
  }
}

// ============================================================================
// DOMAIN FILTERING (APPLIED ONLY IN BACKGROUND MONITOR)
// ============================================================================

/**
 * Get domain filters from Script Properties
 * Shared with main script but ONLY applied here in background monitor
 */
function getDomainFilters() {
  var scriptProps = PropertiesService.getScriptProperties();
  var filtersJson = scriptProps.getProperty("domain_filters");
  
  if (!filtersJson) {
    return [];
  }
  
  try {
    return JSON.parse(filtersJson);
  } catch (e) {
    Logger.log("Failed to parse domain filters: " + e.message);
    return [];
  }
}

function shouldFilterEmail(emailAddress) {
  if (!emailAddress) return false;

  var filters = getDomainFilters();
  if (!filters || filters.length === 0) return false;

  // Extract raw email from Gmail format
  var match = emailAddress.match(/<(.+?)>/);
  var email = match ? match[1] : emailAddress;

  email = email.toLowerCase().trim();

  var atIndex = email.lastIndexOf('@');
  if (atIndex === -1) return false;

  var domain = email.substring(atIndex + 1);

  for (var i = 0; i < filters.length; i++) {
    var filter = filters[i].toLowerCase().trim();

    if (!filter) continue;

    // FULL EMAIL FILTER
    if (filter.indexOf('@') !== -1) {
      if (email === filter) {
        Logger.log("🚫 Filtered by FULL email: " + email);
        return true;
      }
    } 
    // DOMAIN FILTER
    else {
      if (domain === filter) {
        Logger.log("🚫 Filtered by DOMAIN: " + domain);
        return true;
      }
    }
  }

  return false;
}


function shouldFilterMessage(message) {
  var participants = [];

  // From
  participants.push(message.getFrom());

  // To
  participants = participants.concat(
    message.getTo().split(',')
  );

  // CC (if exists)
  if (message.getCc()) {
    participants = participants.concat(
      message.getCc().split(',')
    );
  }

  // Check each participant
  for (var i = 0; i < participants.length; i++) {
    if (shouldFilterEmail(participants[i])) {
      Logger.log("🚫 Message filtered due to: " + participants[i]);
      return true;
    }
  }

  return false;
}

// ============================================================================
// QUICK START GUIDE
// ============================================================================

/**
 * Display setup instructions
 */
function showSetupInstructions() {
  Logger.log("╔════════════════════════════════════════════════════════════════╗");
  Logger.log("║                EMAIL MONITOR - SETUP GUIDE                     ║");
  Logger.log("╚════════════════════════════════════════════════════════════════╝");
  Logger.log("");
  Logger.log("📋 STEP 1: Configure Server URL");
  Logger.log("   1. Go to Project Settings (gear icon)");
  Logger.log("   2. Click 'Script Properties'");
  Logger.log("   3. Add property:");
  Logger.log("      Property: FLASK_SERVER_URL");
  Logger.log("      Value: Your Flask server URL (e.g., https://your-server.com/api)");
  Logger.log("");
  Logger.log("🚀 STEP 2: Start the Monitor");
  Logger.log("   1. Run this function: setupEmailMonitor()");
  Logger.log("   2. Authorize the script when prompted");
  Logger.log("   3. Done! Monitor will run automatically every minute");
  Logger.log("");
  Logger.log("📊 CHECK STATUS");
  Logger.log("   Run: getMonitorStatus()");
  Logger.log("");
  Logger.log("🛑 STOP MONITOR");
  Logger.log("   Run: stopEmailMonitor()");
  Logger.log("");
  Logger.log("🔄 RESET EVERYTHING");
  Logger.log("   Run: resetEmailMonitor()");
  Logger.log("");
  Logger.log("🧪 TEST MANUALLY");
  Logger.log("   Run: testMonitor()");
  Logger.log("");
}



/**
 * Display available colors with examples
 */
function showAvailableColors() {
  Logger.log("╔════════════════════════════════════════════╗");
  Logger.log("║       AVAILABLE LABEL COLORS               ║");
  Logger.log("╚════════════════════════════════════════════╝");
  Logger.log("");
  Logger.log("Examples:");
  Logger.log("  Run: setLabelColor('Important', 'red')");
  Logger.log("  Run: setLabelColor('Urgent', 'orange')");
  Logger.log("  Run: setLabelColor('Done', 'green')");
  Logger.log("");
  Logger.log("Available colors:");
  Logger.log("  • red          - Bright red");
  Logger.log("  • orange       - Bright orange");
  Logger.log("  • yellow       - Bright yellow");
  Logger.log("  • green        - Bright green");
  Logger.log("  • cyan         - Bright cyan/turquoise");
  Logger.log("  • blue         - Bright blue");
  Logger.log("  • purple       - Bright purple");
  Logger.log("  • gray         - Medium gray");
  Logger.log("  • lightgray    - Light gray");
  Logger.log("  • darkgray     - Dark gray");
  Logger.log("  • cocoa        - Brown/cocoa");
  Logger.log("  • white        - White/default");
  Logger.log("");
  Logger.log("Current labels created by main script:");
  Logger.log("─────────────────────────────────────────");
  
  // List all existing labels instead of color config
  var existingLabels = GmailApp.getUserLabels();
  for (var i = 0; i < existingLabels.length; i++) {
    var label = existingLabels[i];
    Logger.log("  ▪ " + label.getName() + " (color set by main script)");
  }
}

/**
 * TEST FUNCTION: Verify labels exist (colors are handled by main script)
 * Run this to test if all required labels have been created
 */
function testLabelColors() {
  Logger.log("=== TESTING LABEL EXISTENCE ===");
  Logger.log("(Colors are set by the main Gmail add-on script)");
  Logger.log("");
  
  // Test labels that should be generated by Python backend
  var testLabels = [
    "response", "FYI", "Notification", "meeting", "Escalation", 
    "hotels", "airlines", "travel", "restaurant", "booking", 
    "bank", "Insurance", "Other", "Awaiting Reply"
  ];
  
  var existingLabels = GmailApp.getUserLabels();
  var existingLabelNames = {};
  
  for (var i = 0; i < existingLabels.length; i++) {
    existingLabelNames[existingLabels[i].getName().toLowerCase()] = true;
  }
  
  for (var i = 0; i < testLabels.length; i++) {
    var labelName = testLabels[i];
    var formattedName = labelName.charAt(0).toUpperCase() + labelName.slice(1).toLowerCase();
    
    if (existingLabelNames[formattedName.toLowerCase()]) {
      Logger.log("✓ " + formattedName + " → EXISTS");
    } else {
      Logger.log("✗ " + formattedName + " → MISSING (run Gmail add-on to create)");
    }
  }
  
  Logger.log("");
  Logger.log("=== ALL EXISTING LABELS ===");
  for (var i = 0; i < existingLabels.length; i++) {
    Logger.log("  " + existingLabels[i].getName());
  }
}