"""
Neo4j Graph Database Client
Manages email thread relationships and contact networks
"""
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable

from agent.config import settings


class Neo4jClient:
    def __init__(self):
        if not settings.NEO4J_PASSWORD:
            raise ValueError("Neo4j password not configured")
        
        self.driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    
    async def close(self):
        """Close the driver connection"""
        await self.driver.close()
    
    async def create_email_node(
        self,
        email_id: str,
        thread_id: str,
        user_id: str,
        tenant_id: str,
        metadata: Dict[str, Any]
    ):
        """Create an email node in the graph"""
        
        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (e:Email {id: $email_id})
                SET e.threadId = $thread_id,
                    e.userId = $user_id,
                    e.tenantId = $tenant_id,
                    e.subject = $subject,
                    e.from = $from,
                    e.timestamp = $timestamp
                """,
                email_id=email_id,
                thread_id=thread_id,
                user_id=user_id,
                tenant_id=tenant_id,
                subject=metadata.get('subject', ''),
                from_address=metadata.get('from', ''),
                timestamp=metadata.get('timestamp', '')
            )
    
    async def create_thread_relationship(
        self,
        email_id1: str,
        email_id2: str
    ):
        """Create a relationship between emails in the same thread"""
        
        async with self.driver.session() as session:
            await session.run(
                """
                MATCH (e1:Email {id: $email_id1})
                MATCH (e2:Email {id: $email_id2})
                MERGE (e1)-[:IN_THREAD]->(e2)
                """,
                email_id1=email_id1,
                email_id2=email_id2
            )
    
    async def create_reply_relationship(
        self,
        reply_id: str,
        original_id: str
    ):
        """Create a reply relationship between emails"""
        
        async with self.driver.session() as session:
            await session.run(
                """
                MATCH (reply:Email {id: $reply_id})
                MATCH (original:Email {id: $original_id})
                MERGE (reply)-[:REPLIES_TO]->(original)
                """,
                reply_id=reply_id,
                original_id=original_id
            )
    
    async def create_contact_node(
        self,
        email_address: str,
        name: Optional[str] = None
    ):
        """Create a contact node"""
        
        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (c:Contact {email: $email})
                SET c.name = COALESCE($name, c.name)
                """,
                email=email_address,
                name=name
            )
    
    async def create_contact_relationship(
        self,
        email_id: str,
        contact_email: str,
        relationship_type: str  # "FROM" or "TO"
    ):
        """Create relationship between email and contact"""
        
        async with self.driver.session() as session:
            if relationship_type == "FROM":
                await session.run(
                    """
                    MATCH (e:Email {id: $email_id})
                    MATCH (c:Contact {email: $contact_email})
                    MERGE (e)-[:FROM_CONTACT]->(c)
                    """,
                    email_id=email_id,
                    contact_email=contact_email
                )
            else:  # TO
                await session.run(
                    """
                    MATCH (e:Email {id: $email_id})
                    MATCH (c:Contact {email: $contact_email})
                    MERGE (e)-[:TO_CONTACT]->(c)
                    """,
                    email_id=email_id,
                    contact_email=contact_email
                )
    
    async def get_related_threads(
        self,
        thread_id: str,
        user_id: str,
        tenant_id: str,
        limit: int = 5
    ) -> List[str]:
        """
        Find related threads based on:
        - Shared contacts
        - Similar topics (would need topic extraction)
        """
        
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e1:Email {threadId: $thread_id, userId: $user_id, tenantId: $tenant_id})
                MATCH (e1)-[:FROM_CONTACT|TO_CONTACT]->(c:Contact)
                MATCH (e2:Email)-[:FROM_CONTACT|TO_CONTACT]->(c)
                WHERE e2.threadId <> $thread_id 
                  AND e2.userId = $user_id 
                  AND e2.tenantId = $tenant_id
                WITH e2.threadId as relatedThreadId, COUNT(DISTINCT c) as sharedContacts
                RETURN relatedThreadId
                ORDER BY sharedContacts DESC
                LIMIT $limit
                """,
                thread_id=thread_id,
                user_id=user_id,
                tenant_id=tenant_id,
                limit=limit
            )
            
            return [record["relatedThreadId"] async for record in result]
    
    async def get_contact_network(
        self,
        user_id: str,
        tenant_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get the user's contact network"""
        
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Email {userId: $user_id, tenantId: $tenant_id})
                MATCH (e)-[:FROM_CONTACT|TO_CONTACT]->(c:Contact)
                WITH c, COUNT(e) as emailCount
                RETURN c.email as email, c.name as name, emailCount
                ORDER BY emailCount DESC
                LIMIT $limit
                """,
                user_id=user_id,
                tenant_id=tenant_id,
                limit=limit
            )
            
            contacts = []
            async for record in result:
                contacts.append({
                    "email": record["email"],
                    "name": record["name"],
                    "emailCount": record["emailCount"]
                })
            
            return contacts
    
    async def get_thread_timeline(
        self,
        thread_id: str,
        user_id: str,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Get chronological timeline of emails in a thread"""
        
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Email {threadId: $thread_id, userId: $user_id, tenantId: $tenant_id})
                RETURN e.id as id, e.subject as subject, e.from as from, e.timestamp as timestamp
                ORDER BY e.timestamp
                """,
                thread_id=thread_id,
                user_id=user_id,
                tenant_id=tenant_id
            )
            
            timeline = []
            async for record in result:
                timeline.append({
                    "id": record["id"],
                    "subject": record["subject"],
                    "from": record["from"],
                    "timestamp": record["timestamp"]
                })
            
            return timeline
    
    async def delete_user_data(
        self,
        user_id: str,
        tenant_id: str
    ):
        """Delete all graph data for a user"""
        
        async with self.driver.session() as session:
            await session.run(
                """
                MATCH (e:Email {userId: $user_id, tenantId: $tenant_id})
                DETACH DELETE e
                """,
                user_id=user_id,
                tenant_id=tenant_id
            )
