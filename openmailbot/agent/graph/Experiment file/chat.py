import requests
import json

def send_chat_request(email_body: str, query: str, include_query: bool = True) -> dict:
    """Send a chat request to the API with email body as context"""
    url = "https://lsdiedb39c.pagekite.me/chat"
    
    # Build text message with context
    if include_query:
        text = f"""Email Context:
{email_body}

Question: {query}

Instructions: Answer the question based on the email context above in a short, concise manner."""
    else:
        text = email_body
    
    payload = {
        "prompt": text
    }
    
    print(f"📤 Sending request to: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"✓ Status Code: {response.status_code}\n")
        
        try:
            response_data = response.json()
            return response_data
        except json.JSONDecodeError:
            return {"text": response.text, "status": response.status_code}
            
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Email body
    email_body = """Hello Jayaji,
I realised I had another video in mail, which we have processed. This is
stationary so we can see there is no blurring, which means it is a data
issue as the bus is moving.

With respect to our system, you will see that all the faces are identified
as they climb up and sit. While most of the time it is a side view, when
sitting the full face does get captured. We have an advanced system for
side faces which we can do a trial at a later date if needed."""
    
    # Query
    query = "Where is Camera Footage update?"
    
    # Send request
    response = send_chat_request(email_body, query)
    print("📥 Response:")
    print(json.dumps(response, indent=2))
