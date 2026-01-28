import os
import json
import requests

FLASK_URL =  "https://lsdiedb39c.pagekite.me/"
FLASK_LOCAL = "http://localhost:5050/"
ollama_flask = FLASK_LOCAL


# model being used on server side is fixed to llama3.2

def call_chat_api(prompt, timeout_seconds=300):
    """
    Calls the /chat endpoint of the Ollama Flask API.
    Returns the response or error string.
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
    Calls the /embed endpoint of the Ollama Flask API.
    Returns the embedding or error string.
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

ollama_url = 'http://localhost:11434/'
# ollama_model = "llama3.2"

def ollama_generate_chat(prompt, ollama_model = "llama3.2"):
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


OPENAI_API_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-5-mini"
def openai_generate_chat(prompt, comment):
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