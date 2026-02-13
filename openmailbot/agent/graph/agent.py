import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from neo4j import GraphDatabase
import json

key="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"
# Initialize clients
# Initialize clients
openai_client = OpenAI(api_key=key)
neo4j_driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "neo4j+s://e5c7fa42.databases.neo4j.io"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "xR15egCk9mX8Tf4Xo1Wf_Z355rINJ7iO-uyZyx_1T8k"))
)







# ============= NEO4J TOOLS =============

def execute_cypher_query(query: str, parameters: dict = None) -> List[Dict]:
    """Execute a Cypher query on Neo4j database."""
    with neo4j_driver.session() as session:
        result = session.run(query, parameters or {})
        return [record.data() for record in result]


def create_thread_node(thread_id: str, participants: List[str], subject: str) -> Dict:
    """
    Create or update a thread node in the graph.
    
    Args:
        thread_id: Unique thread identifier
        participants: List of email addresses involved
        subject: Email subject line
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
    return execute_cypher_query(query, params)


def create_person_node(email: str, name: str = None) -> Dict:
    """
    Create or update a person node.
    
    Args:
        email: Person's email address
        name: Person's name (optional)
    """
    query = """
    MERGE (p:Person {email: $email})
    SET p.name = COALESCE($name, p.name)
    RETURN p
    """
    params = {"email": email, "name": name}
    return execute_cypher_query(query, params)


def create_topic_node(topic_name: str, subtopic_name: str = None) -> Dict:
    """
    Create or update topic and optionally subtopic nodes.
    
    Args:
        topic_name: Main topic name
        subtopic_name: Subtopic name (optional)
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
    
    return execute_cypher_query(query, params)


def create_attachment_node(attachment_id: str, summary: str, thread_id: str) -> Dict:
    """
    Create attachment node and link to thread.
    
    Args:
        attachment_id: Unique attachment identifier
        summary: Summary of the attachment content
        thread_id: Thread this attachment belongs to
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
    return execute_cypher_query(query, params)


def link_thread_to_topic(thread_id: str, topic_name: str, subtopic_name: str = None) -> Dict:
    """
    Create relationship between thread and topic/subtopic.
    
    Args:
        thread_id: Thread identifier
        topic_name: Topic name
        subtopic_name: Subtopic name (optional)
    """
    if subtopic_name:
        query = """
        MATCH (t:Thread {thread_id: $thread_id})
        MATCH (topic:Topic {name: $topic_name})
        MATCH (subtopic:Subtopic {name: $subtopic_name})
        MERGE (t)-[:DISCUSSES]->(topic)
        MERGE (t)-[:DISCUSSES]->(subtopic)
        RETURN t, topic, subtopic
        """
        params = {"thread_id": thread_id, "topic_name": topic_name, "subtopic_name": subtopic_name}
    else:
        query = """
        MATCH (t:Thread {thread_id: $thread_id})
        MATCH (topic:Topic {name: $topic_name})
        MERGE (t)-[:DISCUSSES]->(topic)
        RETURN t, topic
        """
        params = {"thread_id": thread_id, "topic_name": topic_name}
    
    return execute_cypher_query(query, params)


def create_category_node(category_name: str) -> Dict:
    """
    Create or update a category node.
    
    Args:
        category_name: Category name
    """
    query = """
    MERGE (c:Category {name: $category_name})
    RETURN c
    """
    params = {"category_name": category_name}
    return execute_cypher_query(query, params)


def link_thread_to_category(thread_id: str, category_name: str) -> Dict:
    """
    Create relationship between thread and category.
    
    Args:
        thread_id: Thread identifier
        category_name: Category name
    """
    query = """
    MATCH (t:Thread {thread_id: $thread_id})
    MATCH (c:Category {name: $category_name})
    MERGE (t)-[:BELONGS_TO]->(c)
    RETURN t, c
    """
    params = {"thread_id": thread_id, "category_name": category_name}
    return execute_cypher_query(query, params)


def link_topic_to_subtopic(topic_name: str, subtopic_name: str) -> Dict:
    """
    Create relationship between topic and subtopic.
    
    Args:
        topic_name: Topic name
        subtopic_name: Subtopic name
    """
    query = """
    MATCH (topic:Topic {name: $topic_name})
    MATCH (subtopic:Subtopic {name: $subtopic_name})
    MERGE (topic)-[:HAS_SUBTOPIC]->(subtopic)
    RETURN topic, subtopic
    """
    params = {"topic_name": topic_name, "subtopic_name": subtopic_name}
    return execute_cypher_query(query, params)


def link_person_to_thread(email: str, thread_id: str, role: str = "PARTICIPANT") -> Dict:
    """
    Create relationship between person and thread.
    
    Args:
        email: Person's email
        thread_id: Thread identifier
        role: Relationship type (PARTICIPANT, SENDER, RECIPIENT)
    """
    query = f"""
    MATCH (p:Person {{email: $email}})
    MATCH (t:Thread {{thread_id: $thread_id}})
    MERGE (p)-[r:{role}]->(t)
    RETURN p, t, r
    """
    params = {"email": email, "thread_id": thread_id}
    return execute_cypher_query(query, params)


def get_existing_topics() -> List[str]:
    """Retrieve all existing topics from the database."""
    query = "MATCH (t:Topic) RETURN t.name as topic"
    results = execute_cypher_query(query)
    return [r["topic"] for r in results if r.get("topic")]


def get_existing_subtopics() -> List[str]:
    """Retrieve all existing subtopics from the database."""
    query = "MATCH (s:Subtopic) RETURN s.name as subtopic"
    results = execute_cypher_query(query)
    return [r["subtopic"] for r in results if r.get("subtopic")]


def search_threads_by_topic(topic_name: str) -> List[Dict]:
    """
    Retrieve threads related to a specific topic.
    
    Args:
        topic_name: Topic to search for
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
    return execute_cypher_query(query, params)


