#!/usr/bin/env python3
"""
Request logging middleware to capture ALL requests to the agent
This will help identify if the Gmail add-on is even sending requests
"""

import json
import os
from datetime import datetime

LOG_FILE = "/home/ubuntu/openmailbot/openmailbot/agent_request_log.jsonl"

def log_request(endpoint, method, user_id, thread_id, attachments_count=0, error=None):
    """Log incoming request to a file"""
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "endpoint": endpoint,
        "method": method,
        "user_id": user_id,
        "thread_id": thread_id,
        "attachments_count": attachments_count,
        "error": error
    }
    
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Failed to log request: {e}")

def read_logs(limit=20):
    """Read recent request logs"""
    if not os.path.exists(LOG_FILE):
        return []
    
    logs = []
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    logs.append(json.loads(line.strip()))
                except:
                    pass
    except Exception as e:
        print(f"Failed to read logs: {e}")
    
    return logs

if __name__ == "__main__":
    print("Recent API requests to agent:")
    print("=" * 80)
    
    logs = read_logs(20)
    
    if not logs:
        print("No requests logged yet.")
    else:
        for log in logs:
            print(f"\n[{log.get('timestamp')}]")
            print(f"  Endpoint: {log.get('endpoint')}")
            print(f"  Method: {log.get('method')}")
            print(f"  User: {log.get('user_id')}")
            print(f"  Thread: {log.get('thread_id')}")
            print(f"  Attachments: {log.get('attachments_count')}")
            if log.get('error'):
                print(f"  ❌ Error: {log.get('error')}")
    
    print("\n" + "=" * 80)
    print(f"Log file: {LOG_FILE}")
