import json
import os
from typing import Dict, List, Any
from neo4j import GraphDatabase
from openai import OpenAI

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://49d30f90.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "FIdaz6r8IFSIb9yIELw--5lhHT_M4MRxD80ChOuF2Cg")

OPENAI_API_KEY ="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"
client = OpenAI(api_key=OPENAI_API_KEY)


def extract_entities_and_relationships(chunk_text: str) -> Dict[str, Any]:
    """
    Extract entities and relationships from text using OpenAI.
    
    Args:
        chunk_text: The text to extract entities and relationships from
        
    Returns:
        Dict with "entities" and "relationships" keys
    """
    
    prompt = f"""Extract entities and relationships from the following text.

Return ONLY valid JSON (no markdown, no code blocks):

{{
  "entities": [
    {{
      "name": "...",
      "type": "...",
      "description": "..."
    }}
  ],
  "relationships": [
    {{
      "source": "...",
      "target": "...",
      "relation": "...",
      "description": "..."
    }}
  ]
}}

Text:
{chunk_text}"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are an expert at extracting entities and relationships from text. Return only valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3
    )
    
    # Parse the response
    content = response.choices[0].message.content.strip()
    
    # Remove markdown code blocks if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    
    result = json.loads(content)
    return result


def store_in_neo4j(entities_and_relationships: Dict[str, Any], chunk_id: str = None) -> bool:
    """
    Store extracted entities and relationships in Neo4jGraphStore.
    
    Args:
        entities_and_relationships: Dict with "entities" and "relationships"
        chunk_id: Optional ID for the chunk/source
        
    Returns:
        True if successful, False otherwise
    """
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            # Store entities as nodes
            for entity in entities_and_relationships.get("entities", []):
                cypher = """
                MERGE (e:Entity {
                    name: $name,
                    type: $type
                })
                SET e.description = $description,
                    e.updated_at = datetime()
                RETURN e
                """
                
                session.run(
                    cypher,
                    name=entity.get("name"),
                    type=entity.get("type"),
                    description=entity.get("description")
                )
                print(f"✅ Created entity: {entity.get('name')} ({entity.get('type')})")
            
            # Store relationships
            for relationship in entities_and_relationships.get("relationships", []):
                cypher = """
                MATCH (source:Entity {name: $source_name})
                MATCH (target:Entity {name: $target_name})
                MERGE (source)-[r:RELATED {relation: $relation}]->(target)
                SET r.description = $description,
                    r.updated_at = datetime()
                RETURN r
                """
                
                try:
                    session.run(
                        cypher,
                        source_name=relationship.get("source"),
                        target_name=relationship.get("target"),
                        relation=relationship.get("relation"),
                        description=relationship.get("description")
                    )
                    print(f"✅ Created relationship: {relationship.get('source')} -[{relationship.get('relation')}]-> {relationship.get('target')}")
                except Exception as e:
                    print(f"⚠️  Could not create relationship: {str(e)}")
            
            print("\n✅ Successfully stored entities and relationships in Neo4j")
            return True
    
    except Exception as e:
        print(f"❌ Error storing in Neo4j: {str(e)}")
        return False
    
    finally:
        driver.close()


def extract_and_store(chunk_text: str, chunk_id: str = None) -> Dict[str, Any]:
    """
    Extract entities and relationships from text and store in Neo4j.
    
    Args:
        chunk_text: The text to process
        chunk_id: Optional ID for tracking the source
        
    Returns:
        Dict with extracted entities and relationships
    """
    
    print(f"\n📝 Processing text chunk...")
    print(f"📊 Extracting entities and relationships using OpenAI...")
    
    # Extract using OpenAI
    result = extract_entities_and_relationships(chunk_text)
    
    print(f"✅ Found {len(result.get('entities', []))} entities")
    print(f"✅ Found {len(result.get('relationships', []))} relationships")
    
    # Store in Neo4j
    print(f"\n💾 Storing in Neo4jGraphStore...")
    store_in_neo4j(result, chunk_id)
    
    return result


# Example usage
if __name__ == "__main__":
    # Example text
    sample_text = """
    Hotel Appointment Booking Website 
Objective 
Provide a simple way for users to book a hotel appointment online. 
Target Users 
Hotel guests 
Hotel admin/staff 
Core Features 
Home page with hotel details and book appointment button 
Appointment booking form with name, contact, date, time, and number of guests 
Booking confirmation message after submission 
Admin login to view all bookings 
Non-Functional Requirements 
Responsive on mobile and desktop 
Fast and simple user interface 
Basic form validation 
Out of Scope 
Online payments 
User accounts 
Room selection 
Reviews and ratings 
Success Criteria 
Users can complete a booking quickly 
Admin can easily view booking details
    """
    
    print("="*60)
    print("ENTITY EXTRACTION AND NEO4J STORAGE")
    print("="*60)
    
    # Extract and store
    result = extract_and_store(sample_text, chunk_id="sample_001")
    
    # Print results
    print("\n" + "="*60)
    print("EXTRACTED ENTITIES AND RELATIONSHIPS")
    print("="*60)
    print(json.dumps(result, indent=2))
