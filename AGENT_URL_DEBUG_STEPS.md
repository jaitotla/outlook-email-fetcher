# Agent URL Field Debug Steps

## Changes Made

1. **Added MANOTR_AGENT_URL constant** to popup.js (was causing JavaScript errors)
2. **Removed inline styles** from HTML that were making field look disabled  
3. **Added dual event listeners** (both 'change' and 'input') for mode dropdown
4. **Added extensive console logging** to track field state changes
5. **Added initialization debugging** to see state 100ms after page load

## How to Test

### Step 1: Reload the Add-on
1. Press `Ctrl+Shift+A` to open Add-ons Manager
2. Click the gear icon (⚙️) at the top
3. Select "Debug Add-ons"
4. Find "OpenMailBot" in the list
5. Click the **Reload** button
6. Close the debug tab and go back to Thunderbird

### Step 2: Open Browser Console
1. Press `Ctrl+Shift+J` to open Browser Console
2. Clear any old messages (trash icon)  
3. Keep this window open next to Thunderbird

### Step 3: Open OpenMailBot Popup
1. Click the OpenMailBot icon in Thunderbird
2. You should see the onboarding page
3. **Check the console** - you should see messages like:
   ```
   [initOnboarding] After 100ms - Mode: 
   [initOnboarding] Agent input readonly: true
   ```

### Step 4: Select a Mode
1. In the popup, click the **MODE** dropdown  
2. Select **"Local (local URLs like Ollama)"**
3. **Watch the console** - you should see:
   ```
   [Popup] Mode changed to: local
   [updateModeVisibility] prefix=ob, mode=local, agentInput=...
   [updateModeVisibility] Agent input should now be editable. readonly=false
   ```

### Step 5: Test the Field
1. Click in the **Agent URL** field
2. It should:
   - Have a **white background** (not gray)
   - Show **black text** (not gray)
   - Have placeholder: **"http://your-server:5050"** (not "Choose a mode first...")
   - Be **clickable and typeable**
3. Try typing: `http://localhost:5051`

## Expected Console Output

```
[initOnboarding] After 100ms - Mode: 
[initOnboarding] Agent input readonly: true
[initOnboarding] Agent input readonly attr: readonly
[initOnboarding] Agent input value: 

[Popup] Mode changed to: local
[updateModeVisibility] prefix=ob, mode=local, agentInput= HTMLInputElement
[updateModeVisibility] Agent input should now be editable. readonly=false
```

## If It Still Doesn't Work

### Check 1: Is the mode actually changing?
- If you don't see `[Popup] Mode changed to: local` in console, the event listener isn't firing
- Try clicking on a different option, then back to "Local"

### Check 2: Is JavaScript error happening?
- Look for RED error messages in console
- Common errors:
  - `MANOTR_AGENT_URL is not defined` → Reload didn't work, try restarting Thunderbird
  - `Cannot read property of null` → Element not found, timing issue

### Check 3: Manual Test
1. In Browser Console (Ctrl+Shift+J), paste this:
```javascript
const agentInput = document.getElementById("ob-agent-url");
console.log("Readonly:", agentInput.readOnly);
console.log("Readonly attr:", agentInput.getAttribute("readonly"));
agentInput.readOnly = false;
agentInput.removeAttribute("readonly");
agentInput.style.background = "#ffffff";
agentInput.style.color = "#000000";
agentInput.placeholder = "http://your-server:5050";
console.log("Field updated - try typing now!");
```

2. Press Enter
3. Try typing in the field

## If Manual Test Works

If the manual JavaScript test works but selecting the mode doesn't:
1. The event listener isn't attached properly
2. Need to fully restart Thunderbird (not just reload)
3. Possible caching issue

## Next Steps

Report back with:
1. ✅/❌ Did the field become editable after selecting "Local"?
2. 📋 Copy/paste the console output
3. 🐛 Any red error messages?
4. 🔧 Did the manual test work?

