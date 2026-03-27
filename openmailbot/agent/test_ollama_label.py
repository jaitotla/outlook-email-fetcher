#!/usr/bin/env python3
"""
Test script for EmailLabelPipeline (Ollama) - processes emails from data.json one by one
"""

import json
import sys
from pathlib import Path

# Add services directory to path
sys.path.insert(0, str(Path(__file__).parent / "services"))

from ollama_lable_pipline import EmailLabelPipeline


def test_label_pipeline():
    """Test the label pipeline with emails from data.json"""
    
    # Initialize pipeline
    print("=" * 80)
    print("Initializing EmailLabelPipeline (Ollama)...")
    print("=" * 80)
    pipeline = EmailLabelPipeline()
    
    # Load test data
    data_file = Path(__file__).parent / "tests" / "data.json"
    print(f"\nLoading emails from {data_file}...\n")
    
    with open(data_file, 'r') as f:
        emails = json.load(f)
    
    print(f"Loaded {len(emails)} emails\n")
    
    # Process emails one by one
    thread = []
    
    for email in emails:
        email_number = email.get('email_number', '?')
        from_addr = email.get('from', 'Unknown')
        to_addr = email.get('to', 'Unknown')
        subject = email.get('subject', 'No Subject')
        
        # Add email to thread
        thread.append(email)
        
        print("=" * 80)
        print(f"Processing Email #{email_number}")
        print("=" * 80)
        print(f"From: {from_addr}")
        print(f"To: {to_addr}")
        print(f"Subject: {subject}")
        print(f"Thread Size: {len(thread)} messages")
        print("-" * 80)
        
        # Call label_thread
        try:
            result = pipeline.label_thread(thread)
            
            print(f"✓ CLASSIFICATION RESULT:")
            print(f"  Label:           {result.label}")
            print(f"  Category:        {result.category}")
            print(f"  Topic:           {result.topic}")
            print(f"  Subtopic:        {result.subtopic}")
            print(f"  Subject Matter:  {result.subject_matter}")
            
        except Exception as e:
            print(f"✗ Error classifying email: {str(e)}")
        
        print()


if __name__ == "__main__":
    test_label_pipeline()