def search_threads_by_person(email: str) -> List[Dict]:
    """
    Retrieve threads involving a specific person.
    
    Args:
        email: Person's email address
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
    return execute_cypher_query(query, params)


def search_complex_query(query_text: str) -> List[Dict]:
    """
    Execute a natural language query converted to Cypher.
    
    Args:
        query_text: Natural language query
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
    return execute_cypher_query(query, params)


# ============= LLM AGENT =============

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_thread_node",
            "description": "Create or update a thread node in the graph database",
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Unique thread identifier"},
                    "participants": {"type": "array", "items": {"type": "string"}, "description": "List of participant emails"},
                    "subject": {"type": "string", "description": "Email subject line"}
                },
                "required": ["thread_id", "participants", "subject"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_category_node",
            "description": "Create or update a category node",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {"type": "string", "description": "Category name"}
                },
                "required": ["category_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_person_node",
            "description": "Create or update a person node",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Person's email address"},
                    "name": {"type": "string", "description": "Person's name"}
                },
                "required": ["email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_topic_node",
            "description": "Create or update topic and subtopic nodes",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_name": {"type": "string", "description": "Main topic name"},
                    "subtopic_name": {"type": "string", "description": "Subtopic name (optional)"}
                },
                "required": ["topic_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_attachment_node",
            "description": "Create attachment node and link to thread",
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {"type": "string", "description": "Unique attachment identifier"},
                    "summary": {"type": "string", "description": "Summary of attachment content"},
                    "thread_id": {"type": "string", "description": "Thread ID this attachment belongs to"}
                },
                "required": ["attachment_id", "summary", "thread_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "link_thread_to_topic",
            "description": "Create relationship between thread and topic/subtopic",
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Thread identifier"},
                    "topic_name": {"type": "string", "description": "Topic name"},
                    "subtopic_name": {"type": "string", "description": "Subtopic name (optional)"}
                },
                "required": ["thread_id", "topic_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "link_thread_to_category",
            "description": "Create relationship between thread and category",
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Thread identifier"},
                    "category_name": {"type": "string", "description": "Category name"}
                },
                "required": ["thread_id", "category_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "link_topic_to_subtopic",
            "description": "Create relationship between topic and subtopic",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_name": {"type": "string", "description": "Topic name"},
                    "subtopic_name": {"type": "string", "description": "Subtopic name"}
                },
                "required": ["topic_name", "subtopic_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "link_person_to_thread",
            "description": "Create relationship between person and thread",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Person's email"},
                    "thread_id": {"type": "string", "description": "Thread identifier"},
                    "role": {"type": "string", "enum": ["PARTICIPANT", "SENDER", "RECIPIENT"], "description": "Relationship type"}
                },
                "required": ["email", "thread_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_existing_topics",
            "description": "Get all existing topics from the database",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_existing_subtopics",
            "description": "Get all existing subtopics from the database",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_threads_by_topic",
            "description": "Search for threads related to a specific topic",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_name": {"type": "string", "description": "Topic to search for"}
                },
                "required": ["topic_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_threads_by_person",
            "description": "Search for threads involving a specific person",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Person's email address"}
                },
                "required": ["email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_complex_query",
            "description": "Execute a natural language search query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_text": {"type": "string", "description": "Natural language query"}
                },
                "required": ["query_text"]
            }
        }
    }
]

