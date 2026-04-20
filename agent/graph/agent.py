import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from neo4j import GraphDatabase
import json

neo4j_driver_swapnil = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "neo4j+s://e5c7fa42.databases.neo4j.io"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "xR15egCk9mX8Tf4Xo1Wf_Z355rINJ7iO-uyZyx_1T8k"))
)

neo4j_driver_ankit = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "neo4j+s://49d30f90.databases.neo4j.io"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "FIdaz6r8IFSIb9yIELw--5lhHT_M4MRxD80ChOuF2Cg"))
)






# ============= NEO4J TOOLS =============

def execute_cypher_query(query: str, parameters: dict = None, user_id: str = None) -> List[Dict]:
    """Execute a Cypher query on Neo4j database.
    
    Args:
        query: Cypher query string
        parameters: Query parameters dictionary
        user_id: User identifier to determine which driver to use
    """
    
    # Select driver based on user_id
    if user_id == "patilswapnil5090@gmail.com":
        driver = neo4j_driver_ankit
    else:
        driver = neo4j_driver_ankit
    
    with driver.session() as session:
        result = session.run(query, parameters or {})
        return [record.data() for record in result]


def create_thread_node(thread_id: str, participants: List[str], subject: str, user_id: str = None) -> Dict:
    """
    Create or update a thread node in the graph.
    
    Args:
        thread_id: Unique thread identifier
        participants: List of email addresses involved
        subject: Email subject line
        user_id: User identifier
    """
    query = """
    MERGE (t:Thread {thread_id: $thread_id})
    SET t.participants = $participants,
        t.subject = $subject,
        t.updated_at = timestamp()
    RETURN t
    """
    params = {
        "thread_id": thread_id,
        "participants": participants,
        "subject": subject
    }
    return execute_cypher_query(query, params, user_id)


def create_person_node(email: str, name: str = None, user_id: str = None) -> Dict:
    """
    Create or update a person node.
    
    Args:
        email: Person's email address
        name: Person's name (optional)
        user_id: User identifier
    """
    query = """
    MERGE (p:Person {email: $email})
    SET p.name = COALESCE($name, p.name)
    RETURN p
    """
    params = {"email": email, "name": name}
    return execute_cypher_query(query, params, user_id)


def create_topic_node(topic_name: str, subtopic_name: str = None, user_id: str = None) -> Dict:
    """
    Create or update topic and optionally subtopic nodes.
    
    Args:
        topic_name: Main topic name
        subtopic_name: Subtopic name (optional)
        user_id: User identifier
    """
    if subtopic_name:
        query = """
        MERGE (topic:Topic {name: $topic_name})
        MERGE (subtopic:Subtopic {name: $subtopic_name})
        MERGE (topic)-[:HAS_SUBTOPIC]->(subtopic)
        RETURN topic, subtopic
        """
        params = {"topic_name": topic_name, "subtopic_name": subtopic_name}
    else:
        query = """
        MERGE (topic:Topic {name: $topic_name})
        RETURN topic
        """
        params = {"topic_name": topic_name}
    
    return execute_cypher_query(query, params, user_id)


def create_attachment_node(attachment_id: str, summary: str, thread_id: str, user_id: str = None) -> Dict:
    """
    Create attachment node and link to thread.
    
    Args:
        attachment_id: Unique attachment identifier
        summary: Summary of the attachment content
        thread_id: Thread this attachment belongs to
        user_id: User identifier
    """
    query = """
    MATCH (t:Thread {thread_id: $thread_id})
    MERGE (a:Attachment {attachment_id: $attachment_id})
    SET a.summary = $summary
    MERGE (t)-[:HAS_ATTACHMENT]->(a)
    RETURN a
    """
    params = {
        "attachment_id": attachment_id,
        "summary": summary,
        "thread_id": thread_id
    }
    return execute_cypher_query(query, params, user_id)


def create_subject_matter_node(subject_matter: str, user_id: str = None) -> Dict:
    """
    Create or update a subject matter node.
    
    Args:
        subject_matter: One-line summary describing the main subject of the email
        user_id: User identifier
    """
    query = """
    MERGE (sm:SubjectMatter {summary: $subject_matter})
    RETURN sm
    """
    params = {"subject_matter": subject_matter}
    return execute_cypher_query(query, params, user_id)


