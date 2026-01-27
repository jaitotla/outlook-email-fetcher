"""
Prompt templates for chat pipeline RAG system
Centralized prompt management for consistency across the application
"""

# System prompt for tool calling (OpenAI decision making)
TOOL_CALLING_SYSTEM_PROMPT = """You are a tool-calling email assistant. 
You help users find information in their email threads and attachments.

When a user asks a question:
1. Decide if you need to search emails, attachments, or both
2. Use the available tools to retrieve relevant information
3. Do not explain your reasoning - just call the tools

Available tools:
- search_thread_emails: Search email messages by content
- search_attachments: Search attachment content by relevance

Use tools when needed to answer the question."""


# System prompt for final answer generation (Ollama)
FINAL_ANSWER_SYSTEM_PROMPT_TEMPLATE = """You are an AI email assistant helping users understand their email threads.

Your responsibilities:
- Answer questions ONLY using the retrieved context provided
- Be precise and factual
- Mention sender, timestamp, and document names when relevant
- If information is missing from the context, say so clearly
- Keep responses concise and professional
- Maintain a helpful and conversational tone

Important Rules:
- Do NOT make up or infer information
- Do NOT use knowledge outside the provided context
- Always cite the source (email, document name, timestamp)
- If the answer requires information not in the context, explicitly state this

Thread ID: {thread_id}
User: {user_id}
Current Time: {current_time}"""


# Prompt template for combining context and generating answer
FINAL_ANSWER_USER_PROMPT_TEMPLATE = """QUESTION:
{user_question}

RETRIEVED CONTEXT:
{combined_context}

Provide a clear and accurate answer based only on the information provided in the RETRIEVED CONTEXT above.
If the context doesn't contain enough information to answer the question, say so explicitly."""


# Prompt for email search tool description
SEARCH_EMAILS_TOOL_DESCRIPTION = """Search email messages in the thread using semantic search.
Use this when you need to find specific information, discussions, or emails about a particular topic.

Args:
    query: What you're searching for in the emails (e.g., "budget discussion", "project deadline")
    k: Number of relevant emails to retrieve (default: 5, max: 10)
    
Returns:
    List of relevant email messages with sender, timestamp, and content"""


# Prompt for attachment search tool description
SEARCH_ATTACHMENTS_TOOL_DESCRIPTION = """Search attachment content using semantic search.
Use this when you need specific information from documents like PDFs, spreadsheets, or presentations.

Args:
    query: What information you're looking for in attachments (e.g., "quarterly results", "contract terms")
    k: Number of relevant chunks to retrieve (default: 3, max: 5)
    
Returns:
    List of relevant document excerpts with filenames and relevance scores"""


# Fallback prompt when no tool calls are detected
FALLBACK_SEARCH_PROMPT = """No specific tools were selected. Performing comprehensive search across both emails and attachments to answer your question."""


# Context formatting prompts
EMAIL_SEARCH_RESULTS_HEADER = "=== EMAIL SEARCH RESULTS ==="
ATTACHMENT_SEARCH_RESULTS_HEADER = "=== ATTACHMENT SEARCH RESULTS ==="
NO_EMAILS_FOUND = "No relevant emails found for your query."
NO_ATTACHMENTS_FOUND = "No relevant information found in attachments."


# Email relevance formatting
EMAIL_RESULT_TEMPLATE = """📧 Email {index} (Relevance: {relevance:.2f})
Message ID: {message_id}
From: {from_email}
Subject: {subject}
Time: {timestamp}
Content:
{content}
{separator}"""


# Attachment relevance formatting
ATTACHMENT_RESULT_TEMPLATE = """📎 Document {index} (Relevance: {relevance:.2f})
From: {filename} (chunk {chunk_index})
Content:
{content}
{separator}"""


# Processing status messages
EMAIL_PROCESSING_START = "🚀 Processing thread emails for user: {user_id}, thread: {thread_id}"
EMAIL_PROCESSING_COMPLETE = "✅ Thread processing completed: {processing_info}"
ATTACHMENT_PROCESSING_START = "📎 Processing attachments for thread {thread_id}"
ATTACHMENT_PROCESSING_SKIP = "⏭️  Skipping already processed: {attachment_id}"
MESSAGE_PROCESSED_SUCCESS = "✅ Message {message_id} processed and stored successfully"
ATTACHMENT_PROCESSED_SUCCESS = "✅ Attachment {attachment_id} processed successfully"
HYBRID_CHAT_COMPLETE = "✅ Hybrid chat pipeline completed successfully"


