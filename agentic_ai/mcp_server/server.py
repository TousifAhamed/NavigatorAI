"""
MCP Server implementation using FastAPI.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory
from .ollama_llm import OllamaLLM, check_ollama_setup
import uvicorn
import os
import asyncio
import nest_asyncio
from dotenv import load_dotenv
import json
import uuid
import logging
from datetime import datetime, timedelta

# Load environment variables
from pathlib import Path
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Enable nested asyncio
nest_asyncio.apply()

class ToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

class AgentRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    session_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
        
    def model_dump(self, **kwargs):
        """Custom serialization to handle nested Pydantic models."""
        data = super().model_dump(**kwargs)
        if "context" in data and isinstance(data["context"], dict):
            for key, value in data["context"].items():
                if hasattr(value, "model_dump"):
                    data["context"][key] = value.model_dump()
        return data

class ConversationSession:
    """Manages conversation state for a user session"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.memory = ConversationBufferWindowMemory(
            k=10,  # Keep last 10 exchanges
            return_messages=True,
            memory_key="chat_history",
            input_key="input"
        )
        self.context = {}
        self.preferences = {}
        
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history"""
        if role == "user":
            self.memory.chat_memory.add_user_message(content)
        elif role == "assistant":
            self.memory.chat_memory.add_ai_message(content)
        self.last_activity = datetime.now()
        
    def get_messages(self) -> List[Dict[str, str]]:
        """Get conversation history as a list of dicts"""
        messages = []
        for msg in self.memory.chat_memory.messages:
            if isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})
        return messages
        
    def is_expired(self, max_age_hours: int = 24) -> bool:
        """Check if session has expired"""
        return datetime.now() - self.last_activity > timedelta(hours=max_age_hours)

class MCPServer:
    def __init__(self):
        self.app = FastAPI(title="Travel Planner MCP Server")
        self.tools = {}
        self.agent_executor = None
        self.conversation_sessions = {}  # session_id -> ConversationSession
        
        # Set up logging
        self.logger = logging.getLogger("TravelPlanner.MCPServer")
        self.logger.info("Initializing MCP Server")
        
        self.setup_routes()
        
    def get_or_create_session(self, session_id: str) -> ConversationSession:
        """Get existing session or create a new one"""
        if session_id not in self.conversation_sessions:
            self.logger.info(f"Creating new conversation session: {session_id}")
            self.conversation_sessions[session_id] = ConversationSession(session_id)
        else:
            self.logger.debug(f"Using existing conversation session: {session_id}")
        return self.conversation_sessions[session_id]
        
    def cleanup_expired_sessions(self):
        """Remove expired conversation sessions"""
        expired_sessions = [
            session_id for session_id, session in self.conversation_sessions.items()
            if session.is_expired()
        ]
        if expired_sessions:
            self.logger.info(f"Cleaning up {len(expired_sessions)} expired sessions")
        for session_id in expired_sessions:
            del self.conversation_sessions[session_id]
        
    def setup_routes(self):
        @self.app.post("/invoke_tool")
        async def invoke_tool(request: ToolRequest):
            self.logger.info(f"Tool invocation request: {request.tool_name}")
            self.logger.debug(f"Tool parameters: {request.parameters}")
            
            if request.tool_name not in self.tools:
                self.logger.error(f"Tool not found: {request.tool_name}")
                raise HTTPException(status_code=404, detail=f"Tool {request.tool_name} not found")
            
            tool = self.tools[request.tool_name]
            try:
                self.logger.info(f"Executing tool: {request.tool_name}")
                result = await tool.arun(**request.parameters)
                self.logger.info(f"Tool execution successful: {request.tool_name}")
                self.logger.debug(f"Tool result: {result}")
                return {"status": "success", "result": result}
            except Exception as e:
                self.logger.error(f"Tool execution failed: {request.tool_name} - {str(e)}")
                error_msg = str(e)
                if hasattr(e, 'detail'):
                    error_msg = e.detail
                raise HTTPException(status_code=500, detail={"error": error_msg})

        @self.app.post("/agent/execute")
        async def execute_agent(request: AgentRequest):
            self.logger.info(f"Agent execution request received")
            self.logger.debug(f"Query: {request.query}")
            
            if not self.agent_executor:
                # Return a fallback response when agent is not available
                self.logger.warning("Agent not available, returning fallback response")
                
                # Generate a simple structured response based on the query
                query_lower = request.query.lower()
                
                if any(word in query_lower for word in ['suggest', 'recommend', 'ideas', 'where']):
                    # Destination suggestions
                    fallback_response = """* Tokyo, Japan for its blend of modern technology and traditional culture, featuring world-class sushi and ramen