def link_thread_to_subject_matter(thread_id: str, subject_matter: str, user_id: str = None) -> Dict:
    """
    Create relationship between thread and subject matter.
    
    Args:
        thread_id: Thread identifier
        subject_matter: Subject matter summary to link
        user_id: User identifier
    """
    query = """
    MATCH (t:Thread {thread_id: $thread_id})
    MATCH (sm:SubjectMatter {summary: $subject_matter})
    MERGE (t)-[:HAS_SUBJECT_MATTER]->(sm)
    RETURN t, sm
    """
    params = {"thread_id": thread_id, "subject_matter": subject_matter}
    return execute_cypher_query(query, params, user_id)


def link_thread_to_topic(thread_id: str, topic_name: str, subtopic_name: str = None, user_id: str = None, message_id: str = None, timestamp: str = None) -> Dict:
    """
    Create relationship between thread and topic/subtopic with message metadata.
    
    Args:
        thread_id: Thread identifier
        topic_name: Topic name
        subtopic_name: Subtopic name (optional)
        user_id: User identifier
        message_id: Message identifier (optional)
        timestamp: Message timestamp (optional)
    """
    if subtopic_name:
        query = """
        MATCH (t:Thread {thread_id: $thread_id})
        MATCH (topic:Topic {name: $topic_name})
        MATCH (subtopic:Subtopic {name: $subtopic_name})
        MERGE (t)-[r1:DISCUSSES]->(topic)
        SET r1.message_id = COALESCE(r1.message_id, $message_id),
            r1.timestamp = COALESCE(r1.timestamp, $timestamp)
        MERGE (t)-[r2:DISCUSSES]->(subtopic)
        SET r2.message_id = COALESCE(r2.message_id, $message_id),
            r2.timestamp = COALESCE(r2.timestamp, $timestamp)
        RETURN t, topic, subtopic
        """
        params = {"thread_id": thread_id, "topic_name": topic_name, "subtopic_name": subtopic_name, "message_id": message_id, "timestamp": timestamp}
    else:
        query = """
        MATCH (t:Thread {thread_id: $thread_id})
        MATCH (topic:Topic {name: $topic_name})
        MERGE (t)-[r:DISCUSSES]->(topic)
        SET r.message_id = COALESCE(r.message_id, $message_id),
            r.timestamp = COALESCE(r.timestamp, $timestamp)
        RETURN t, topic
        """
        params = {"thread_id": thread_id, "topic_name": topic_name, "message_id": message_id, "timestamp": timestamp}
    
    return execute_cypher_query(query, params, user_id)


def create_category_node(category_name: str, user_id: str = None) -> Dict:
    """
    Create or update a category node.
    
    Args:
        category_name: Category name
        user_id: User identifier
    """
    query = """
    MERGE (c:Category {name: $category_name})
    RETURN c
    """
    params = {"category_name": category_name}
    return execute_cypher_query(query, params, user_id)


def link_thread_to_category(thread_id: str, category_name: str, user_id: str = None) -> Dict:
    """
    Create relationship between thread and category.
    
    Args:
        thread_id: Thread identifier
        category_name: Category name
        user_id: User identifier
    """
    query = """
    MATCH (t:Thread {thread_id: $thread_id})
    MATCH (c:Category {name: $category_name})
    MERGE (t)-[:BELONGS_TO]->(c)
    RETURN t, c
    """
    params = {"thread_id": thread_id, "category_name": category_name}
    return execute_cypher_query(query, params, user_id)


def link_topic_to_subtopic(topic_name: str, subtopic_name: str, user_id: str = None, message_id: str = None, timestamp: str = None) -> Dict:
    """
    Create relationship between topic and subtopic with message metadata.
    
    Args:
        topic_name: Topic name
        subtopic_name: Subtopic name
        user_id: User identifier
        message_id: Message identifier (optional)
        timestamp: Message timestamp (optional)
    """
    query = """
    MATCH (topic:Topic {name: $topic_name})
    MATCH (subtopic:Subtopic {name: $subtopic_name})
    MERGE (topic)-[r:HAS_SUBTOPIC]->(subtopic)
    SET r.message_id = COALESCE(r.message_id, $message_id),
        r.timestamp = COALESCE(r.timestamp, $timestamp)
    RETURN topic, subtopic
    """
    params = {"topic_name": topic_name, "subtopic_name": subtopic_name, "message_id": message_id, "timestamp": timestamp}
    return execute_cypher_query(query, params, user_id)


