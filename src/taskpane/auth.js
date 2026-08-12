import { PublicClientApplication } from "@azure/msal-browser";

const msalConfig = {
  auth: {
    clientId: "708b6c48-376c-4d05-8529-f256785836d9",
    authority: "https://login.microsoftonline.com/consumers",
    redirectUri: "https://outlook-email-fetcher.vercel.app/auth.html",
  },
  cache: {
    cacheLocation: "localStorage",
  },
};

const msalInstance = new PublicClientApplication(msalConfig);
const loginRequest = { scopes: ["Mail.ReadWrite", "MailboxSettings.ReadWrite", "User.Read"] };

function sendResultToParent(payload) {
  try {
    if (Office.context && Office.context.ui && Office.context.ui.messageParent) {
      Office.context.ui.messageParent(JSON.stringify(payload));
    } else {
      console.error("Office.context.ui not available — retrying in 300ms");
      setTimeout(() => sendResultToParent(payload), 300);
    }
  } catch (e) {
    console.error("messageParent failed:", e);
  }
}

Office.onReady(async () => {
  await msalInstance.initialize();

  try {
    const response = await msalInstance.loginPopup(loginRequest);
    sendResultToParent({ status: "success", token: response.accessToken });
  } catch (e) {
    console.error("loginPopup failed:", e);
    sendResultToParent({ status: "error", message: e.message });
  }
});