"""
Store Graph Database Pipeline
Simplified pipeline that stores email thread data with category, topic, subtopic
using direct tool calls: create_thread_node, create_topic_node, link_thread_to_topic
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'graph'))

from agent import (
    create_thread_node,
    create_topic_node,
    create_category_node,
    create_subject_matter_node,
    link_thread_to_topic,
    link_thread_to_category,
    link_thread_to_subject_matter,
    link_topic_to_subtopic,
)


@dataclass
class ThreadGraphData:
    """Input data for graph storage pipeline"""
    thread_id: str
    subject: str
    participants: List[str]
    category: str
    topic: str
    user_id: str
    subtopic: Optional[str] = None
    subject_matter: Optional[str] = None
    message_id: Optional[str] = None
    timestamp: Optional[str] = None


class StoreGraphPipeline:
    """
    Simple pipeline for storing email thread data in Neo4j graph database
    Uses three core tools: create_thread_node, create_topic_node, link_thread_to_topic
    """
    
    def __init__(self):
        """Initialize the graph storage pipeline"""
        self.logs = []
    
    def log(self, message: str, level: str = "INFO"):
        """
        Log a message with timestamp and level
        
        Args:
            message: Message to log
            level: Log level (INFO, SUCCESS, ERROR, WARNING)
        """
        log_entry = f"[{level}] {message}"
        self.logs.append(log_entry)
        
        # Print with icons for clarity
        if level == "SUCCESS":
            print(f"✅ {message}")
        elif level == "ERROR":
            print(f"❌ {message}")
        elif level == "WARNING":
            print(f"⚠️  {message}")
        else:
            print(f"ℹ️  {message}")
    
    def store_thread_graph(self, data: ThreadGraphData) -> Dict[str, Any]:
        """
        Main pipeline: Store thread data in graph database
        
        Executes in sequence:
        1. Create category node
        2. Create topic node for main topic
        3. Create subtopic node if provided
        4. Create thread node
        5. Link thread to category
        6. Link thread to topic
        9. Link topic to subtopic (if exists)
        10. Link thread to subtopic (if exists)
        
        Args:
            data: ThreadGraphData with thread information
            
        Returns:
            Result dictionary with status and execution details
        """
        self.logs = []
        
        print("\n" + "="*70)
        print("📦 GRAPH DATABASE STORAGE PIPELINE")
        print("="*70)
        self.log(f"Starting pipeline for thread: {data.thread_id}")
        
        results = {
            "thread_id": data.thread_id,
            "status": "pending",
            "steps": [],
            "errors": []
        }
        
        try:
            # ============= STEP 1: Create Category Node =============
            self.log(f"Step 1: Creating category node: '{data.category}'", "INFO")
            try:
                category_result = create_category_node(data.category, user_id=data.user_id)
                self.log(f"Category node created: {data.category}", "SUCCESS")
                results["steps"].append({
                    "step": 1,
                    "action": "create_category_node",
                    "input": {"category_name": data.category},
                    "result": "SUCCESS",
                    "data": category_result
                })
            except Exception as e:
                error_msg = f"Failed to create category node: {str(e)}"
                self.log(error_msg, "ERROR")
                results["errors"].append(error_msg)
                results["steps"].append({
                    "step": 1,
                    "action": "create_category_node",
                    "result": "FAILED",
                    "error": str(e)
                })
            
            # ============= STEP 2: Create Topic Node =============
            self.log(f"Step 2: Creating topic node: '{data.topic}'", "INFO")
            try:
                topic_result = create_topic_node(data.topic, user_id=data.user_id)
                self.log(f"Topic node created: {data.topic}", "SUCCESS")
                results["steps"].append({
                    "step": 2,
                    "action": "create_topic_node",
                    "input": {"topic_name": data.topic},
                    "result": "SUCCESS",
                    "data": topic_result
                })
            except Exception as e:
                error_msg = f"Failed to create topic node: {str(e)}"
                self.log(error_msg, "ERROR")
                results["errors"].append(error_msg)
                results["steps"].append({
                    "step": 2,
                    "action": "create_topic_node",
                    "result": "FAILED",
                    "error": str(e)
                })
            
            # ============= STEP 3: Create Subtopic Node (if provided) =============
            if data.subtopic:
                self.log(f"Step 3: Creating subtopic node: '{data.subtopic}'", "INFO")
                try:
                    subtopic_result = create_topic_node(data.topic, data.subtopic, user_id=data.user_id)
                    self.log(f"Subtopic node created: {data.subtopic} under {data.topic}", "SUCCESS")
                    results["steps"].append({
                        "step": 3,
                        "action": "create_topic_node",
                        "input": {"topic_name": data.topic, "subtopic_name": data.subtopic},
                        "result": "SUCCESS",
                        "data": subtopic_result
                    })
                except Exception as e:
                    error_msg = f"Failed to create subtopic node: {str(e)}"
                    self.log(error_msg, "ERROR")
                    results["errors"].append(error_msg)
                    results["steps"].append({
                        "step": 3,
                        "action": "create_topic_node",
                        "result": "FAILED",
                        "error": str(e)
                    })
            else:
                self.log("Step 3: Skipped (no subtopic provided)", "INFO")
            
            # ============= STEP 4: Create Thread Node =============
            self.log(f"Step 4: Creating/updating thread node: '{data.thread_id}'", "INFO")
            try:
                thread_result = create_thread_node(
                    thread_id=data.thread_id,
                    participants=data.participants,
                    subject=data.subject,
                    user_id=data.user_id
                )
                self.log(f"Thread node created: {data.thread_id}", "SUCCESS")
                self.log(f"   Subject: {data.subject}", "INFO")
                self.log(f"   Participants: {len(data.participants)} persons", "INFO")
                results["steps"].append({
                    "step": 4,
                    "action": "create_thread_node",
                    "input": {
                        "thread_id": data.thread_id,
                        "participants": data.participants,
                        "subject": data.subject
                    },
                    "result": "SUCCESS",
                    "data": thread_result
                })
            except Exception as e:
                error_msg = f"Failed to create thread node: {str(e)}"
                self.log(error_msg, "ERROR")
                results["errors"].append(error_msg)
                results["steps"].append({
                    "step": 4,
                    "action": "create_thread_node",
                    "result": "FAILED",
                    "error": str(e)
                })
            
            # ============= STEP 4.5: Create Subject Matter Node =============
            if data.subject_matter:
                self.log(f"Step 4.5: Creating subject matter node: '{data.subject_matter}'", "INFO")
                try:
                    subject_matter_result = create_subject_matter_node(
                        subject_matter=data.subject_matter,
                        user_id=data.user_id
                    )
                    self.log(f"Subject matter node created: {data.subject_matter}", "SUCCESS")
                    results["steps"].append({
                        "step": 4.5,
                        "action": "create_subject_matter_node",
                        "input": {"subject_matter": data.subject_matter},
                        "result": "SUCCESS",
                        "data": subject_matter_result
                    })
                except Exception as e:
                    error_msg = f"Failed to create subject matter node: {str(e)}"
                    self.log(error_msg, "ERROR")
                    results["errors"].append(error_msg)
                    results["steps"].append({
                        "step": 4.5,
                        "action": "create_subject_matter_node",
                        "result": "FAILED",
                        "error": str(e)
                    })
            else:
                self.log("Step 4.5: Skipped (no subject matter provided)", "INFO")
            
            # ============= STEP 5: Link Thread to Category =============
            self.log(f"Step 5: Linking thread to category: '{data.category}'", "INFO")
            try:
                link_category_result = link_thread_to_category(
                    thread_id=data.thread_id,
                    category_name=data.category,
                    user_id=data.user_id
                )
                self.log(f"Thread linked to category: {data.category}", "SUCCESS")
                results["steps"].append({
                    "step": 5,
                    "action": "link_thread_to_category",
                    "input": {"thread_id": data.thread_id, "category_name": data.category},
                    "result": "SUCCESS",
                    "data": link_category_result
                })
            except Exception as e:
                error_msg = f"Failed to link thread to category: {str(e)}"
                self.log(error_msg, "ERROR")
                results["errors"].append(error_msg)
                results["steps"].append({
                    "step": 5,
                    "action": "link_thread_to_category",
                    "result": "FAILED",
                    "error": str(e)
                })
            
            # ============= STEP 5.5: Link Thread to Subject Matter =============
            if data.subject_matter:
                self.log(f"Step 5.5: Linking thread to subject matter: '{data.subject_matter}'", "INFO")
                try:
                    link_subject_matter_result = link_thread_to_subject_matter(
                        thread_id=data.thread_id,
                        subject_matter=data.subject_matter,
                        user_id=data.user_id
                    )
                    self.log(f"Thread linked to subject matter: {data.subject_matter}", "SUCCESS")
                    results["steps"].append({
                        "step": 5.5,
                        "action": "link_thread_to_subject_matter",
                        "input": {"thread_id": data.thread_id, "subject_matter": data.subject_matter},
                        "result": "SUCCESS",
                        "data": link_subject_matter_result
                    })
                except Exception as e:
                    error_msg = f"Failed to link thread to subject matter: {str(e)}"
                    self.log(error_msg, "ERROR")
                    results["errors"].append(error_msg)
                    results["steps"].append({
                        "step": 5.5,
                        "action": "link_thread_to_subject_matter",
                        "result": "FAILED",
                        "error": str(e)
                    })
            else:
                self.log("Step 5.5: Skipped (no subject matter provided)", "INFO")
            
            # ============= STEP 6: Link Thread to Topic =============
            self.log(f"Step 6: Linking thread to topic: '{data.topic}'", "INFO")
            try:
                link_topic_result = link_thread_to_topic(
                    thread_id=data.thread_id,
                    topic_name=data.topic,
                    user_id=data.user_id,
                    message_id=data.message_id,
                    timestamp=data.timestamp
                )
                self.log(f"Thread linked to topic: {data.topic}", "SUCCESS")
                results["steps"].append({
                    "step": 6,
                    "action": "link_thread_to_topic",
                    "input": {"thread_id": data.thread_id, "topic_name": data.topic},
                    "result": "SUCCESS",
                    "data": link_topic_result
                })
            except Exception as e:
                error_msg = f"Failed to link thread to topic: {str(e)}"
                self.log(error_msg, "ERROR")
                results["errors"].append(error_msg)
                results["steps"].append({
                    "step": 8,
                    "action": "link_thread_to_topic",
                    "result": "FAILED",
                    "error": str(e)
                })
            
            # ============= STEP 9: Link Topic to Subtopic (if exists) =============
            if data.subtopic:
                self.log(f"Step 9: Linking topic to subtopic: '{data.subtopic}'", "INFO")
                try:
                    link_topic_subtopic_result = link_topic_to_subtopic(
                        topic_name=data.topic,
                        subtopic_name=data.subtopic,
                        user_id=data.user_id,
                        message_id=data.message_id,
                        timestamp=data.timestamp
                    )
                    self.log(f"Topic linked to subtopic: {data.topic} -> {data.subtopic}", "SUCCESS")
                    results["steps"].append({
                        "step": 9,
                        "action": "link_topic_to_subtopic",
                        "input": {
                            "topic_name": data.topic,
                            "subtopic_name": data.subtopic
                        },
                        "result": "SUCCESS",
                        "data": link_topic_subtopic_result
                    })
                except Exception as e:
                    error_msg = f"Failed to link topic to subtopic: {str(e)}"
                    self.log(error_msg, "ERROR")
                    results["errors"].append(error_msg)
                    results["steps"].append({
                        "step": 9,
                        "action": "link_topic_to_subtopic",
                        "result": "FAILED",
                        "error": str(e)
                    })
            else:
                self.log("Step 9: Skipped (no subtopic provided)", "INFO")
            
            # ============= STEP 10: Link Thread to Subtopic (if exists) =============
            if data.subtopic:
                self.log(f"Step 10: Linking thread to subtopic: '{data.subtopic}'", "INFO")
                try:
                    link_subtopic_result = link_thread_to_topic(
                        thread_id=data.thread_id,
                        topic_name=data.topic,
                        subtopic_name=data.subtopic,
                        user_id=data.user_id,
                        message_id=data.message_id,
                        timestamp=data.timestamp
                    )
                    self.log(f"Thread linked to subtopic: {data.subtopic}", "SUCCESS")
                    results["steps"].append({
                        "step": 10,
                        "action": "link_thread_to_topic",
                        "input": {
                            "thread_id": data.thread_id,
                            "topic_name": data.topic,
                            "subtopic_name": data.subtopic
                        },
                        "result": "SUCCESS",
                        "data": link_subtopic_result
                    })
                except Exception as e:
                    error_msg = f"Failed to link thread to subtopic: {str(e)}"
                    self.log(error_msg, "ERROR")
                    results["errors"].append(error_msg)
                    results["steps"].append({
                        "step": 10,
                        "action": "link_thread_to_topic",
                        "result": "FAILED",
                        "error": str(e)
                    })
            else:
                self.log("Step 10: Skipped (no subtopic provided)", "INFO")
            
            # ============= FINAL SUMMARY =============
            print("\n" + "="*70)
            print("📋 PIPELINE EXECUTION SUMMARY")
            print("="*70)
            
            successful_steps = len([s for s in results["steps"] if s.get("result") == "SUCCESS"])
            total_steps = len(results["steps"])
            
            if len(results["errors"]) == 0:
                results["status"] = "SUCCESS"
                self.log(f"Pipeline completed successfully! ({successful_steps}/{total_steps} steps)", "SUCCESS")
            else:
                results["status"] = "COMPLETED_WITH_ERRORS"
                self.log(f"Pipeline completed with {len(results['errors'])} error(s)", "WARNING")
            
            print(f"\n✅ Thread ID: {data.thread_id}")
            print(f"📁 Category: {data.category}")
            print(f"📚 Topic: {data.topic}")
            if data.subtopic:
                print(f"📖 Subtopic: {data.subtopic}")
            if data.subject_matter:
                print(f"💭 Subject Matter: {data.subject_matter}")
            print(f"👥 Participants: {len(data.participants)}")
            print(f"\n📊 Steps Completed: {successful_steps}/{total_steps}")
            
            if results["errors"]:
                print(f"\n⚠️  Errors Encountered:")
                for error in results["errors"]:
                    print(f"   • {error}")
            
            print("\n" + "="*70)
            
        except Exception as e:
            error_msg = f"Fatal error in pipeline: {str(e)}"
            self.log(error_msg, "ERROR")
            results["status"] = "FAILED"
            results["errors"].append(error_msg)
        
        results["logs"] = self.logs
        return results


