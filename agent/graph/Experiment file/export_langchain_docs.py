import json
import re
from pathlib import Path
from typing import List, Dict, Any

TEST_PY = Path(__file__).with_name("test.py")


def extract_credentials(path: Path):
    """Extract Neo4j credentials from test.py"""
    text = path.read_text()
    username = re.search(r'username\s*=\s*"([^"]+)"', text)
    password = re.search(r'password\s*=\s*"([^"]+)"', text)
    url = re.search(r'url\s*=\s*"([^"]+)"', text)
    database = re.search(r'database\s*=\s*"([^"]+)"', text)
    
    if not (username and password and url):
        raise RuntimeError(f"Could not extract credentials from {path}")
    
    return username.group(1), password.group(1), url.group(1), (database.group(1) if database else None)


def query_threads_and_topics(uri: str, user: str, pwd: str, database: str = None) -> List[Dict[str, Any]]:
    """Query Neo4j for all Thread nodes and their DISCUSSES relationships to Topics"""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise RuntimeError("neo4j driver not installed. Run: pip install neo4j")
    
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    threads_data = []
    
    try:
        session = driver.session(database=database) if database else driver.session()
        
        # Query threads with their properties and related topics
        query = """
        MATCH (t:Thread)
        OPTIONAL MATCH (t)-[:DISCUSSES]->(topic:Topic)
        OPTIONAL MATCH (t)-[:HAS_SUBJECT_MATTER]->(sm:SubjectMatter)
        RETURN t.thread_id as thread_id,
               t.subject as subject,
               t.participants as participants,
               t.updated_at as updated_at,
               collect(distinct topic.name) as topics,
               collect(distinct sm.summary) as subject_matters
        ORDER BY t.thread_id
        """
        
        result = session.run(query)
        for record in result:
            threads_data.append({
                "thread_id": record["thread_id"],
                "subject": record["subject"],
                "participants": record["participants"] or [],
                "updated_at": record["updated_at"],
                "topics": [t for t in (record["topics"] or []) if t],
                "subject_matters": [s for s in (record["subject_matters"] or []) if s]
            })
        
        session.close()
    finally:
        driver.close()
    
    return threads_data


def create_langchain_documents(threads_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert thread data into LangChain document format (one document per topic and subject_matter)"""
    documents = []
    
    for thread in threads_data:
        # Create documents for topics
        for topic_name in thread["topics"]:
            documents.append({
                "page_content": topic_name,
                "metadata": {
                    "topic_name": topic_name,
                    "thread_id": thread["thread_id"],
                    "node_type": "Topic"
                }
            })
        
        # Create documents for subject_matters
        for subject_matter in thread["subject_matters"]:
            documents.append({
                "page_content": subject_matter,
                "metadata": {
                    "topic_name": subject_matter,
                    "thread_id": thread["thread_id"],
                    "node_type": "SubjectMatter"
                }
            })
    
    return documents


def main():
    print("Extracting credentials from test.py...")
    user, pwd, uri, db = extract_credentials(TEST_PY)
    print(f"✓ Extracted: user={user}, database={db}")
    
    print(f"\nConnecting to Neo4j: {uri}")
    
    # First, check how many threads exist in the database
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        session = driver.session(database=db) if db else driver.session()
        count_result = session.run("MATCH (t:Thread) RETURN count(t) as count")
        total_count = count_result.single()["count"]
        print(f"📊 Total Thread nodes in database: {total_count}")
        session.close()
        driver.close()
    except Exception as e:
        print(f"⚠️  Could not count threads: {e}")
    
    threads_data = query_threads_and_topics(uri, user, pwd, database=db)
    print(f"✓ Retrieved {len(threads_data)} threads")
    
    print("\nCreating LangChain documents...")
    documents = create_langchain_documents(threads_data)
    print(f"✓ Created {len(documents)} documents")
    
    # Save to JSON
    output_file = Path(__file__).with_name("langchain_docs_ankit2.json")
    with open(output_file, "w") as f:
        json.dump(documents, f, indent=2)
    print(f"\n✓ Saved to {output_file}")
    
    # Print sample
    if documents:
        print(f"\n--- Sample Documents ---")
        # Show one topic document
        topic_samples = [d for d in documents if d.get('metadata', {}).get('node_type') == 'Topic']
        if topic_samples:
            sample = topic_samples[0]
            print(f"\nTopic Document:")
            print(f"Content: {sample['page_content']}")
            print(f"Metadata: {json.dumps(sample['metadata'], indent=2)}")
        
        # Show one subject_matter document
        sm_samples = [d for d in documents if d.get('metadata', {}).get('node_type') == 'SubjectMatter']
        if sm_samples:
            sample = sm_samples[0]
            print(f"\nSubjectMatter Document:")
            print(f"Content: {sample['subject_matter']}")
            print(f"Metadata: {json.dumps(sample['metadata'], indent=2)}")
    
    return documents


if __name__ == "__main__":
    main()