* Barcelona, Spain for its stunning Gaudi architecture, vibrant tapas scene, and Mediterranean charm"""
                
                elif any(word in query_lower for word in ['plan', 'itinerary', 'schedule', 'day']):
                    # Itinerary planning
                    fallback_response = """Day 1:
- Morning: Explore the historic downtown area and visit local museums
- Afternoon: Take a guided food tour and sample local cuisine  
- Evening: Enjoy sunset views from a scenic viewpoint

Day 2:
- Morning: Visit famous landmarks and take photos
- Afternoon: Shop for souvenirs in local markets
- Evening: Experience the nightlife and entertainment districts"""
                
                else:
                    # General travel advice
                    fallback_response = "I'd be happy to help with your travel planning! Please ask for destination suggestions or help planning a specific itinerary."
                
                return {
                    "status": "success",
                    "result": {"output": fallback_response},
                    "session_id": "fallback_session",
                    "note": "Using fallback mode - OpenRouter API not available"
                }
            
            try:
                # Clean up expired sessions
                self.cleanup_expired_sessions()
                
                # Get or create session
                session_id = request.session_id or str(uuid.uuid4())
                session = self.get_or_create_session(session_id)
                self.logger.info(f"Processing request for session: {session_id}")
                
                # Add user message to conversation history
                session.add_message("user", request.query)
                
                # Update session context with new information
                if request.context:
                    session.context.update(request.context)
                    self.logger.debug(f"Updated session context: {session.context}")
                
                # Prepare input with conversation history
                memory_variables = session.memory.load_memory_variables({})
                chat_history = memory_variables.get("chat_history", [])
                self.logger.debug(f"Chat history length: {len(chat_history)}")
                
                # Convert request to dict with proper serialization
                request_dict = request.model_dump()
                
                # Create input with conversation context
                agent_input = {
                    "input": request_dict["query"],
                    "context": session.context,
                    "chat_history": chat_history
                }
                
                self.logger.info("Executing agent with input")
                result = await self.agent_executor.ainvoke(agent_input)
                self.logger.info("Agent execution completed successfully")
                self.logger.debug(f"Agent result: {result}")
                
                # Add assistant response to conversation history
                if "output" in result:
                    session.add_message("assistant", result["output"])
                
                return {
                    "status": "success", 
                    "result": result,
                    "session_id": session_id,
                    "conversation_history": session.get_messages()
                }
            except Exception as e:
                self.logger.error(f"Agent execution failed: {str(e)}", exc_info=True)
                error_msg = str(e)
                if hasattr(e, 'detail'):
                    error_msg = e.detail
                raise HTTPException(status_code=500, detail={"error": error_msg})
                
        @self.app.get("/conversation/{session_id}")
        async def get_conversation(session_id: str):
            """Get conversation history for a session"""
            self.logger.info(f"Retrieving conversation for session: {session_id}")
            
            if session_id not in self.conversation_sessions:
                self.logger.warning(f"Session not found: {session_id}")
                raise HTTPException(status_code=404, detail="Session not found")
            
            session = self.conversation_sessions[session_id]
            self.logger.debug(f"Retrieved conversation with {len(session.get_messages())} messages")
            
            return {
                "session_id": session_id,
                "conversation_history": session.get_messages(),
                "context": session.context,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            }
            
        @self.app.delete("/conversation/{session_id}")
        async def delete_conversation(session_id: str):
            """Delete a conversation session"""
            self.logger.info(f"Deleting conversation session: {session_id}")
            
            if session_id in self.conversation_sessions:
                del self.conversation_sessions[session_id]
                self.logger.info(f"Successfully deleted session: {session_id}")
            else:
                self.logger.warning(f"Attempted to delete non-existent session: {session_id}")
            
            return {"status": "success", "message": "Session deleted"}

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint to verify server status"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "tools_registered": len(self.tools),
                "agent_available": self.agent_executor is not None,
                "tools": list(self.tools.keys())
            }

        @self.app.get("/tools")
        async def list_tools():
            """List all available tools"""
            self.logger.info("Listing available tools")
            return {
                "tools": list(self.tools.keys()),
                "count": len(self.tools)
            }

    def register_tool(self, tool_name: str, tool):
        """Register a new tool with the MCP server."""
        self.logger.info(f"Registering tool: {tool_name}")
        self.tools[tool_name] = tool
        self.logger.debug(f"Tool registered successfully: {tool_name}")

    def setup_agent(self, tools):
        """Set up the LangChain agent with OpenRouter LLM."""
        self.logger.info("Setting up agent with OpenRouter LLM")
        
        # Check Ollama setup first
        self.logger.info("Checking Ollama setup")
        ollama_status = check_ollama_setup("devstral:latest")
        
        if not ollama_status['ollama_running']:
            self.logger.error("Ollama is not running!")
            for instruction in ollama_status.get('setup_instructions', []):
                self.logger.info(instruction)
            self.agent_executor = None
            return
            
        if not ollama_status['model_available']:
            self.logger.warning(f"Model devstral:latest not available. Available models: {ollama_status.get('available_models', [])}")
            self.logger.info("To install the model, run: ollama pull devstral:latest")
            # Try to use the first available model if any
            available_models = ollama_status.get('available_models', [])
            if available_models:
                model_to_use = available_models[0]
                self.logger.info(f"Using available model: {model_to_use}")
            else:
                self.logger.error("No models available in Ollama")
                self.agent_executor = None
                return
        else:
            model_to_use = "devstral:latest"
            self.logger.info("Found devstral:latest model")
        
        try:
            self.logger.info(f"Initializing Ollama LLM with model: {model_to_use}")
            llm = OllamaLLM(
                model=model_to_use,
                temperature=0.1,  # Consistent temperature for reliable responses
                num_predict=4000,  # Increased for better responses
                host=os.getenv('OLLAMA_HOST', 'http://localhost:11434')
            )
            
            # Test the LLM with a simple query
            self.logger.info("Testing LLM connection")
            test_response = llm._call("Hello, please respond with 'LLM connection successful'")
            self.logger.info(f"LLM test response: {test_response[:100]}...")
            
            # Create ReAct prompt template for better compatibility
            self.logger.debug("Creating ReAct prompt template")
            react_prompt = PromptTemplate.from_template("""You are an expert AI travel assistant. You MUST use tools to answer user questions about travel.

