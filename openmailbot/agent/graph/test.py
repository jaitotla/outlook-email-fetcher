import json
from neo4j import GraphDatabase
from openai import OpenAI
from datetime import datetime

class EmailGraphDB:
    def __init__(self, uri, user, password, openai_key):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.client = OpenAI(api_key=openai_key)
    
    def close(self):
        self.driver.close()
    
    def clear_db(self):
        """Clear all data from database"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    def store_email_thread(self, thread_data):
        """Store email thread with all relationships"""
        with self.driver.session() as session:
            # Create Thread
            session.run("""
                MERGE (t:Thread {thread_id: $thread_id})
                SET t.user_id = $user_id,
                    t.message_count = $message_count,
                    t.stored_at = $stored_at
            """, 
                thread_id=thread_data['thread_id'],
                user_id=thread_data['user_id'],
                message_count=thread_data['metadata']['processed_message_count'],
                stored_at=thread_data['metadata']['stored_at']
            )
            
            # Process each message
            for msg in thread_data['messages']:
                # Get sentiment from OpenAI
                sentiment = self._analyze_sentiment(msg['body'])
                
                # Generate embedding for semantic search
                embedding = self._generate_embedding(msg['subject'] + " " + msg['body'])
                
                # Create Email node
                session.run("""
                    MERGE (e:Email {message_id: $message_id})
                    SET e.subject = $subject,
                        e.body = $body,
                        e.timestamp = $timestamp,
                        e.sentiment = $sentiment,
                        e.embedding = $embedding
                """,
                    message_id=msg['message_id'],
                    subject=msg['subject'],
                    body=msg['body'],
                    timestamp=msg['timestamp'],
                    sentiment=sentiment,
                    embedding=embedding
                )
                
                # Link Email to Thread
                session.run("""
                    MATCH (e:Email {message_id: $message_id})
                    MATCH (t:Thread {thread_id: $thread_id})
                    MERGE (e)-[:BELONGS_TO]->(t)
                """,
                    message_id=msg['message_id'],
                    thread_id=thread_data['thread_id']
                )
                
                # Create sender Person and SENT relationship
                sender_email = msg['from'].split('<')[-1].rstrip('>')
                sender_name = msg['from'].split('<')[0].strip()
                
                session.run("""
                    MERGE (p:Person {email: $email})
                    SET p.name = $name
                """,
                    email=sender_email,
                    name=sender_name
                )
                
                session.run("""
                    MATCH (p:Person {email: $sender})
                    MATCH (e:Email {message_id: $message_id})
                    MERGE (p)-[:SENT]->(e)
                """,
                    sender=sender_email,
                    message_id=msg['message_id']
                )
                
                # Create recipients and TO relationships
                for recipient in msg['to']:
                    rec_email = recipient.split('<')[-1].rstrip('>') if '<' in recipient else recipient
                    rec_name = recipient.split('<')[0].strip() if '<' in recipient else recipient
                    
                    session.run("""
                        MERGE (p:Person {email: $email})
                        SET p.name = $name
                    """,
                        email=rec_email,
                        name=rec_name
                    )
                    
                    session.run("""
                        MATCH (e:Email {message_id: $message_id})
                        MATCH (p:Person {email: $recipient})
                        MERGE (e)-[:TO]->(p)
                    """,
                        message_id=msg['message_id'],
                        recipient=rec_email
                    )
    

    
    def _generate_embedding(self, text):
        """Generate embedding vector for text"""
        if not text or text == "No draft content received":
            return None
        
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000]  # Limit text length
            )
            return response.data[0].embedding
        except:
            return None
    
    
    
    def query_with_llm(self, natural_query):
        """Use LLM to generate Cypher query and answer based on results"""
        
        # Step 1: Generate Cypher query using LLM
        cypher_prompt = f"""Given this Neo4j graph schema:
- (Person)-[:SENT]->(Email)
- (Email)-[:TO]->(Person)
- (Email)-[:BELONGS_TO]->(Thread)

Person properties: name, email
Email properties: message_id, subject, body, timestamp, sentiment
Thread properties: thread_id, user_id

Generate a Cypher query to answer: "{natural_query}"

Return ONLY the Cypher query, no explanation."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Neo4j Cypher expert. Generate only the query."},
                {"role": "user", "content": cypher_prompt}
            ]
        )
        
        cypher_query = response.choices[0].message.content.strip()
        cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()
        
        print(f"Generated Cypher: {cypher_query}\n")
        
        # Step 2: Execute the query
        with self.driver.session() as session:
            try:
                result = session.run(cypher_query)
                query_results = [dict(record) for record in result]
            except Exception as e:
                return f"Query execution error: {str(e)}"
        print(query_results)
        # Step 3: Use LLM to format the answer
        answer_prompt = f"""Based on these query results:
{json.dumps(query_results, indent=2, default=str)}

Answer the question: "{natural_query}"

Provide a clear, concise answer."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful email assistant."},
                {"role": "user", "content": answer_prompt}
            ]
        )
        
        return response.choices[0].message.content
    
   


# Usage Example
if __name__ == "__main__":
    # Configuration
    NEO4J_URI = "neo4j+s://e5c7fa42.databases.neo4j.io"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "xR15egCk9mX8Tf4Xo1Wf_Z355rINJ7iO-uyZyx_1T8k"
    OPENAI_API_KEY = "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"
    
    # Initialize
    db = EmailGraphDB(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, OPENAI_API_KEY)
    
    # # Load and store data
    # with open('email_data.json', 'r') as f:
    #     thread_data = json.load(f)
    
    # print("Storing email thread...")
    # db.store_email_thread(thread_data)
    
   
    print("\n=== Smart LLM Query (Cypher Generation) ===")
    answer = db.query_with_llm("what is update on comunication with jayne")
    print(answer)
    

    
    db.close()