# Error messages
ERROR_EMBEDDING_API = "Embedding API error: {error}"
ERROR_LOADING_THREAD = "Error loading thread JSON {file_path}: {error}"
ERROR_PROCESSING_MESSAGE = "Error processing message {message_id}: {error}"
ERROR_PROCESSING_ATTACHMENT = "Error processing attachment {attachment_path}: {error}"
ERROR_READING_METADATA = "Error reading metadata file {metadata_file}: {error}"
ERROR_THREAD_PROCESSING = "Thread processing error: {error}"
ERROR_ATTACHMENT_PROCESSING = "Attachment processing error: {error}"
ERROR_PIPELINE = "Hybrid chat pipeline error: {error}"


# Warning messages
WARNING_EMPTY_CONTENT = "Empty content for message {message_id}"
WARNING_NO_THREAD_DATA = "No thread data found for thread {thread_id}"
WARNING_NO_ATTACHMENTS = "No attachments found for thread: {thread_id}"
WARNING_ATTACHMENT_PATH_NOT_FOUND = "Attachment path not found: {attachment_path}"
WARNING_NO_TOOL_CALLS = "⚠️ No tool calls detected — fallback search activated"


# Info messages
INFO_FOUND_EXISTING_MESSAGES = "Found {count} existing messages in ChromaDB for thread {thread_id}"
INFO_FOUND_THREAD_MESSAGES = "Found {count} messages in thread {thread_id}"
INFO_UNPROCESSED_MESSAGES = "Unprocessed messages: {unprocessed_count} out of {total_count}"
INFO_FOUND_ATTACHMENTS = "Found {count} attachments for thread {thread_id}"
INFO_SEARCHING_EMAILS = "🔍 Searching emails: {query}"
INFO_SEARCHING_ATTACHMENTS = "🔍 Searching attachments: {query}"
INFO_TOOL_EXECUTION = "📞 Executing tool: {tool_name} | args: {tool_args}"
INFO_CONTEXT_LENGTH = "📚 Retrieved context length: {length} characters"
INFO_OLLAMA_CALLING = "🦙 Calling Ollama for final answer generation..."
INFO_HYBRID_CHAT_START = "💬 Hybrid chat for thread {thread_id}: {user_question}"
INFO_OPENAI_RESPONSE = "🤖 OpenAI raw response: {response}"
INFO_TOOL_CALLS_DETECTED = "🛠 Tool calls detected: {tool_calls}"


# API response messages
API_CHAT_REQUEST = "Chat request: user={user_id}, thread={thread_id}, question={question}"
API_ERROR = "API error: {error}"


def get_final_answer_system_prompt(thread_id: str, user_id: str, current_time: str = None) -> str:
    """
    Generate the system prompt for final answer generation
    
    Args:
        thread_id: The thread ID
        user_id: The user ID
        current_time: Optional current time stamp
        
    Returns:
        Formatted system prompt
    """
    if current_time is None:
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return FINAL_ANSWER_SYSTEM_PROMPT_TEMPLATE.format(
        thread_id=thread_id,
        user_id=user_id,
        current_time=current_time
    )


def get_final_answer_user_prompt(user_question: str, combined_context: str) -> str:
    """
    Generate the user prompt for final answer generation
    
    Args:
        user_question: The user's question
        combined_context: The combined context from searches
        
    Returns:
        Formatted user prompt
    """
    return FINAL_ANSWER_USER_PROMPT_TEMPLATE.format(
        user_question=user_question,
        combined_context=combined_context
    )


def format_email_result(index: int, relevance: float, message_id: str, 
                       from_email: str, subject: str, timestamp: str, 
                       content: str, separator: str = "-"*80) -> str:
    """Format an email search result"""
    return EMAIL_RESULT_TEMPLATE.format(
        index=index,
        relevance=relevance,
        message_id=message_id,
        from_email=from_email,
        subject=subject,
        timestamp=timestamp,
        content=content,
        separator=separator
    )


def format_attachment_result(index: int, relevance: float, filename: str, 
                            chunk_index: str, content: str, 
                            separator: str = "-"*80) -> str:
    """Format an attachment search result"""
    return ATTACHMENT_RESULT_TEMPLATE.format(
        index=index,
        relevance=relevance,
        filename=filename,
        chunk_index=chunk_index,
        content=content,
        separator=separator
    )
