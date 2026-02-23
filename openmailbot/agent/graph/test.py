from llama_index.graph_stores.neo4j import Neo4jGraphStore
from neo4j import GraphDatabase
from typing import List, Dict, Set
import os

graph_store = Neo4jGraphStore(
    username="neo4j",
    password="FIdaz6r8IFSIb9yIELw--5lhHT_M4MRxD80ChOuF2Cg",
    url="neo4j+s://49d30f90.databases.neo4j.io",
    database="neo4j"
)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://49d30f90.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "FIdaz6r8IFSIb9yIELw--5lhHT_M4MRxD80ChOuF2Cg")


def get_all_thread_participants() -> Dict[str, any]:
    """
    Find all thread nodes, extract participants from each thread,
    combine all participants, and return the results.
    
    Returns:
        Dict containing:
        - all_threads: List of thread objects with their participants
        - combined_participants: Set of all unique participants
        - participant_count: Total unique participants
    """
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            # Query all thread nodes with their participants
            cypher = """
            MATCH (t:Thread)
            RETURN
                t.thread_id AS thread_id,
                t.subject AS subject,
                t.participants AS participants,
                t.updated_at AS updated_at,
                t.created_at AS created_at
            ORDER BY t.updated_at DESC
            """
            
            threads = []
            combined_participants: Set[str] = set()
            
            for record in session.run(cypher):
                thread_data = {
                    "thread_id": record["thread_id"],
                    "subject": record["subject"],
                    "participants": record["participants"] or [],
                    "updated_at": record["updated_at"],
                    "created_at": record["created_at"]
                }
                threads.append(thread_data)
                
                # Combine participants - handle both string and list formats
                participants = record["participants"] or []
                if isinstance(participants, str):
                    # If stored as string, parse it
                    combined_participants.add(participants)
                elif isinstance(participants, list):
                    combined_participants.update(participants)
            
            result = {
                "all_threads": threads,
                "combined_participants": sorted(list(combined_participants)),
                "participant_count": len(combined_participants),
                "thread_count": len(threads)
            }
            
            print(f"\n✅ Found {len(threads)} threads")
            print(f"✅ Combined {len(combined_participants)} unique participants")
            print(f"\nParticipants: {result['combined_participants']}")
            
            return result
    
    finally:
        driver.close()


# Run the function
if __name__ == "__main__":
    result = get_all_thread_participants()
    print("\n" + "="*50)
    print("RESULT:")
    print("="*50)
    print(f"Total threads: {result['thread_count']}")
    print(f"Total unique participants: {result['participant_count']}")
    print(f"Participants: {result['combined_participants']}")


