"""
LLM Service
Handles interactions with various LLM providers
"""
from typing import Optional, Dict, Any, List
import openai
from anthropic import Anthropic
import httpx
import logging
import os
import json
from config import settings

logger = logging.getLogger(__name__)

# Load configuration
CONFIG_PATH = "/home/manotr/openmailbot/openmailbot/agent/config.json"
# openmailbot/openmailbot/agent/config.json
with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

class ProviderError(Exception):
    """Exception raised when an LLM provider fails"""
    def __init__(self, provider: str, message: str, original_error: Exception = None):
        self.provider = provider
        self.message = message
        self.original_error = original_error
        super().__init__(f"{provider} error: {message}")


class LLMService:
    def __init__(self, effective_settings: Optional[Dict[str, Any]] = None):
        """
        Initialize LLM service.
        
        Args:
            effective_settings: Optional dict with user-specific settings including:
                - llm_provider: 'openai', 'anthropic', 'gemini', 'ollama', 'inbuilt'
                - llm_api_key: API key for the provider
                - llm_model: Model name to use
                - ollama_url: URL for Ollama server (if using ollama)
                If not provided, uses CONFIG as fallback
        """
        # Use provided settings or fall back to global CONFIG
        self.effective_settings = effective_settings if effective_settings else (CONFIG or {})
        
        # Use effective settings if provided, otherwise fall back to global config
        self.default_provider = self.effective_settings.get("llm_provider") or settings.DEFAULT_LLM_PROVIDER
        self.default_model = self.effective_settings.get("llm_model") or settings.DEFAULT_MODEL
        
        # Initialize clients based on settings
        self._init_clients()
    
    def _init_clients(self):
        """Initialize LLM clients based on settings"""
        # OpenAI
        openai_key = self.effective_settings.get("llm_api_key") or settings.OPENAI_API_KEY
        if openai_key:
            openai.api_key = openai_key
        
        # Anthropic
        anthropic_key = self.effective_settings.get("llm_api_key") or settings.ANTHROPIC_API_KEY
        if anthropic_key:
            self.anthropic_client = Anthropic(api_key=anthropic_key)
        else:
            self.anthropic_client = None
        
        # # Gemini
        # gemini_key = self.effective_settings.get("llm_api_key") or os.environ.get("GEMINI_API_KEY")
        # if gemini_key:
        #     try:
        #         import google.generativeai as genai
        #         genai.configure(api_key=gemini_key)
        #         self.gemini_configured = True
        #     except ImportError:
        #         logger.warning("google-generativeai not installed. Gemini support disabled.")
        #         self.gemini_configured = False
        # else:
        #     self.gemini_configured = False
    
    async def _call_openai(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Call OpenAI API using Chat Completions"""
        
        try:
            model = model or self.default_model
            
            response = openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature or settings.TEMPERATURE,
                max_tokens=max_tokens or settings.MAX_TOKENS
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise ProviderError("openai", str(e), e)
    
    async def _call_openai_responses(
        self,
        messages: list,
        model: str = "gpt-5-mini",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Call OpenAI Responses API for newer models like gpt-5-mini.
        Uses /v1/responses endpoint with 'input' format.
        """
        try:
            api_key = self.effective_settings.get("llm_api_key") or settings.OPENAI_API_KEY
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "input": messages,
                        "temperature": temperature or settings.TEMPERATURE,
                        "max_output_tokens": max_tokens or settings.MAX_TOKENS
                    },
                    timeout=120.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Parse Responses API format
                return data["output"][1]["content"][0]["text"]
                
        except Exception as e:
            raise ProviderError("openai", f"Responses API error: {str(e)}", e)
    
    async def _call_anthropic(
        self,
        messages: list,
        model: str = "claude-3-sonnet-20240229",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Call Anthropic Claude API"""
        
        if not self.anthropic_client:
            raise ProviderError("anthropic", "Anthropic API key not configured")
        
        try:
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
            
        except Exception as e:
            raise ProviderError("anthropic", str(e), e)
    
    async def _call_gemini(
        self,
        messages: list,
        model: str = "gemini-1.5-pro",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Call Google Gemini API"""
        
        if not self.gemini_configured:
            raise ProviderError("gemini", "Gemini API key not configured or google-generativeai not installed")
        
        try:
            import google.generativeai as genai
            
            # Convert messages to Gemini format
            gemini_model = genai.GenerativeModel(model)
            
            # Extract system instruction and chat history
            system_instruction = None
            chat_history = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    chat_history.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    chat_history.append({"role": "model", "parts": [msg["content"]]})
            
            # If system instruction, prepend to first user message
            if system_instruction and chat_history:
                first_msg = chat_history[0]
                if first_msg["role"] == "user":
                    first_msg["parts"][0] = f"{system_instruction}\n\n{first_msg['parts'][0]}"
            
            # Generate response
            generation_config = genai.GenerationConfig(
                temperature=temperature or settings.TEMPERATURE,
                max_output_tokens=max_tokens or settings.MAX_TOKENS
            )
            
            # For single turn
            if len(chat_history) == 1:
                response = gemini_model.generate_content(
                    chat_history[0]["parts"][0],
                    generation_config=generation_config
                )
            else:
                # Multi-turn chat
                chat = gemini_model.start_chat(history=chat_history[:-1])
                response = chat.send_message(
                    chat_history[-1]["parts"][0],
                    generation_config=generation_config
                )
            
            return response.text
            
        except Exception as e:
            raise ProviderError("gemini", str(e), e)
    
    async def _call_ollama(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Call Ollama local LLM"""
        
        ollama_url ="http://localhost:11434"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{ollama_url}/api/chat",
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
                
        except Exception as e:
            raise ProviderError("ollama", str(e), e)
    
    async def _call_inbuilt(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Call inbuilt LLM service (uses utils.py)"""
        
        try:
            from utils import call_chat_api
            
            # Convert messages to prompt format
            prompt_parts = []
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    prompt_parts.append(f"System: {content}")
                elif role == "user":
                    prompt_parts.append(f"User: {content}")
                elif role == "assistant":
                    prompt_parts.append(f"Assistant: {content}")
            
            prompt = "\n\n".join(prompt_parts)
            
            # Call inbuilt API (synchronous, wrap in async context)
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, call_chat_api, prompt)
            
            if isinstance(result, dict) and "error" in result:
                raise ProviderError("inbuilt", result["error"])
            
            return result
            
        except ImportError:
            raise ProviderError("inbuilt", "utils.py not found or call_chat_api not available")
        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError("inbuilt", str(e), e)
    
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
        model = model or self.default_model
        
        # Detect if we need OpenAI Responses API for gpt-5 models
        if provider == "openai" and model and model.startswith("gpt-5"):
            return await self._call_openai_responses(messages, model, temperature, max_tokens)
        elif provider == "openai":
            return await self._call_openai(messages, model, temperature, max_tokens)
        elif provider == "anthropic":
            return await self._call_anthropic(messages, model or "claude-3-sonnet-20240229", temperature, max_tokens)
        elif provider == "gemini":
            return await self._call_gemini(messages, model or "gemini-1.5-pro", temperature, max_tokens)
        elif provider == "ollama":
            return await self._call_ollama(messages, model, temperature)
        elif provider == "inbuilt":
            return await self._call_inbuilt(messages, model, temperature)
        else:
            raise ProviderError(provider, f"Unsupported LLM provider: {provider}")
    
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
