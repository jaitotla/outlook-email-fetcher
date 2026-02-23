#!/usr/bin/env python3
"""
Simple test script: read a saved thread JSON and POST each message
one-by-one to the /api/label-email endpoint.

Usage:
  python agent/scripts/test_label_email_api.py
  API URL can be changed with --api-url or env API_URL
"""
import os
import json
import argparse
import urllib.request
import urllib.error


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_message_payload(msg):
    # Normalize various possible key names from saved JSON
    message_id = msg.get("message_id") or msg.get("id") or msg.get("messageId")
    from_addr = msg.get("from_address") or msg.get("from") or msg.get("fromAddress")
    to = msg.get("to") or msg.get("recipients") or []
    subject = msg.get("subject") or ""
    timestamp = msg.get("timestamp") or msg.get("date") or ""
    body = msg.get("body") or msg.get("content") or msg.get("text") or ""

    if isinstance(to, str):
        to = [to]

    return {
        "message_id": message_id,
        "from_address": from_addr,
        "to": to,
        "subject": subject,
        "timestamp": timestamp,
        "body": body,
    }


def post(api_url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.getcode(), resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return None, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://localhost:5050/api/label-email"),
        help="Full URL for the /api/label-email endpoint",
    )
    default_json = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "ankitgoel2004@gmail.com",
        "log_emails",
        "19b10f314c473626",
        "19b10f314c473626.json",
    )
    parser.add_argument("--json", default=default_json, help="Path to thread JSON file")
    parser.add_argument("--user-id", default="ankitgoel2004@gmail.com")
    parser.add_argument("--thread-id", default="19b10f314c473626")

    args = parser.parse_args()

    json_path = os.path.abspath(os.path.expanduser(args.json))
    if not os.path.exists(json_path):
        print(f"JSON file not found: {json_path}")
        return

    data = load_json(json_path)
    messages = data.get("messages") or []
    if not messages:
        print("No messages found in JSON")
        return

    print(f"Found {len(messages)} messages. Sending one-by-one to {args.api_url}")

    for i, msg in enumerate(messages, start=1):
        payload = {
            "user_id": args.user_id,
            "thread_id": args.thread_id,
            "messages": [make_message_payload(msg)],
        }

        status, body = post(args.api_url, payload)
        print(f"[{i}/{len(messages)}] status={status}")
        if body:
            print(body)

    print("Done.")


if __name__ == "__main__":
    main()
