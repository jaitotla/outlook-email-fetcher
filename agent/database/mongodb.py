"""
MongoDB Client for Agent
"""
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

from agent.config import settings


class MongoDBClient:
    def __init__(self, uri: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client.openmailbot
        
        # Collections
        self.emails = self.db.emailmetadata
        self.users = self.db.users
        self.tenants = self.db.tenants
    
    async def get_emails_by_thread(
        self,
        thread_id: str,
        user_id: str,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Get all emails in a thread"""
        
        cursor = self.emails.find({
            "threadId": thread_id,
            "userId": user_id,
            "tenantId": tenant_id
        }).sort("timestamp", 1)
        
        return await cursor.to_list(length=None)
    
    async def get_user_emails(
        self,
        user_id: str,
        tenant_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user's emails"""
        
        cursor = self.emails.find({
            "userId": user_id,
            "tenantId": tenant_id
        }).sort("timestamp", -1).skip(skip).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_email_by_id(
        self,
        email_id: str,
        user_id: str,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get single email"""
        
        return await self.emails.find_one({
            "id": email_id,
            "userId": user_id,
            "tenantId": tenant_id
        })
    
    async def store_email(
        self,
        email_data: Dict[str, Any]
    ) -> str:
        """Store email metadata"""
        
        result = await self.emails.insert_one(email_data)
        return str(result.inserted_id)
    
    async def update_email(
        self,
        email_id: str,
        user_id: str,
        tenant_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update email metadata"""
        
        result = await self.emails.update_one(
            {
                "id": email_id,
                "userId": user_id,
                "tenantId": tenant_id
            },
            {"$set": updates}
        )
        
        return result.modified_count > 0
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        
        return await self.users.find_one({"id": user_id})
    
    async def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID"""
        
        return await self.tenants.find_one({"id": tenant_id})
