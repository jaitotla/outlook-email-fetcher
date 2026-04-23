"""
File processing service for extracting text from PDFs, DOCX, images (OCR)
"""

import io
import logging
import mimetypes
from typing import Optional, Dict, Any
import httpx
import PyPDF2
from docx import Document
from PIL import Image
import pytesseract
import anthropic

logger = logging.getLogger(__name__)


class FileProcessor:
    """Process files from various sources (Slack, email attachments, etc.)"""
    
    def __init__(self, max_file_size: int = 10485760):  # 10MB default
        self.max_file_size = max_file_size
        self.anthropic_client = None
        
    def _init_anthropic(self):
        """Initialize Anthropic client for image description"""
        if not self.anthropic_client:
            import os
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if api_key:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
    
    async def process_file(
        self,
        file_url: Optional[str] = None,
        file_data: Optional[bytes] = None,
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        use_ocr: bool = False
    ) -> Dict[str, Any]:
        """
        Process a file and extract text/information
        
        Args:
            file_url: URL to download file from
            file_data: Raw file bytes (if already downloaded)
            file_name: Name of the file
            mime_type: MIME type of the file
            use_ocr: Whether to use OCR for images (requires user permission)
        
        Returns:
            Dict with extracted_text, description, processed status
        """
        result = {
            'extracted_text': '',
            'description': '',
            'processed': False,
            'error': None
        }
        
        try:
            # Download file if URL provided
            if file_url and not file_data:
                file_data = await self._download_file(file_url)
            
            if not file_data:
                result['error'] = 'No file data provided'
                return result
            
            # Check file size
            if len(file_data) > self.max_file_size:
                result['error'] = f'File too large: {len(file_data)} bytes (max: {self.max_file_size})'
                return result
            
            # Determine MIME type if not provided
            if not mime_type and file_name:
                mime_type, _ = mimetypes.guess_type(file_name)
            
            # Process based on file type
            if mime_type == 'application/pdf':
                result['extracted_text'] = self._process_pdf(file_data)
                result['processed'] = True
            
            elif mime_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
                result['extracted_text'] = self._process_docx(file_data)
                result['processed'] = True
            
            elif mime_type and mime_type.startswith('image/'):
                if use_ocr:
                    ocr_text = self._process_image_ocr(file_data)
                    description = await self._generate_image_description(file_data, mime_type)
                    result['extracted_text'] = ocr_text
                    result['description'] = description
                    result['processed'] = True
                else:
                    result['error'] = 'Image processing requires OCR permission'
            
            elif mime_type == 'text/plain':
                result['extracted_text'] = file_data.decode('utf-8', errors='ignore')
                result['processed'] = True
            
            else:
                result['error'] = f'Unsupported file type: {mime_type}'
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    async def _download_file(self, url: str) -> Optional[bytes]:
        """Download file from URL"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return None
    
    def _process_pdf(self, file_data: bytes) -> str:
        """Extract text from PDF"""
        try:
            pdf_file = io.BytesIO(file_data)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_parts = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return '\n\n'.join(text_parts)
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return ''
    
    def _process_docx(self, file_data: bytes) -> str:
        """Extract text from DOCX"""
        try:
            doc_file = io.BytesIO(file_data)
            doc = Document(doc_file)
            
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text:
                    text_parts.append(paragraph.text)
            
            return '\n\n'.join(text_parts)
        except Exception as e:
            logger.error(f"Error processing DOCX: {str(e)}")
            return ''
    
    def _process_image_ocr(self, file_data: bytes) -> str:
        """Extract text from image using OCR"""
        try:
            image = Image.open(io.BytesIO(file_data))
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.error(f"Error processing image OCR: {str(e)}")
            return ''
    
    async def _generate_image_description(self, file_data: bytes, mime_type: str) -> str:
        """Generate image description using Claude Vision"""
        try:
            self._init_anthropic()
            if not self.anthropic_client:
                return ''
            
            import base64
            image_b64 = base64.b64encode(file_data).decode('utf-8')
            
            message = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": image_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": "Describe this image in 2-3 sentences, focusing on key content and context."
                        }
                    ]
                }]
            )
            
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error generating image description: {str(e)}")
            return ''
