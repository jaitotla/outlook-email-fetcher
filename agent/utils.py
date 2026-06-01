"""
OpenMailBot Inbuilt Mode Utilities
==================================

This module provides the core functions for "inbuilt" mode - a zero-configuration
option for tenants who want to use the central hosted LLM and embedding services
without providing their own API keys.

INBUILT MODE SERVERS:
- FLASK_URL: Central Flask server providing /chat and /embed endpoints
- OLLAMA_URL: Central Ollama server for direct LLM access

These URLs should be configured per-tenant deployment. For managed multi-tenant,
each tenant's agent container sets these via environment variables.

Usage:
    from utils import call_chat_api, call_embed_api, ollama_generate_chat
    
    # Generate text response
    response = call_chat_api("What is the summary of this email?")
    
    # Generate embedding
    embedding = call_embed_api("Email content to embed")
    
    # Direct Ollama call with specific model
    response = ollama_generate_chat("Your prompt", model="llama3.2")
"""
import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# INBUILT MODE CONFIGURATION
# Secret URLs MUST be configured via .env file for security.
# Localhost URLs have defaults for local development.
# =============================================================================

def _load_required_env(key: str, description: str) -> str:
    """
    Load a required environment variable or raise an error.
    
    Args:
        key: Environment variable name
        description: Human-readable description for error message
        
    Raises:
        ValueError: If environment variable is not set
    """
    value = os.environ.get(key)
    if not value:
        raise ValueError(
            f"\n❌ ERROR: Required environment variable '{key}' not found in .env file.\n"
            f"   This is needed for: {description}\n"
            f"   Please add to .env file:\n"
            f"   {key}=<your-{description.lower()}>\n"
        )
    return value.strip()  # Remove whitespace

# Central Flask server URL (REQUIRED - provides /chat and /embed endpoints)
FLASK_URL = _load_required_env(
    "INBUILT_FLASK_URL",
    "Central Flask server for LLM and embedding services"
)

# Flask local fallback (optional - for local development)
FLASK_LOCAL = os.environ.get("INBUILT_FLASK_LOCAL", "http://localhost:5050/")

# Use FLASK_URL by default, can be overridden
ollama_flask = os.environ.get("INBUILT_OLLAMA_FLASK", FLASK_URL)

# Direct Ollama server URL (localhost default for local deployments)
ollama_url = os.environ.get("INBUILT_OLLAMA_URL", "http://localhost:11434/")

# =============================================================================
# INBUILT LLM FUNCTIONS
# =============================================================================

def call_chat_api(prompt, timeout_seconds=300):
    """
    Calls the /chat endpoint of the Ollama Flask API.
    Returns the response or error dict.

    Args:
        prompt: The prompt text to send to the LLM
        timeout_seconds: Request timeout (default 300 seconds)
    """
    url = ollama_flask.rstrip('/') + '/chat'
    try:
        res = requests.post(url, json={"prompt": prompt}, timeout=timeout_seconds)
        res.raise_for_status()
        data = res.json()
        if "response" in data:
            return data["response"]
        return data
    except Exception as e:
        return {"error": str(e)}


def call_embed_api(text):
    """
    Call the /embed endpoint of the inbuilt Flask API.
    
    Generates embeddings for text using the central embedding service.
    The embedding model and dimension are configured server-side.
    
    Args:
        text: The text to generate embeddings for
    
    Returns:
        list: The embedding vector (list of floats)
        dict: Error dict with 'error' key if something went wrong
    """
    url = ollama_flask.rstrip('/') + '/embed'
    try:
        res = requests.post(url, json={"text": text})
        res.raise_for_status()
        data = res.json()
        if "embedding" in data:
            return data["embedding"]
        return data
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# DIRECT OLLAMA ACCESS
# =============================================================================

def ollama_generate_chat(prompt, ollama_model="llama3.2"):
    """
    Direct call to Ollama's /api/generate endpoint.
    
    Use this for direct Ollama access with specific model selection,
    bypassing the Flask wrapper. Useful for local deployments or
    when you need a specific model not available via Flask.
    
    Args:
        prompt: The prompt text
        ollama_model: Model name (default "llama3.2")
    
    Returns:
        str: The generated response
        str: Error message if something went wrong (starts with "Error:")
    """
    try:
        res = requests.post(f"{ollama_url}/api/generate", json={
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "1h"
        })
        res.raise_for_status()
        response_json = res.json()
        return response_json.get('response', '').strip()
    except requests.RequestException as e:
        print(f"Request error in ollama_generate_chat: {e}")
        return f"Error: {e}"
    except Exception as e:
        print(f"Unexpected error in ollama_generate_chat: {e}")
        return f"Error: {e}"


# =============================================================================
# OPENAI RESPONSES API (for gpt-5-mini and newer models)
# =============================================================================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()  # Optional, may use other providers
OPENAI_API_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-5-mini"


def openai_generate_chat(prompt, comment):
    """
    Call OpenAI Responses API for gpt-5-mini and newer models.
    
    This uses the newer /v1/responses endpoint format required
    by gpt-5 series models.
    
    Args:
        prompt: System prompt
        comment: User message
    
    Returns:
        str: The generated response text
        str: Error message if something went wrong
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY not configured"
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": comment}
        ]
    }
    print("ready to call openai", len(comment))

    try:
        response = requests.post(OPENAI_API_URL, headers=headers, json=data)

        if response.status_code == 429:
            raise Exception("Rate limit reached")

        response.raise_for_status()
        resp_json = response.json()
        return resp_json["output"][1]["content"][0]["text"]

    except requests.RequestException as e:
        print(f"Request error in openai_generate_chat: {e}")
        print(response.text if response else "")
        return f"Error: {e}"
    except Exception as e:
        print(f"Unexpected error in openai_generate_chat: {e}")
        return f"Error: {e}"