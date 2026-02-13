"""
Email Pipeline Test - Ollama Only
Tests the Ollama pipeline (agent/services/ollama_lable_pipline.py)
Loads emails from JSON file and tests the Ollama pipeline
OpenAI pipeline code is commented out
"""
import json
import os
from typing import List, Dict, Any
from pathlib import Path
from tabulate import tabulate
from datetime import datetime

# Import both pipelines
# from services.label_pipeline import EmailLabelPipeline  # OpenAI pipeline - commented out
from services.ollama_lable_pipline import EmailLabelPipeline as OllamaEmailLabelPipeline


def load_emails_from_json(json_file_path: str) -> List[Dict[str, Any]]:
    """
    Load emails from JSON file
    
    Args:
        json_file_path: Path to the JSON file
        
    Returns:
        List of email dictionaries
    """
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        # Extract messages from the JSON structure
        messages = data.get('messages', [])
        print(f"✓ Loaded {len(messages)} emails from {json_file_path}\n")
        return messages
    except FileNotFoundError:
        print(f"❌ File not found: {json_file_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return []


def format_email_for_pipeline(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format email message for pipeline processing
    
    Args:
        message: Raw email message from JSON
        
    Returns:
        Formatted email dictionary with required fields
    """
    return {
        'from': message.get('from', 'Unknown'),
        'to': message.get('to', []),
        'subject': message.get('subject', ''),
        'body': message.get('body', ''),
        'user_id': 'ankitgoel2004@gmail.com',  # Default user
        'timestamp': message.get('timestamp', '')
    }


def show_ollama_results(
    email_data: Dict[str, Any],
    ollama_result: Any,
    email_index: int,
    output_file=None
) -> str:
    """
    Display formatted results from Ollama pipeline only
    
    Args:
        email_data: Original email data
        ollama_result: Result from Ollama pipeline
        email_index: Index of the email being processed
        output_file: File handle to write results (optional)
        
    Returns:
        Formatted results string
    """
    output = f"\n{'='*80}\n"
    output += f"EMAIL #{email_index} - OLLAMA RESULTS\n"
    output += f"{'='*80}\n"
    output += f"From: {email_data['from']}\n"
    output += f"Subject: {email_data['subject']}\n"
    output += f"Body Preview: {email_data['body'][:100]}...\n"
    output += f"\n{'-'*80}\n\n"
    
    # Create results table
    results_data = [
        ['Field', 'Ollama Pipeline Result'],
        ['-' * 15, '-' * 30],
        ['Label', ollama_result.label],
        ['Category', ollama_result.category],
        ['Topic', ollama_result.topic],
        ['Subtopic', ollama_result.subtopic or 'None']
    ]
    
    table_str = tabulate(results_data, tablefmt='grid')
    output += table_str
    
    print(output)
    if output_file:
        output_file.write(output + "\n")
    
    return output


def compare_pipeline_results(
    email_data: Dict[str, Any],
    openai_result: Any,
    ollama_result: Any,
    email_index: int,
    output_file=None
) -> str:
    """
    Generate formatted comparison of results from both pipelines
    
    Args:
        email_data: Original email data
        openai_result: Result from OpenAI pipeline
        ollama_result: Result from Ollama pipeline
        email_index: Index of the email being processed
        output_file: File handle to write results (optional)
        
    Returns:
        Formatted comparison string
    """
    output = f"\n{'='*80}\n"
    output += f"EMAIL #{email_index}\n"
    output += f"{'='*80}\n"
    output += f"From: {email_data['from']}\n"
    output += f"Subject: {email_data['subject']}\n"
    output += f"Body Preview: {email_data['body'][:100]}...\n"
    output += f"\n{'-'*80}\n\n"
    
    # Create comparison table
    comparison_data = [
        ['Field', 'OpenAI Pipeline', 'Ollama Pipeline', 'Match?'],
        ['-' * 15, '-' * 30, '-' * 30, '-' * 8],
        [
            'Label',
            openai_result.label,
            ollama_result.label,
            '✓' if openai_result.label == ollama_result.label else '✗'
        ],
        [
            'Category',
            openai_result.category,
            ollama_result.category,
            '✓' if openai_result.category == ollama_result.category else '✗'
        ],
        [
            'Topic',
            openai_result.topic,
            ollama_result.topic,
            '✓' if openai_result.topic == ollama_result.topic else '✗'
        ],
        [
            'Subtopic',
            openai_result.subtopic or 'None',
            ollama_result.subtopic or 'None',
            '✓' if openai_result.subtopic == ollama_result.subtopic else '✗'
        ]
    ]
    
    table_str = tabulate(comparison_data, tablefmt='grid')
    output += table_str
    
    print(output)
    if output_file:
        output_file.write(output + "\n")
    
    return output


def test_single_email_both_pipelines(email_data: Dict[str, Any], email_index: int, output_file=None):
    """
    Test a single email with both pipelines
    
    Args:
        email_data: Email data to classify
        email_index: Index of the email
        output_file: File handle to write results (optional)
    """
    print(f"\n🔄 Processing email #{email_index}...")
    
    try:
        # Initialize Ollama pipeline only
        # openai_pipeline = EmailLabelPipeline(openai_api_key=None)  # OpenAI pipeline - commented out
        ollama_pipeline = OllamaEmailLabelPipeline(
            ollama_url="https://lsdiedb39c.pagekite.me/chat_structure",
            model="llama3.2"
        )
        
        # Process with OpenAI pipeline - COMMENTED OUT
        # print("  → Calling OpenAI pipeline...")
        # try:
        #     openai_result = openai_pipeline.label_email(email_data)
        #     print(f"    ✓ OpenAI result: {openai_result.label}")
        # except Exception as e:
        #     print(f"    ❌ OpenAI error: {str(e)}")
        #     openai_result = None
        openai_result = None  # Set to None since OpenAI is disabled
        
        # Process with Ollama pipeline
        print("  → Calling Ollama pipeline...")
        try:
            ollama_result = ollama_pipeline.label_email(email_data)
            print(f"    ✓ Ollama result: {ollama_result.label}")
        except Exception as e:
            print(f"    ❌ Ollama error: {str(e)}")
            ollama_result = None
        
        # Show results (Ollama only)
        if ollama_result:
            show_ollama_results(email_data, ollama_result, email_index, output_file)
        else:
            msg = "⚠️  Ollama pipeline failed\n"
            print(msg)
            if output_file:
                output_file.write(msg)
            
    except Exception as e:
        print(f"❌ Error processing email: {str(e)}")


def test_all_emails_from_json(json_file_path: str, output_file_path: str = None):
    """
    Main test function - load all emails and test with Ollama pipeline only
    Optionally saves results to a text file
    
    Args:
        json_file_path: Path to JSON file with emails
        output_file_path: Path to save results (optional)
    """
    print(f"\n{'='*80}")
    print(f"EMAIL PIPELINE TEST - OLLAMA ONLY")
    print(f"{'='*80}\n")
    
    # Create output file if path provided
    output_file = None
    if output_file_path:
        try:
            output_file = open(output_file_path, 'w')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header = f"\n{'='*80}\n"
            header += f"EMAIL PIPELINE TEST - OLLAMA ONLY\n"
            header += f"Generated: {timestamp}\n"
            header += f"{'='*80}\n\n"
            output_file.write(header)
            print(f"✓ Results will be saved to: {output_file_path}\n")
        except IOError as e:
            print(f"⚠️  Could not open output file: {str(e)}")
            output_file = None
    
    # Load emails
    messages = load_emails_from_json(json_file_path)
    
    if not messages:
        print("❌ No emails found to process")
        return
    
    # Process each email
    for index, message in enumerate(messages, 1):
        email_data = format_email_for_pipeline(message)
        test_single_email_both_pipelines(email_data, index, output_file)
    
    # Close output file if opened
    if output_file:
        output_file.write(f"\n{'='*80}\n")
        output_file.write(f"✓ OLLAMA TEST COMPLETE\n")
        output_file.write(f"{'='*80}\n\n")
        output_file.close()
    
    print(f"\n{'='*80}")
    print(f"✓ OLLAMA TEST COMPLETE")
    print(f"{'='*80}\n")


def test_custom_email(output_file_path: str = None):
    """
    Test with a custom email sample
    
    Args:
        output_file_path: Path to save results (optional)
    """
    # Create output file if path provided
    output_file = None
    if output_file_path:
        try:
            output_file = open(output_file_path, 'w')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header = f"\n{'='*80}\n"
            header += f"CUSTOM EMAIL TEST - OLLAMA ONLY\n"
            header += f"Generated: {timestamp}\n"
            header += f"{'='*80}\n\n"
            output_file.write(header)
        except IOError as e:
            print(f"⚠️  Could not open output file: {str(e)}")
            output_file = None
    
    print(f"\n{'='*80}")
    print(f"CUSTOM EMAIL TEST - OLLAMA ONLY")
    print(f"{'='*80}\n")
    
    test_email = {
        "from": "reservations@marriott.com",
        "to": ["user@example.com"],
        "subject": "Your Hotel Booking Confirmation",
        "body": "Dear Guest, Your reservation at Marriott Hotel has been confirmed. Check-in: Jan 15, 2025. Check-out: Jan 18, 2025.",
        "user_id": "ankitgoel2004@gmail.com"
    }
    
    print(f"Testing custom email:")
    test_single_email_both_pipelines(test_email, 1, output_file)
    
    if output_file:
        output_file.write(f"\n{'='*80}\n")
        output_file.write(f"✓ TEST COMPLETE\n")
        output_file.write(f"{'='*80}\n\n")
        output_file.close()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Output file configuration
    output_file_path = "test_results_LLama.txt"
    
    # Option 1: Test with JSON file (if available)
    json_file_path = "/home/ubuntu/openmailbot/openmailbot/agent/data/ankitgoel2004@gmail.com/log_emails/19b10f314c473626/19b10f314c473626.json"
    
    if os.path.exists(json_file_path):
        print("\n✓ Found email data JSON file - testing with real emails...\n")
        test_all_emails_from_json(json_file_path, output_file_path)
   
