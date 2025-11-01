"""
LLM Service
Handles interactions with various LLM providers
"""
from typing import Optional, Dict, Any
import openai
from anthropic import Anthropic
import httpx

from config import settings


class LLMService:
    def __init__(self):
        self.default_provider = settings.DEFAULT_LLM_PROVIDER
        self.default_model = settings.DEFAULT_MODEL
        
        # Initialize clients
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
        
        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            self.anthropic_client = None
    
    async def _call_openai(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Call OpenAI API"""
        
        response = openai.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature or settings.TEMPERATURE,
            max_tokens=max_tokens or settings.MAX_TOKENS
        )
        
        return response.choices[0].message.content
    
    async def _call_anthropic(
        self,
        messages: list,
        model: str = "claude-3-sonnet-20240229",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Call Anthropic Claude API"""
        
        if not self.anthropic_client:
            raise ValueError("Anthropic API key not configured")
        
        # Convert messages format
        system_message = None
        claude_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        response = self.anthropic_client.messages.create(
            model=model,
            system=system_message if system_message else "You are a helpful AI assistant.",
            messages=claude_messages,
            temperature=temperature or settings.TEMPERATURE,
            max_tokens=max_tokens or settings.MAX_TOKENS
        )
        
        return response.content[0].text
    
    async def _call_ollama(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Call Ollama local LLM"""
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": model or settings.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature or settings.TEMPERATURE
                    }
                },
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
    
    async def generate(
        self,
        messages: list,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate response using specified or default LLM"""
        
        provider = provider or self.default_provider
        
        if provider == "openai":
            return await self._call_openai(messages, model, temperature, max_tokens)
        elif provider == "anthropic":
            return await self._call_anthropic(messages, model or "claude-3-sonnet-20240229", temperature, max_tokens)
        elif provider == "ollama":
            return await self._call_ollama(messages, model, temperature)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    async def summarize(
        self,
        content: str,
        user_id: str,
        tenant_id: str,
        provider: Optional[str] = None
    ) -> str:
        """Summarize email thread"""
        
        messages = [
            {
                "role": "system",
                "content": "You are an AI email assistant. Summarize the following email thread concisely, highlighting key points, decisions, and action items."
            },
            {
                "role": "user",
                "content": f"Please summarize this email thread:\n\n{content}"
            }
        ]
        
        return await self.generate(messages, provider=provider)
    
    async def generate_reply(
        self,
        email_content: str,
        from_address: str,
        thread_context: str,
        tone: str,
        additional_context: Optional[str],
        user_id: str,
        tenant_id: str,
        provider: Optional[str] = None
    ) -> str:
        """Generate context-aware email reply"""
        
        tone_instructions = {
            "professional": "Write a formal, professional reply.",
            "semi-professional": "Write a friendly but professional reply.",
            "casual": "Write a casual, conversational reply.",
            "personal": "Write a warm, personal reply."
        }
        
        tone_instruction = tone_instructions.get(tone, tone_instructions["professional"])
        
        system_message = f"""You are an AI email assistant. {tone_instruction}
Consider the email thread context and maintain consistency with the conversation tone.
Be concise and actionable. Do not include greetings like "Dear" or signatures - just the body of the reply."""
        
        user_message = f"""Generate a reply to this email:

From: {from_address}

Email content:
{email_content}

Thread context:
{thread_context}
"""
        
        if additional_context:
            user_message += f"\n\nAdditional context:\n{additional_context}"
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        return await self.generate(messages, provider=provider)
    
    async def analyze_sentiment(
        self,
        text: str,
        provider: Optional[str] = None
    ) -> str:
        """Analyze sentiment of text"""
        
        messages = [
            {
                "role": "system",
                "content": "You are a sentiment analysis AI. Analyze the sentiment of the text and respond with one word: positive, negative, or neutral."
            },
            {
                "role": "user",
                "content": f"Analyze the sentiment of this text:\n\n{text}"
            }
        ]
        
        sentiment = await self.generate(messages, provider=provider, max_tokens=10)
        return sentiment.strip().lower()
