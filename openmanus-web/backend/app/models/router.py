"""
Model Router Module
Routes LLM requests to different providers (OpenAI, Anthropic, Google, Ollama)
"""

import os
import logging
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]]) -> Any:
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            raise


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider"""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
    
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            # Convert messages to Anthropic format
            system_message = ""
            anthropic_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_message,
                messages=anthropic_messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            raise


class GoogleProvider(BaseLLMProvider):
    """Google Gemini provider"""
    
    def __init__(self, api_key: str, model: str = "gemini-pro"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
    
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            # Convert messages to Gemini format
            prompt = ""
            for msg in messages:
                if msg["role"] == "system":
                    prompt += f"System: {msg['content']}\n\n"
                elif msg["role"] == "user":
                    prompt += f"User: {msg['content']}\n\n"
                elif msg["role"] == "assistant":
                    prompt += f"Assistant: {msg['content']}\n\n"
                elif msg["role"] == "tool":
                    prompt += f"Tool Result: {msg['content']}\n\n"
            
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Google error: {e}")
            raise


class OllamaProvider(BaseLLMProvider):
    """Ollama local model provider"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1"):
        from ollama import AsyncClient
        self.client = AsyncClient(host=base_url)
        self.model = model
        self.base_url = base_url
    
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = await self.client.chat(
                model=self.model,
                messages=messages
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise


class ModelRouter:
    """
    Routes LLM requests to appropriate provider based on configuration
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize model router with configuration
        
        Args:
            config: Dictionary with keys:
                - provider: "openai", "anthropic", "google", or "ollama"
                - model: Model name
                - api_key: API key (for cloud providers)
                - ollama_base_url: Base URL for Ollama (optional)
        """
        self.config = config
        self.provider = self._initialize_provider(config)
    
    def _initialize_provider(self, config: Dict[str, Any]) -> BaseLLMProvider:
        """Initialize the appropriate LLM provider"""
        provider_name = config.get("provider", "ollama").lower()
        model = config.get("model", "")
        api_key = config.get("api_key") or os.getenv(f"{provider_name.upper()}_API_KEY", "")
        ollama_url = config.get("ollama_base_url") or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        
        if provider_name == "openai":
            if not api_key:
                raise ValueError("OpenAI API key is required")
            return OpenAIProvider(api_key=api_key, model=model or "gpt-4o")
        
        elif provider_name == "anthropic":
            if not api_key:
                raise ValueError("Anthropic API key is required")
            return AnthropicProvider(api_key=api_key, model=model or "claude-3-5-sonnet-20241022")
        
        elif provider_name == "google":
            if not api_key:
                raise ValueError("Google API key is required")
            return GoogleProvider(api_key=api_key, model=model or "gemini-pro")
        
        elif provider_name == "ollama":
            return OllamaProvider(base_url=ollama_url, model=model or "llama3.1")
        
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
    
    async def generate(self, messages: List[Dict[str, str]]) -> Any:
        """Generate response using configured provider"""
        return await self.provider.generate(messages)
