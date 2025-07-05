"""
Custom Ollama LLM implementation for LangChain.
Provides local LLM inference without rate limits or API costs.
"""

from typing import Any, List, Mapping, Optional
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from pydantic import BaseModel, Field, ConfigDict
import ollama
import json
import logging
import asyncio

class OllamaLLM(LLM):
    """LangChain LLM implementation for Ollama."""
    
    model: str = "devstral:latest"  # Use available model (was llama3.1:8b)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=1)
    num_predict: int = 4000  # Maximum tokens to generate
    host: str = "http://localhost:11434"  # Default Ollama host
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.logger = logging.getLogger("TravelPlanner.OllamaLLM")
        self.logger.info(f"Initializing Ollama LLM with model: {self.model}")
        
        # Test connection to Ollama
        try:
            self._test_connection()
            self.logger.info("Successfully connected to Ollama service")
        except Exception as e:
            self.logger.error(f"Failed to connect to Ollama: {e}")
            self.logger.warning("Make sure Ollama is running and the model is available")
    
    def _test_connection(self):
        """Test connection to Ollama and verify model availability"""
        try:
            # List available models
            models = ollama.list()
            available_models = [model['name'] for model in models['models']]
            
            if self.model not in available_models:
                self.logger.warning(f"Model {self.model} not found. Available models: {available_models}")
                self.logger.info(f"You can pull the model with: ollama pull {self.model}")
            else:
                self.logger.info(f"Model {self.model} is available")
                
        except Exception as e:
            raise Exception(f"Cannot connect to Ollama service at {self.host}. Make sure Ollama is running.")
    
    @property
    def _llm_type(self) -> str:
        return "ollama"

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Async call to Ollama."""
        self.logger.debug(f"Making async call to Ollama")
        self.logger.debug(f"Prompt length: {len(prompt)} characters")
        
        try:
            # Run Ollama generation in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                self._generate_sync, 
                prompt, 
                stop
            )
            
            self.logger.info(f"Ollama Response: {response[:100]}...")
            return response
            
        except Exception as e:
            self.logger.error(f"Error in Ollama call: {e}")
            raise

    def _generate_sync(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Synchronous generation using Ollama"""
        try:
            # Prepare generation options
            options = {
                'temperature': self.temperature,
                'top_p': self.top_p,
                'top_k': self.top_k,
                'num_predict': self.num_predict,
            }
            
            if stop:
                options['stop'] = stop
            
            self.logger.debug(f"Ollama options: {options}")
            
            # Generate response
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options=options,
                stream=False
            )
            
            if 'response' in response:
                return response['response']
            else:
                self.logger.error(f"Unexpected response format: {response}")
                raise ValueError(f"Unexpected response format from Ollama: {response}")
                
        except Exception as e:
            self.logger.error(f"Ollama generation failed: {e}")
            
            # Provide helpful error messages
            if "model" in str(e).lower():
                raise Exception(f"Model {self.model} not found. Please run: ollama pull {self.model}")
            elif "connection" in str(e).lower() or "refused" in str(e).lower():
                raise Exception(f"Cannot connect to Ollama at {self.host}. Make sure Ollama is running.")
            else:
                raise Exception(f"Ollama error: {e}")

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Sync call to Ollama."""
        self.logger.debug("Making sync call to Ollama")
        return self._generate_sync(prompt, stop)

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "num_predict": self.num_predict,
            "host": self.host
        }

    def get_model_info(self) -> dict:
        """Get information about the current model"""
        try:
            models = ollama.list()
            for model in models['models']:
                if model['name'] == self.model:
                    return {
                        'name': model['name'],
                        'size': model.get('size', 'Unknown'),
                        'modified_at': model.get('modified_at', 'Unknown'),
                        'available': True
                    }
            return {'name': self.model, 'available': False}
        except Exception as e:
            self.logger.error(f"Failed to get model info: {e}")
            return {'name': self.model, 'available': False, 'error': str(e)}

# Helper function to check if Ollama is running and model is available
def check_ollama_setup(model_name: str = "llama3.1:8b") -> dict:
    """Check if Ollama is properly set up with the required model"""
    try:
        # Test connection
        models = ollama.list()
        available_models = [model['name'] for model in models['models']]
        
        return {
            'ollama_running': True,
            'model_available': model_name in available_models,
            'available_models': available_models,
            'recommended_model': model_name
        }
    except Exception as e:
        return {
            'ollama_running': False,
            'error': str(e),
            'setup_instructions': [
                "1. Install Ollama from https://ollama.ai/",
                "2. Start Ollama service",
                f"3. Pull the model: ollama pull {model_name}",
                "4. Restart the application"
            ]
        }
