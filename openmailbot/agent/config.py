"""
Configuration management using Pydantic Settings

This file defines default/fallback configuration from environment variables.
In production, user-specific settings are fetched from the backend and passed
as 'effective_settings' to service methods.

Provider priorities:
1. effective_settings (per-request user config from backend)
2. Environment variables (tenant-level defaults)
3. Hardcoded defaults below (inbuilt mode)
"""
from pydantic_settings import BaseSettings
from typing import Optional, Dict,Any
import os
import json
class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 5050
    ENVIRONMENT: str = "development"
    
    # Backend API
    BACKEND_API_URL: str = "http://localhost:3000"
    
    # MongoDB
    MONGODB_URI: str = ""
    
    # ==========================================================================
    # Provider Defaults (can be overridden per-user via effective_settings)
    # ==========================================================================
    
    # Default providers - "inbuilt" uses central servers defined in utils.py
    LLM_PROVIDER: str = "inbuilt"  # openai, anthropic, gemini, ollama, inbuilt
    EMBEDDING_PROVIDER: str = "inbuilt"  # openai, nomic, gemini, sentence-transformers, inbuilt
    VECTOR_PROVIDER: str = "inbuilt"  # pinecone, chroma, weaviate, inbuilt
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"
    
    # Google Gemini
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-pro"
    
    # Ollama (self-hosted)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    
    # ==========================================================================
    # Inbuilt Mode - Central Servers (zero-config for users)
    # ==========================================================================
    INBUILT_FLASK_URL: str = "https://lsdiedb39c.pagekite.me"
    INBUILT_OLLAMA_URL: str = "https://ej5f4s6jtj.pagekite.me"
    INBUILT_CHROMA_URL: str = "http://localhost:8500"  # Central ChromaDB
    
    # ==========================================================================
    # Vector Database Settings
    # ==========================================================================
    
    # Pinecone
    PINECONE_API_KEY: Optional[str] = ""
    PINECONE_ENVIRONMENT: str = "us-east-1-aws"
    PINECONE_INDEX_NAME: str = "openmailbot-emails"
    
    # ChromaDB (HTTP-only, remote)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8500
    
    # Weaviate (HTTP-only, remote)
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: Optional[str] = None
    
    # Neo4j (graph relationships)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: Optional[str] = None
    
    # ==========================================================================
    # Embedding Settings
    # ==========================================================================
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    
    # Nomic
    NOMIC_API_KEY: Optional[str] = None
    NOMIC_MODEL: str = "nomic-embed-text-v1.5"
    
    # Sentence Transformers (local)
    SENTENCE_TRANSFORMER_MODEL: str = "all-MiniLM-L6-v2"
    
    # ==========================================================================
    # LLM Generation Settings
    # ==========================================================================
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.7
    
    # Legacy compatibility
    DEFAULT_LLM_PROVIDER: str = "inbuilt"
    DEFAULT_MODEL: str = "gpt-4o-mini"
    VECTOR_DB_TYPE: str = "inbuilt"  # Deprecated: use VECTOR_PROVIDER
    
    def update_settings(self, new_settings: Dict[str, Any], persist: bool = True) -> None:
        """
        Dynamically update settings attributes.
        This allows settings to be changed at runtime without restarting the app.
        
        Args:
            new_settings: Dictionary of settings to update
            persist: If True, saves settings to disk (default: True)
            
        Example:
            settings.update_settings({
                'LLM_PROVIDER': 'openai',
                'OPENAI_API_KEY': 'sk-...',
                'TEMPERATURE': 0.5
            })
        """
        for key, value in new_settings.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                # Warn about unknown settings but still set them
                print(f"⚠️  Warning: Unknown setting '{key}' will be added to Settings")
                setattr(self, key, value)
        
        # Persist to disk if requested
        if persist:
            self.save_to_file()
    
    def get_settings_dict(self) -> Dict[str, Any]:
        """
        Get all current settings as a dictionary.
        
        Returns:
            Dictionary containing all current settings
        """
        return self.model_dump()
    
    def reload_from_dict(self, settings_dict: Dict[str, Any]) -> None:
        """
        Reload all settings from a dictionary.
        Replaces current settings entirely.
        
        Args:
            settings_dict: Dictionary of all settings to load
        """
        self.update_settings(settings_dict, persist=True)
    
    def save_to_file(self, filepath: Optional[str] = None) -> str:
        """
        Save current settings to a JSON file for persistence.
        
        Args:
            filepath: Path to save settings file. If None, uses default location.
            
        Returns:
            Path to the saved file
        """
        if filepath is None:
            # Default location: agent/config_settings.json
            filepath = os.path.join(os.path.dirname(__file__), "config_settings.json")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save settings to file
        settings_dict = self.model_dump()
        with open(filepath, 'w') as f:
            json.dump(settings_dict, f, indent=2, default=str)
        
        print(f"✅ Settings saved to {filepath}")
        return filepath
    
    def load_from_file(self, filepath: Optional[str] = None) -> None:
        """
        Load settings from a JSON file.
        
        Args:
            filepath: Path to load settings file. If None, uses default location.
        """
        if filepath is None:
            # Default location: agent/config_settings.json
            filepath = os.path.join(os.path.dirname(__file__), "config_settings.json")
        
        # Load settings from file if it exists
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    settings_dict = json.load(f)
                self.update_settings(settings_dict, persist=False)
                print(f"✅ Settings loaded from {filepath}")
            except Exception as e:
                print(f"⚠️  Failed to load settings from {filepath}: {e}")
        else:
            print(f"ℹ️  No saved settings file found at {filepath}")


# Create global settings instance
settings = Settings()

# Load persisted settings on startup if available
settings.load_from_file()

# ==========================================================================
# USER SETTINGS - Synced f