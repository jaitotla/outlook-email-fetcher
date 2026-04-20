# OpenMailBot Thunderbird Add-on: Multi-Account Setup Guide

**Last Updated**: April 14, 2026

---

## 🎯 What's New?

You can now:
- ✅ Use OpenMailBot with multiple Thunderbird email accounts
- ✅ Keep separate settings for each account
- ✅ automatically load settings you saved on Gmail/other services

---

## 🚀 Quick Start

### If You Have ONE Email Account

When you first open the add-on, it will automatically:
1. Detect your email account
2. Check if you have settings saved on the server
3. Ask if you want to use those settings or configure new ones
4. Save and you're done!

### If You Have MULTIPLE Email Accounts

**First Time Setup:**
1. Open OpenMailBot add-on
2. See a dropdown with your accounts (e.g., "work@company.com", "personal@gmail.com")
3. Select the account you want to configure first
4. Choose to check server for existing settings or configure manually
5. Save settings
6. ...Open the add-on again and repeat for your other accounts

Each account will have its own separate settings!

---

## 📧 How It Works

### Step 1: Choose Account
![Account Selection](./docs/step1-account-selection.png)

When opening the add-on for the first time, you'll see all your Thunderbird email accounts listed.

```
📧 Thunderbird Account
[▼] work@company.com
```

Select which account to configure.

### Step 2: Check Server (Optional)
![Check Server](./docs/step2-check-server.png)

Click the button to see if you already have settings saved:

```
🔍 Check Server for Existing Settings
```

**Possible Results:**
- ✅ **Settings Found**: "Found settings on server!"
- ℹ️ **No Settings**: "No settings found on server. You can configure now."
- ❌ **Error**: "Server is unreachable" (you can still configure manually)

### Step 3: Choose Your Settings
![Use or Configure](./docs/step3-use-or-configure.png)

**If settings were found on server:**
- `✅ Use These Settings` - Load them and get started
- `🔄 Configure Manually` - Set up your own preferences

**If no settings found:**
- Configure all settings manually

### Step 4: Configure (If Needed)
![Configure Settings](./docs/step4-configure.png)

Fill out:
- 🌐 **Backend URL** (leave default unless self-hosting)
- 🔧 **Mode** (Inbuilt or Custom)
- 🤖 **LLM Provider** (OpenAI, Anthropic, Ollama, etc.)
- 🔢 **Embedding Service**
- 🗄️ **Vector Database**
- 👤 **User Profile**

### Step 5: Save
![Save Settings](./docs/step5-save.png)

Click `🚀 Get Started` to save your settings for this account.

Settings are automatically saved to:
- 📱 Your device (browser storage)
- ☁️ The server (for backup and multi-device use)

---

## 🔄 Using Multiple Accounts

### After Initial Setup

When you open the add-on with a different account selected in Thunderbird:

**Option 1: Same Settings for All Accounts**
- Just use the same settings (they sync across)

**Option 2: Different Settings Per Account**
- Go to ⚙️ Settings
- The add-on will show you which account's settings you're currently editing
- Modify and save
- When you switch to another account, its settings load automatically

---

## 💡 Common Scenarios

### Scenario 1: Work + Personal Email

**Setup:**
1. First load → Select "work@company.com" → Configure with work settings
2. Save
3. Open add-on again → Select "personal@gmail.com" → Configure with personal settings
4. Save

**Daily Use:**
- In Thunderbird, use work email → Add-on shows work settings
- In Thunderbird, use personal email → Add-on shows personal settings

### Scenario 2: Migrating from Gmail Add-on

**If you used the Gmail add-on before:**
1. First load → Select your account
2. Click "🔍 Check Server for Existing Settings"
3. Add-on finds your Gmail settings
4. Click "✅ Use These Settings"
5. Done! Your settings are loaded

### Scenario 3: Fresh Setup

**If you're setting up for the first time:**
1. First load → Select your account
2. Click "🔍 Check Server" (nothing found)
3. Click "🔄 Configure Manually"
4. Fill in your preferences
5. Click "🚀 Get Started"

---

## ⚙️ Settings Management

### Changing Settings Later

1. Open add-on
2. Click ⚙️ **Settings** button
3. Modify any settings
4. Click **Save Settings**
5. Settings are saved for your current account

### Settings Per Account

| Account | LLM Provider | Tone | Status |
|---------|------------|------|--------|
| work@company.com | OpenAI | Professional | ✅ Saved |
| personal@gmail.com | Ollama | Friendly | ✅ Saved |

Each account maintains its own configuration.

---

## 🔗 Syncing Across Devices

### How It Works
1. Settings saved in Thunderbird → Stored locally
2. Also synced to OpenMailBot server
3. On another device with same account → Same settings automatically available

### Requirements
- Same email account configured on both devices
- Both using OpenMailBot add-on
- Internet connection for sync

**Example:**
- Set up on laptop with personal@gmail.com
- Later use Thunderbird on desktop
- Settings automatically available for personal@gmail.com

---

## ❓ FAQ

### Q: Do I need to set up each account separately?
**A:** Only if you want different settings per account. If you want the same settings for all accounts, set it up once and it applies.

### Q: What if I delete one account from Thunderbird?
**A:** Settings for that account remain stored (but unused). If you add the same account back later, they'll load automatically.

### Q: Can I use the same email in different Thunderbird instances?
**A:** Yes! Each Thunderbird instance can have settings for the same account, and they'll sync via the server.

### Q: What happens if the server is unavailable?
**A:** Settings are saved locally first. The server sync is optional - you can still use the add-on offline.

### Q: Can I export/backup settings?
**A:** Currently settings are backed up to the server automatically. Full export feature coming soon.

---

## 🆘 Troubleshooting

### Account Not Appearing in Dropdown
- **Check**: Is the account configured in Thunderbird?
- **Fix**: Go to Thunderbird Settings > Mail > Account Settings > Add any missing accounts
- **Reload**: Close and reopen the add-on

### Settings Not Loading After Switching Accounts
- **Check**: Did you save settings for that account?
- **Fix**: Run onboarding again for that account
- **Reload**: Refresh the add-on

### "Check Server" Shows No Settings
- **Expected**: If this is first time using this account with the add-on
- **Action**: Configure manually or use settings from another account

### Can't Connect to Backend Server
- **Check**: Is your internet connection working?
- **Check**: Is the backend URL correct?
- **Fix**: Go to ⚙️ Settings, verify backend URL
- **Workaround**: Settings save locally even if server unreachable

---

## 📞 Support

For issues or questions:
1. Check the [Complete Documentation](./MULTI_ACCOUNT_AND_SETTINGS_SYNC_IMPLEMENTATION.md)
2. Review this guide again
3. Check add-on logs in Thunderbird console
4. Open an issue on GitHub

---

## 🎓 Best Practices

1. **Use Descriptive Settings**: Set "Name" and "Position" fields so you remember which account settings are which

2. **Test Before Production**: After configuring an account, send one test email to verify settings work

3. **Keep Backups**: If using custom API keys, keep copies outside of Thunderbird

4. **Regular Sync**: Occasionally click "Sync Settings" to ensure server backup is current

5. **Update Regularly**: Keep Thunderbird and the add-on updated for latest features

---

**Enjoy multi-account productivity with OpenMailBot! 🚀**