def link_person_to_thread(email: str, thread_id: str, role: str = "PARTICIPANT", user_id: str = None) -> Dict:
    """
    Create relationship between person and thread.
    
    Args:
        email: Person's email
        thread_id: Thread identifier
        role: Relationship type (PARTICIPANT, SENDER, RECIPIENT)
        user_id: User identifier
    """
    query = f"""
    MATCH (p:Person {{email: $email}})
    MATCH (t:Thread {{thread_id: $thread_id}})
    MERGE (p)-[r:{role}]->(t)
    RETURN p, t, r
    """
    params = {"email": email, "thread_id": thread_id}
    return execute_cypher_query(query, params, user_id)


def get_existing_topics(user_id: str = None) -> List[str]:
    """Retrieve all existing topics from the database.
    
    Args:
        user_id: User identifier
    """
    query = "MATCH (t:Topic) RETURN t.name as topic"
    results = execute_cypher_query(query, user_id=user_id)
    return [r["topic"] for r in results if r.get("topic")]


def get_existing_subtopics(user_id: str = None) -> List[str]:
    """Retrieve all existing subtopics from the database.
    
    Args:
        user_id: User identifier
    """
    query = "MATCH (s:Subtopic) RETURN s.name as subtopic"
    results = execute_cypher_query(query, user_id=user_id)
    return [r["subtopic"] for r in results if r.get("subtopic")]


def search_threads_by_topic(topic_name: str, user_id: str = None) -> List[Dict]:
    """
    Retrieve threads related to a specific topic.
    
    Args:
        topic_name: Topic to search for
        user_id: User identifier
    """
    query = """
    MATCH (t:Thread)-[:DISCUSSES]->(topic:Topic {name: $topic_name})
    OPTIONAL MATCH (t)-[:DISCUSSES]->(subtopic:Subtopic)
    OPTIONAL MATCH (person:Person)-[:PARTICIPANT]->(t)
    RETURN t.thread_id as thread_id, 
           t.subject as subject,
           t.participants as participants,
           collect(DISTINCT subtopic.name) as subtopics,
           collect(DISTINCT person.email) as people
    """
    params = {"topic_name": topic_name}
    return execute_cypher_query(query, params, user_id)


def search_threads_by_person(email: str, user_id: str = None) -> List[Dict]:
    """
    Retrieve threads involving a specific person.
    
    Args:
        email: Person's email address
        user_id: User identifier
    """
    query = """
    MATCH (p:Person {email: $email})-[:PARTICIPANT]->(t:Thread)
    OPTIONAL MATCH (t)-[:DISCUSSES]->(topic:Topic)
    OPTIONAL MATCH (t)-[:DISCUSSES]->(subtopic:Subtopic)
    RETURN t.thread_id as thread_id,
           t.subject as subject,
           collect(DISTINCT topic.name) as topics,
           collect(DISTINCT subtopic.name) as subtopics
    """
    params = {"email": email}
    return execute_cypher_query(query, params, user_id)


def search_complex_query(query_text: str, user_id: str = None) -> List[Dict]:
    """
    Execute a natural language query converted to Cypher.
    
    Args:
        query_text: Natural language query
        user_id: User identifier
    """
    # This is a placeholder - you'd use LLM to convert natural language to Cypher
    # For now, return a simple search
    query = """
    MATCH (t:Thread)
    WHERE t.subject CONTAINS $query_text
    OPTIONAL MATCH (t)-[:DISCUSSES]->(topic:Topic)
    RETURN t.thread_id as thread_id, 
           t.subject as subject,
           collect(DISTINCT topic.name) as topics
    LIMIT 10
    """
    params = {"query_text": query_text}
    return execute_cypher_query(query, params, user_id)

