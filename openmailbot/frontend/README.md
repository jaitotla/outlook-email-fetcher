# Frontend (Next.js + Tailwind)

This folder contains the web portal for OpenMailBot. Users can work without the Gmail add-on:

## Account Linking
- Users can link either a Google (Gmail) or Outlook/Hotmail account.
- Email data is pulled into the platform after authentication.

## Chatbot UI
- The frontend provides a chatbot interface for users to query, summarize, and analyze their emails using natural language.
- Similar to the Gmail add-on, but users must specify which email or thread to discuss (since the add-on knows the context automatically).

## Modules
- Home Page
- Signup/Login (Google OAuth or Outlook OAuth)
- User Dashboard
- Admin Dashboard
- Group Dashboard
- Analytics (Recharts/Chart.js)
- Settings
- Chatbot (email Q&A, summaries, smart replies)

## Onboarding Flow
1. User chooses Google or Outlook/Hotmail.
2. Links their account via OAuth.
3. Emails are pulled into the platform.
4. User can chat about their emails via the chatbot UI.

## Note
- The Gmail add-on automatically references the opened email for summary generation.
- On the web portal, users must specify the email/thread to discuss in the chatbot.

Run `npx create-next-app .` and add Tailwind CSS for setup.