AVAILABLE_FUNCTIONS = {
    "create_thread_node": create_thread_node,
    #"create_person_node": create_person_node,
    "create_topic_node": create_topic_node,
    "create_category_node": create_category_node,
    "create_attachment_node": create_attachment_node,
    "link_thread_to_topic": link_thread_to_topic,
    "link_thread_to_category": link_thread_to_category,
    "link_topic_to_subtopic": link_topic_to_subtopic,
    #"link_person_to_thread": link_person_to_thread,
    "get_existing_topics": get_existing_topics,
    "get_existing_subtopics": get_existing_subtopics,
    "search_threads_by_topic": search_threads_by_topic,
    #"search_threads_by_person": search_threads_by_person,
    "search_complex_query": search_complex_query
}


def process_email_thread(email_thread_json: str) -> Dict[str, Any]:
    """
    Process an email thread and store it in the graph database using LLM agent.
    
    Args:
        email_thread_json: JSON string containing email thread data
    
    Returns:
        Processing result with status and details
    """
    messages = [
        {
            "role": "system",
            "content": """You are an email analysis agent that extracts information and stores it in a Neo4j graph database.

Your tasks:
1. Extract thread information (id, participants, subject)
2. Extract person information (emails, names)
3. Analyze the email content and determine:
   - Main topics being discussed
   - Subtopics if applicable
4. Check existing topics/subtopics before creating new ones
5. Identify any attachments mentioned (create IDs and summaries)
6. Create all necessary nodes and relationships

Process:
1. First, get existing topics and subtopics
2. Analyze if new topics/subtopics are needed
3. Create nodes for thread, people, topics, attachments
4. Create all relationships

Be thorough and create a complete graph representation of the email thread."""
        },
        {
            "role": "user",
            "content": f"Process this email thread and store it in the graph database:\n\n{email_thread_json}"
        }
    ]
    
    response = openai_client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )
    
    # Execute tool calls iteratively
    max_iterations = 20
    iteration = 0
    
    while iteration < max_iterations:
        response_message = response.choices[0].message
        
        # Append assistant message as dict to ensure proper serialization
        messages.append({
            "role": "assistant",
            "content": response_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in (response_message.tool_calls or [])
            ] if response_message.tool_calls else None
        })
        
        if not response_message.tool_calls:
            break
        
        # Execute all tool calls and collect responses
        tool_results_added = 0
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"Calling: {function_name} with args: {function_args}")
            
            function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
            if function_to_call:
                try:
                    function_response = function_to_call(**function_args)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps(function_response)
                    })
                    tool_results_added += 1
                except Exception as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps({"error": str(e)})
                    })
                    tool_results_added += 1
            else:
                # Function not found, still add error response
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps({"error": f"Function {function_name} not found"})
                })
                tool_results_added += 1
        
        # Only make next API call if we added tool results
        if tool_results_added > 0:
            response = openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )
        
        iteration += 1
    
    final_message = response.choices[0].message.content
    return {
        "status": "success",
        "message": final_message,
        "iterations": iteration
    }


