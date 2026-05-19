"""
Email Ingestion Service
Fetches and processes emails from Gmail and Outlook
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from msal import ConfidentialClientApplication
import httpx

from agent.config import settings


class EmailIngestionService:
    def __init__(self):
        self.backend_url = settings.BACKEND_API_URL
    
    async def ingest_emails(
        self,
        user_id: str,
        tenant_id: str,
        provider: str,
        access_token: str,
        sync_from: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Ingest emails from Gmail or Outlook"""
        
        if provider == "google":
            return await self._ingest_gmail(user_id, tenant_id, access_token, sync_from)
        elif provider == "microsoft":
            return await self._ingest_outlook(user_id, tenant_id, access_token, sync_from)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def _ingest_gmail(
        self,
        user_id: str,
        tenant_id: str,
        access_token: str,
        sync_from: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Ingest emails from Gmail"""
        
        try:
            # Create credentials
            creds = Credentials(token=access_token)
            service = build('gmail', 'v1', credentials=creds)
            
            # Build query
            query = ""
            if sync_from:
                query = f"after:{int(sync_from.timestamp())}"
            
            # Fetch messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=100
            ).execute()
            
            messages = results.get('messages', [])
            ingested_count = 0
            
            for msg in messages:
                # Get full message
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # Extract email data
                email_data = self._parse_gmail_message(message)
                
                # Store in database via backend API
                await self._store_email(user_id, tenant_id, email_data)
                
                ingested_count += 1
            
            return {
                "success": True,
                "provider": "google",
                "ingestedCount": ingested_count,
                "userId": user_id
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": "google"
            }
    
    async def _ingest_outlook(
        self,
        user_id: str,
        tenant_id: str,
        access_token: str,
        sync_from: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Ingest emails from Outlook"""
        
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build filter
            url = "https://graph.microsoft.com/v1.0/me/messages"
            params = {
                "$top": 100,
                "$orderby": "receivedDateTime DESC"
            }
            
            if sync_from:
                params["$filter"] = f"receivedDateTime ge {sync_from.isoformat()}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
            
            messages = data.get('value', [])
            ingested_count = 0
            
            for msg in messages:
                # Extract email data
                email_data = self._parse_outlook_message(msg)
                
                # Store in database via backend API
                await self._store_email(user_id, tenant_id, email_data)
                
                ingested_count += 1
            
            return {
                "success": True,
                "provider": "microsoft",
                "ingestedCount": ingested_count,
                "userId": user_id
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": "microsoft"
            }
    
    def _parse_gmail_message(self, message: Dict) -> Dict[str, Any]:
        """Parse Gmail message to standard format"""
        
        headers = {h['name']: h['value'] for h in message['payload']['headers']}
        
        # Get body
        body = ""
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    body = base64.urlsafe_b64decode(
                        part['body'].get('data', '')
                    ).decode('utf-8')
                    break
        else:
            body = base64.urlsafe_b64decode(
                message['payload']['body'].get('data', '')
            ).decode('utf-8')
        
        return {
            "messageId": message['id'],
            "threadId": message['threadId'],
            "from": headers.get('From', ''),
            "to": [headers.get('To', '')],
            "subject": headers.get('Subject', ''),
            "timestamp": datetime.fromtimestamp(int(message['internalDate']) / 1000),
            "content": body,
            "labels": message.get('labelIds', [])
        }
    
    def _parse_outlook_message(self, message: Dict) -> Dict[str, Any]:
        """Parse Outlook message to standard format"""
        
        return {
            "messageId": message['id'],
            "threadId": message.get('conversationId', message['id']),
            "from": message['from']['emailAddress']['address'],
            "to": [recipient['emailAddress']['address'] for recipient in message.get('toRecipients', [])],
            "subject": message.get('subject', ''),
            "timestamp": datetime.fromisoformat(message['receivedDateTime'].replace('Z', '+00:00')),
            "content": message.get('body', {}).get('content', ''),
            "labels": message.get('categories', [])
        }
    
    async def _store_email(self, user_id: str, tenant_id: str, email_data: Dict):
        """Store email via backend API"""
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.backend_url}/api/emails/ingest",
                json={
                    "userId": user_id,
                    "tenantId": tenant_id,
                    "email": email_data
                }
            )
            response.raise_for_status()
