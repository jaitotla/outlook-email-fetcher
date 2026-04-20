"""
Email Preprocessing Pipeline
Handles cleaning, deduplication, and content extraction from raw emails
"""
import re
import html
from typing import List, Dict, Any


class EmailPreprocessingPipeline:
    """
    Pipeline for preprocessing email data before storage or analysis
    """
    
    def __init__(self):
        """Initialize the preprocessing pipeline"""
        pass
    
    def clean_email_body(self, body: str) -> str:
        """
        Clean email body by removing:
        - HTML tags and code
        - All URLs/links
        - Email disclaimers
        - Excessive whitespace
        Using only Python regex (no external libraries except html)
        """
        if not body:
            return ""
        
        # Decode HTML entities first (e.g., &nbsp; &lt; &gt; &amp;)
        body = html.unescape(body)
        
        # Remove HTML comments
        body = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
        
        # Remove script and style tags with their content
        body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove all HTML tags
        body = re.sub(r'<[^>]+>', '', body)
        
        # Remove all URLs (multiple patterns for comprehensive coverage)
        # http:// and https:// URLs
        body = re.sub(r'https?://[^\s<>"{}|\\^`\[\]]+', '', body)
        # www. URLs without protocol
        body = re.sub(r'www\.[^\s<>"{}|\\^`\[\]]+', '', body)
        # Remove email-style links with <> brackets
        body = re.sub(r'<[^\s]+@[^\s]+>', '', body)
        # Remove mailto: links
        body = re.sub(r'mailto:[^\s]+', '', body)
        
        # Remove common email disclaimers (case insensitive, multiline)
        disclaimer_patterns = [
            r'this\s+email.*?confidential.*?intended.*?recipient.*?(?:\n|$)',
            r'confidentiality\s+notice:.*?(?:\n\n|\Z)',
            r'disclaimer:.*?(?:\n\n|\Z)',
            r'this\s+message.*?confidential.*?(?:\n\n|\Z)',
            r'if\s+you.*?not.*?intended\s+recipient.*?(?:\n\n|\Z)',
            r'please\s+consider\s+the\s+environment\s+before\s+printing.*?(?:\n|$)',
            r'virus.*?free.*?checked.*?(?:\n\n|\Z)',
            r'unsubscribe.*?(?:\n\n|\Z)',
            r'to\s+unsubscribe.*?(?:\n|$)',
            r'click\s+here\s+to.*?(?:\n|$)',
            r'you\s+received\s+this\s+email\s+because.*?(?:\n\n|\Z)',
        ]
        
        for pattern in disclaimer_patterns:
            body = re.sub(pattern, '', body, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove email signatures (common patterns)
        # Standard -- separator
        body = re.sub(r'\n--\s*\n.*', '', body, flags=re.DOTALL)
        # Long separator lines
        body = re.sub(r'\n_{5,}.*', '', body, flags=re.DOTALL)
        body = re.sub(r'\n={5,}.*', '', body, flags=re.DOTALL)
        body = re.sub(r'\n-{5,}.*', '', body, flags=re.DOTALL)
        
        # Remove common signature patterns
        body = re.sub(r'\n(best\s+regards?|sincerely|thanks?|cheers|regards),?\s*\n.*', '', body, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove excessive whitespace
        body = re.sub(r'\n{3,}', '\n\n', body)  # Multiple newlines to max 2
        body = re.sub(r'[ \t]+', ' ', body)  # Multiple spaces/tabs to single space
        body = re.sub(r' +\n', '\n', body)  # Trailing spaces before newline
        body = re.sub(r'\n ', '\n', body)  # Leading spaces after newline
        
        return body.strip()
    
    def extract_new_content(self, body: str) -> str:
        """
        Remove quoted/nested email content from body
        Returns only the new content written in this specific message
        """
        if not body:
            return ""
        
        lines = body.split('\n')
        new_content = []
        
        for line in lines:
            # Stop at common quote indicators
            # "On Thu, Jan 22, 2026 at 10:34 AM ... wrote:"
            if re.match(r'^On .+wrote:\s*$', line.strip()):
                break
            # Lines starting with ">"
            if re.match(r'^>\s*', line):
                break
            # Email headers in forwarded messages
            if re.match(r'^From:\s*', line.strip()):
                break
            # Separator lines
            if re.match(r'^-{3,}', line.strip()):
                break
            # Alternative quote pattern with email
            if 'wrote:' in line and '@' in line and '<' in line:
                break
                
            new_content.append(line)
        
        # Join and clean up
        result = '\n'.join(new_content).strip()
        
        # Remove excessive blank lines
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result
    
    def deduplicate_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process messages to extract only new content from each message
        Removes nested/quoted email content, HTML, links, and disclaimers
        """
        processed = []
        
        for msg in messages:
            raw_body = msg.get('body', '')
            
            # Step 1: Extract new content (remove quoted/nested emails)
            new_content = self.extract_new_content(raw_body)
            
            # Step 2: Clean the content (remove HTML, links, disclaimers)
            clean_body = self.clean_email_body(new_content)
            
            # Create new message object with cleaned body
            processed_msg = {
                'message_id': msg.get('message_id'),
                'from': msg.get('from'),
                'to': msg.get('to'),
                'subject': msg.get('subject'),
                'timestamp': msg.get('timestamp'),
                'body': clean_body
            }
            
            processed.append(processed_msg)
        
        return processed
    
    def process(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Main entry point for preprocessing pipeline
        
        Args:
            messages: List of raw email message dictionaries
            
        Returns:
            List of cleaned and deduplicated email message dictionaries
        """
        return self.deduplicate_messages(messages)
