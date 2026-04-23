# Agent URL Input Fix

## Issue
The agent URL input field in the onboarding/popup view was not becoming editable when a mode (Local/External) was selected. It remained grayed out with the placeholder "Choose a mode first...".

## Root Cause
The HTML had `readonly` attribute set on the input field initially:
```html
<input type="url" id="ob-agent-url" ... placeholder="Choose a mode first…" readonly ...>
```

When the user selected a mode, the JavaScript set `agentInput.readOnly = false`, but this only changed the JavaScript property, not the HTML attribute. In some browsers/contexts, the HTML attribute takes precedence.

## Fix Applied

### 1. popup.js - Added explicit attribute removal
```javascript
// In updateModeVisibility() function:
else if (mode) {  // For local/external modes
  if (agentInput) {
    agentInput.readOnly = false;
    agentInput.removeAttribute("readonly");  // ← Explicitly remove HTML attribute
    agentInput.style.background = "";
    agentInput.style.color = "";
    agentInput.placeholder = "http://your-server:5050";
  }
}
```

### 2. options.js - Added similar fix
```javascript
// In updateModeFields() function for options page:
else if (mode) {
  urlInput.disabled = false;
  urlInput.removeAttribute("disabled");  // ← Remove disabled attribute
  urlInput.classList.remove("hidden");
}
```

### 3. Added HTML required attribute
```html
<input type="url" id="agent_url" name="agent_url"
       placeholder="http://your-server:5050"
       class="hidden"
       required>  <!-- ← Added for form validation -->
```

## Testing

### Test in Thunderbird:
1. Open Thunderbird
2. Click OpenMailBot icon → Should show onboarding
3. Select "Local" or "External API" from Mode dropdown
4. **Verify:** Agent URL field becomes editable (white background, black text)
5. **Verify:** Placeholder changes to "http://your-server:5050"
6. **Verify:** You can click and type in the field

### Debug Logging
Added console.log to help troubleshoot:
```javascript
console.log(`[updateModeVisibility] prefix=${prefix}, mode=${mode}, agentInput=`, agentInput);
console.log(`[updateModeVisibility] Agent input should now be editable. readonly=${agentInput.readOnly}`);
```

Check browser console (Ctrl+Shift+J) to see these logs.

## Files Modified
1. `agent/thunderbrid-addon/popup/popup.js` - Lines 48-88
2. `agent/thunderbrid-addon/options/options.js` - Lines 167-206
3. `agent/thunderbrid-addon/options/options.html` - Line 57

## Why This Happened
The HTML `readonly` attribute is not automatically removed when you set the JavaScript property `readOnly = false`. You need to explicitly call `removeAttribute("readonly")` to remove it from the DOM.

This is a common gotcha with HTML boolean attributes like:
- `readonly` / `readOnly`
- `disabled` / `disabled`  
- `checked` / `checked`
- `selected` / `selected`

Always use both approaches to be safe:
```javascript
element.readOnly = false;          // Set JS property
element.removeAttribute("readonly"); // Remove HTML attribute
```

## Status
✅ **FIXED** - Agent URL field should now be editable when Local or External mode is selected.
