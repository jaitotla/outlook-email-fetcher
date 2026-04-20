"""
Lock Book (Log Book) for /api/label-email endpoint
Tracks metrics: requests, labeled emails, graph storage, and timestamps
Uses JSON for fast reads/writes and structured data
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import threading


class LabelEmailLockBook:
    """
    Thread-safe lock book for tracking label-email endpoint metrics
    Stores data in JSON format for fast I/O
    """
    
    def __init__(self, user_id: str = None):
        """
        Initialize lock book
        
        Args:
            user_id: Optional user ID for user-specific metrics
        """
        self.lock = threading.Lock()
        self.user_id = user_id or "global"
        
        # Create lockbook directory
        self.lockbook_dir = Path("/home/manotr/openmailbot/openmailbot/agent/data/lockbook")
        self.lockbook_dir.mkdir(parents=True, exist_ok=True)
        
        # Lock book file path
        self.lockbook_file = self.lockbook_dir / f"label_email_metrics_{self.user_id}.json"
        
        # Initialize lock book if it doesn't exist
        if not self.lockbook_file.exists():
            self._initialize_lockbook()
    
    def _initialize_lockbook(self):
        """Initialize a new lock book with default structure"""
        default_data = {
            "user_id": self.user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
            "metrics": {
                "total_requests": 0,
                "total_labeled_emails": 0,
                "total_graph_stored": 0,
                "by_label": {}
            },
            "recent_requests": []  # Store last 100 requests
        }
        
        with self.lock:
            with open(self.lockbook_file, 'w') as f:
                json.dump(default_data, f, indent=2)
    
    def _read_lockbook(self) -> Dict[str, Any]:
        """Read lock book from JSON file"""
        with self.lock:
            try:
                with open(self.lockbook_file, 'r') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                self._initialize_lockbook()
                with open(self.lockbook_file, 'r') as f:
                    return json.load(f)
    
    def _write_lockbook(self, data: Dict[str, Any]):
        """Write lock book to JSON file"""
        with self.lock:
            with open(self.lockbook_file, 'w') as f:
                json.dump(data, f, indent=2)
    
    def log_request(self, 
                   thread_id: str,
                   label: str,
                   num_labeled: int,
                   num_graph_stored: int,
                   status: str = "SUCCESS"):
        """
        Log a label-email request
        
        Args:
            thread_id: Thread ID being labeled
            label: The label assigned
            num_labeled: Number of emails labeled
            num_graph_stored: Number of emails stored in graph DB
            status: Request status (SUCCESS, FAILED, PARTIAL)
        """
        data = self._read_lockbook()
        
        # Update metrics
        data["metrics"]["total_requests"] += 1
        data["metrics"]["total_labeled_emails"] += num_labeled
        data["metrics"]["total_graph_stored"] += num_graph_stored
        
        # Update by-label statistics
        if label not in data["metrics"]["by_label"]:
            data["metrics"]["by_label"][label] = {
                "count": 0,
                "emails_labeled": 0,
                "emails_graph_stored": 0
            }
        
        data["metrics"]["by_label"][label]["count"] += 1
        data["metrics"]["by_label"][label]["emails_labeled"] += num_labeled
        data["metrics"]["by_label"][label]["emails_graph_stored"] += num_graph_stored
        
        # Create request entry
        request_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "thread_id": thread_id,
            "label": label,
            "emails_labeled": num_labeled,
            "emails_graph_stored": num_graph_stored,
            "status": status
        }
        
        # Add to recent requests (keep last 100)
        data["recent_requests"].append(request_entry)
        if len(data["recent_requests"]) > 100:
            data["recent_requests"] = data["recent_requests"][-100:]
        
        # Update last_updated
        data["last_updated"] = datetime.utcnow().isoformat()
        
        self._write_lockbook(data)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        data = self._read_lockbook()
        return {
            "user_id": data["user_id"],
            "created_at": data["created_at"],
            "last_updated": data["last_updated"],
            "metrics": data["metrics"]
        }
    
    def get_recent_requests(self, limit: int = 20) -> list:
        """Get recent requests"""
        data = self._read_lockbook()
        return data["recent_requests"][-limit:]
    
    def get_label_stats(self, label: str = None) -> Dict[str, Any]:
        """Get statistics for a specific label or all labels"""
        data = self._read_lockbook()
        
        if label:
            return data["metrics"]["by_label"].get(label, {})
        else:
            return data["metrics"]["by_label"]
    
    def reset_metrics(self):
        """Reset all metrics (use with caution)"""
        self._initialize_lockbook()
    
    def get_summary(self) -> str:
        """Get a human-readable summary of metrics"""
        data = self._read_lockbook()
        metrics = data["metrics"]
        
        summary = f"""
╔════════════════════════════════════════════════════════════╗
║         LABEL-EMAIL LOCK BOOK SUMMARY (User: {self.user_id})
╚════════════════════════════════════════════════════════════╝

📊 Overall Metrics:
   • Total Requests: {metrics['total_requests']}
   • Total Emails Labeled: {metrics['total_labeled_emails']}
   • Total Emails Stored (Graph): {metrics['total_graph_stored']}
   • Created: {data['created_at']}
   • Last Updated: {data['last_updated']}

📌 By Label:
"""
        for label, stats in metrics['by_label'].items():
            summary += f"""   • {label.upper()}
     - Requests: {stats['count']}
     - Emails Labeled: {stats['emails_labeled']}
     - Graph Stored: {stats['emails_graph_stored']}
"""
        
        return summary


# Global lock book instance for general metrics
_global_lockbook = None

def get_global_lockbook() -> LabelEmailLockBook:
    """Get or create global lock book instance"""
    global _global_lockbook
    if _global_lockbook is None:
        _global_lockbook = LabelEmailLockBook(user_id="global")
    return _global_lockbook


def get_user_lockbook(user_id: str) -> LabelEmailLockBook:
    """Get user-specific lock book"""
    return LabelEmailLockBook(user_id=user_id)
