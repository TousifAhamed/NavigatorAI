"""
Custom OpenRouter LLM implementation for LangChain.
"""

from typing import Any, List, Mapping, Optional
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from pydantic import BaseModel, Field, ConfigDict
import aiohttp
import json
import logging

class OpenRouterLLM(LLM):
    """LangChain LLM implementation for OpenRouter."""
    
    api_key: str
    # Use a more reliable model for tool calling
    model: str = "meta-llama/llama-3.1-8b-instruct:free"
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)  # Slightly higher for better responses
    max_tokens: int = 4000  # Increased for better responses
    site_url: str = "http://localhost:8501"
    site_name: str = "AI Travel Planner"
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.logger = logging.getLogger("TravelPlanner.OpenRouterLLM")
        self.logger.info(f"Initializing OpenRouter LLM with model: {self.model}")
    
    @property
    def _llm_type(self) -> str:
        return "openrouter"

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Async call to OpenRouter's API."""
        self.logger.debug(f"Making async call to OpenRouter API")
        self.logger.debug(f"Prompt length: {len(prompt)} characters")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name
        }
        
        # Basic message format - let LangChain handle function calling formatting
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stop": ["```", "</json>"]  # Add stop tokens to prevent incomplete responses
        }
        
        # Add function calling support if tools are provided
        if 'tools' in kwargs:
            payload['tools'] = kwargs['tools']
            payload['tool_choice'] = kwargs.get('tool_choice', 'auto')
        
        if stop:
            payload["stop"] = stop
        
        self.logger.debug(f"API payload: {json.dumps(payload, indent=2)}")
            
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_text = await response.text()
                    self.logger.info(f"OpenRouter API Response Status: {response.status}")
                    
                    if response.status == 401:
                        self.logger.error("OpenRouter API Key is invalid or expired!")
                        raise Exception("Invalid OpenRouter API key. Please check your API key at https://openrouter.ai/")
                    elif response.status == 429:
                        self.logger.warning("OpenRouter API rate limit exceeded")
                        raise Exception("Rate limit exceeded. Please try again later.")
                    elif response.status != 200:
                        self.logger.error(f"OpenRouter API Error: {response_text}")
                        raise Exception(f"API call failed with status {response.status}: {response_text}")
                    
                    try:
                        result = await response.json()
                        self.logger.debug(f"API response: {json.dumps(result, indent=2)}")
                    except json.JSONDecodeError:
                        self.logger.error(f"Invalid JSON response: {response_text}")
                        raise Exception(f"Invalid JSON response from OpenRouter: {response_text}")
                    
                    if not result.get('choices'):
                        self.logger.error(f"No choices in response: {result}")
                        raise ValueError("No response choices found in API result")
                    
                    choice = result['choices'][0]
                    message = choice['message']
                    
                    # Handle function calling response
                    if message.get('tool_calls'):
                        self.logger.info("Tool calls detected in response")
                        # Return the full message for LangChain to handle
                        return json.dumps(message)
                    
                    content = message.get('content', '')
                    self.logger.debug(f"Response content length: {len(content)} characters")
                    
                    # Handle empty or very short responses with retry logic
                    if not content or len(content.strip()) < 2:
                        self.logger.warning("Empty or very short response, retrying with modified prompt...")
                        # Try again with a more explicit prompt
                        modified_payload = payload.copy()
                        modified_payload['messages'][0]['content'] = f"Please provide a complete response to: {prompt}\n\nYou must use the exact format with 'Action:' and 'Action Input:' when using tools."
                        modified_payload['temperature'] = 0.3  # Increase temperature for retry
                        
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=modified_payload,
                            timeout=aiohttp.ClientTimeout(total=45)
                        ) as retry_response:
                            if retry_response.status == 200:
                                retry_result = await retry_response.json()
                                if retry_result.get('choices'):
                                    retry_content = retry_result['choices'][0]['message'].get('content', '')
                                    if retry_content and len(retry_content.strip()) > 2:
                                        self.logger.info("Retry successful, got better response")
                                        content = retry_content
                    
                    self.logger.info(f"OpenRouter Response: {content[:100]}...")
                    return content
                    
            except aiohttp.ClientError as e:
                self.logger.error(f"Network error calling OpenRouter: {e}")
                raise Exception(f"Network error: {e}")
            except Exception as e:
                self.logger.error(f"Error in OpenRouter call: {e}")
                raise

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Sync call to OpenRouter's API."""
        self.logger.debug("Making sync call to OpenRouter API")
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._acall(prompt, stop, run_manager, **kwargs))

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        } 