Available tools: {tools}

CRITICAL: You MUST follow this EXACT format for every response:

Question: the input question you must answer
Thought: I need to help the user with their travel request. Let me think about what tool to use.
Action: [EXACT_TOOL_NAME]
Action Input: {{"parameter": "value"}}
Observation: [tool result will appear here]
Thought: Based on the observation, I can now provide a helpful response
Final Answer: [your complete response to the user]

MANDATORY RULES:
1. ALWAYS write "Action:" (with colon) before the tool name
2. ALWAYS write "Action Input:" (with colon) before the JSON parameters
3. Use EXACT tool names from: {tool_names}
4. Use proper JSON format for Action Input
5. NEVER skip the Action/Action Input format

TOOL USAGE:
- For flight questions: use "intelligent_flight_search" with natural language
- For weather: use "weather_info" 
- For currency: use "currency_conversion"
- For trip planning: use "travel_planner"

Question: {input}
Thought: {agent_scratchpad}""")

            # Create the agent using ReAct pattern
            self.logger.info("Creating ReAct agent")
            agent = create_react_agent(llm, tools, react_prompt)

            # Create the agent executor with enhanced error handling
            self.logger.info("Creating agent executor")
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors="Check your output and make sure it follows the exact format:\nThought: [your thinking]\nAction: [tool name]\nAction Input: {\"parameter\": \"value\"}\nThen wait for the Observation.",
                max_iterations=8,  # Reduced to prevent infinite loops
                max_execution_time=90,  # 1.5 minutes timeout
                return_intermediate_steps=True,
                early_stopping_method="generate"
            )
            
            self.logger.info("MCP Agent successfully initialized with tools")
            
        except Exception as e:
            self.logger.error(f"Error initializing MCP agent: {str(e)}", exc_info=True)
            if "model" in str(e).lower() and "not found" in str(e).lower():
                self.logger.error("The specified Ollama model was not found.")
                self.logger.info("Available models can be listed with: ollama list")
                self.logger.info("Install the model with: ollama pull llama3.1:8b")
            elif "connection" in str(e).lower() or "refused" in str(e).lower():
                self.logger.error("Cannot connect to Ollama service.")
                self.logger.info("Make sure Ollama is running. Start it with: ollama serve")
                self.logger.info("Or check if Ollama is installed: https://ollama.ai/")
            self.agent_executor = None
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the MCP server."""
        self.logger.info(f"Starting MCP server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port)
    
    def run_async(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the MCP server asynchronously."""
        self.logger.info(f"Starting MCP server asynchronously on {host}:{port}")
        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        
        # Use asyncio to run the server
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

if __name__ == "__main__":
    server = MCPServer()
    server.run()