def retrieve_information(query: str) -> Dict[str, Any]:
    """
    Retrieve information from the graph database using natural language query.
    
    Args:
        query: Natural language query
    
    Returns:
        Retrieved information
    """
    messages = [
        {
            "role": "system",
            "content": """You are an information retrieval agent for email thread data stored in Neo4j.

You can search for:
- Threads by topic
- Threads by person
- Complex queries

Use the available search functions to retrieve the requested information."""
        },
        {
            "role": "user",
            "content": query
        }
    ]
    
    response = openai_client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )
    
    # Execute tool calls
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        response_message = response.choices[0].message
        messages.append(response_message)
        
        if not response_message.tool_calls:
            break
        
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
            if function_to_call:
                try:
                    function_response = function_to_call(**function_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps(function_response)
                    })
                except Exception as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps({"error": str(e)})
                    })
        
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        
        iteration += 1
    
    return {
        "status": "success",
        "answer": response.choices[0].message.content
    }


# ============= MAIN EXECUTION =============

if __name__ == "__main__":
    # Example email thread (from your document)
    email_thread = """
   {
  "thread_id": "19bec1a232b8af9c",
  "user_id": "ankitgoel2004@gmail.com",
  "messages": [
    {
      "message_id": "19bec1a232b8af9c",
      "from": "Jayne Taylor <jayne@theapollogroup.com>",
      "to": [
        "Ankit Goel <ankitgoel2004@gmail.com>"
      ],
      "subject": "Information Update Requirement",
      "timestamp": "2026-01-23T18:24:51.000Z",
      "body": "Hello Ankit, Please can you change the below, the office is in Barcelona, not Madrid….\r\n\r\n[cid:image001.png@01DC8C95.053A39F0]"
    },
    {
      "message_id": "19bec5a55604f761",
      "from": "Ankit Goel <ankitgoel2004@gmail.com>",
      "to": [
        "Jayne Taylor <jayne@theapollogroup.com>"
      ],
      "subject": "Re: Information Update Requirement",
      "timestamp": "2026-01-23T19:35:00.000Z",
      "body": "Hello Jayne,\r\nMadrid is now Barcelona :)"
    },
    {
      "message_id": "19bf5ede86e3dd27",
      "from": "Jayne Taylor <jayne@theapollogroup.com>",
      "to": [
        "Ankit Goel <ankitgoel2004@gmail.com>"
      ],
      "subject": "RE: Information Update Requirement",
      "timestamp": "2026-01-25T16:12:41.000Z",
      "body": "Thank you.\r\n\r\nSo we have the below. What have I missed – please confirm what else is now in place.\r\n\r\nSorted the date issue\r\nCOMPLETE - Location - WFH, Corporate Team Meeting, Multiple Ship visits. System allows you to select all 3 options\r\n\r\n- Madrid changed to Barcelona\r\nCOMPLETE - Add project is at the bottom of each box and added a new box directly underneath\r\nCOMPLETE - Multi Select Attendees\r\n\r\n- However, requires more options – see below\r\nCOMPLETE - Text box is limited to 50 words\r\n\r\n- However, please change to 100 word limit – internal discussions highlight that this is too low and is impacting the information shared\r\nAlso note below – 50/50 seen as an over count & warning given, all other counts where below the limit.\r\n[cid:image007.png@01DC8E0C.C3DC2AD0]\r\n\r\nWeekly Report\r\nTeam Meetings – multiple choice available – however, need to add more options:\r\n\r\n- Client Operations\r\n\r\n- Client Customer Experience\r\n\r\n- Client Finance\r\n\r\n- Client IT\r\n\r\n[cid:image006.png@01DC8E0B.979F0D80]\r\n\r\nThanks & Regards\r\n\r\nJayne\r\n\r\nJayne Taylor\r\nHead of Programs and Planning | BSSL 2014\r\njayne@theapollogroup.com | \r\nOffice 1.305.592.8790 | Cell 1.786.823.5916 | +44 (0)7768 172 936\r\n6950 NW 77th Ct, Miami, FL 33166, USA\r\n[cid:image003.png@01D4CF7A.080EE2A0] [cid:a1f6a7e9-884e-4763-b9ef-1799e984a32a]\r\nBSSL (2014)-ISO 14001:2015 Certified – Environmental\r\nManagement System (Certified by MSECB)\r\nReduce, Reuse, Recycle. ♻️"
    },
    {
      "message_id": "19bf8dad1f49615d",
      "from": "Ankit Goel <ankitgoel2004@gmail.com>",
      "to": [
        "Jayne Taylor <jayne@theapollogroup.com>"
      ],
      "subject": "Re: Information Update Requirement",
      "timestamp": "2026-01-26T05:50:46.000Z",
      "body": "Hello Jayne,\r\nWill get the additional options enabled by tomorrow at most.\r\n\r\nI will see about the count. I am actually testing if we can give the count\r\nas a warning pop up before submission.\r\n\r\nFor the reports dashboard page we had things planned. These will get rolled\r\nout by tomorrow morning. I had put them on hold for the weekend-\r\nTeam name works as hotlinks to get reports and summary for the complete\r\nteam.\r\nSection wise Summary should be shown for multiple sheets when selected.\r\nSummary for each report should be show - done"
    },
    {
      "message_id": "19c0e3e6d33da8dd",
      "from": "ankitgoel2004@gmail.com",
      "to": [
        "Ankit Goel <ankitgoel2004@gmail.com>"
      ],
      "subject": "Re: Information Update Requirement",
      "timestamp": "2026-01-30T09:31:38.000Z",
      "body": "Subject: Re: Information Update Requirement\r\n\r\nDear Jayne,\r\n\r\nThank you for your confirmation regarding the update requirement. I have taken note of the additional options that need to be added to the Team Meetings section, specifically Client Operations, Client Customer Experience, Client Finance, and Client IT.\r\n\r\nRegarding the count issue, I will look into implementing a warning pop-up before submission as you suggested. Additionally, I will explore the possibility of increasing the text box limit from 50 words to 100 words, as internal discussions have highlighted that this is too low and may be impacting the information shared.\r\n\r\nI am on track to enable the additional options by tomorrow at most, as promised. The reports dashboard page is also moving forward as planned, with the team name feature serving as hotlinks to get reports and summaries for the complete team. I will ensure that Section-wise Summary shows for multiple sheets when selected and summary for each report is displayed.\r\n\r\nPlease let me know if there's anything else I can assist you with in this regard."
    }
  ],
  "metadata": {
    "original_message_count": 5,
    "processed_message_count": 5,
    "stored_at": "2026-01-30T09:52:15.313915"
  }
}
    """
    
    # # Process and store email thread
    # print("Processing email thread...")
    # result = process_email_thread(email_thread)
    # print(f"Result: {result}")
    
    # Example retrieval queries
    print("\n--- Retrieval Examples ---")
    
    # Search by topic
    retrieval_result = retrieve_information("what is email about")
    print(f"Topic search: {retrieval_result}")
    
    neo4j_driver.close()