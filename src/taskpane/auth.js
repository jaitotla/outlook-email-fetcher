import { PublicClientApplication } from "@azure/msal-browser";

const msalConfig = {
  auth: {
    clientId: "708b6c48-376c-4d05-8529-f256785836d9",
    authority: "https://login.microsoftonline.com/consumers",
    redirectUri: "https://localhost:3000/auth.html",
  },
};

const msalInstance = new PublicClientApplication(msalConfig);
const loginRequest = { scopes: ["Mail.ReadWrite", "MailboxSettings.ReadWrite", "User.Read"] };

Office.onReady(async () => {
  await msalInstance.initialize();
  const response = await msalInstance.handleRedirectPromise();
  if (response) {
    Office.context.ui.messageParent(JSON.stringify({ status: "success", token: response.accessToken }));
  } else {
    await msalInstance.loginRedirect(loginRequest);
  }
});