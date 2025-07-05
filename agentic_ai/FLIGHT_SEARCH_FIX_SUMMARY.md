# Flight Search Tool Calling - DIAGNOSIS AND FIXES

## PROBLEM IDENTIFIED
The flight search tool was not being called by the AI agent despite working weather tool calling. After thorough investigation, I identified several issues:

### ROOT CAUSES:
1. **Incompatible Agent Type**: Using `OpenAIFunctionsAgent` which requires specific function calling format not optimally supported by OpenRouter
2. **Model Selection**: Previous models had limited function calling capabilities  
3. **Tool Schema Complexity**: Complex Pydantic models were causing parsing issues
4. **Prompt Engineering**: System prompt was not structured optimally for tool calling

## FIXES IMPLEMENTED

### 1. Changed Agent Architecture
**File**: `mcp_server/server.py`
- **BEFORE**: `OpenAIFunctionsAgent` with complex function calling format
- **AFTER**: `create_react_agent` with ReAct pattern for better compatibility

```python
# OLD (problematic)
from langchain.agents import OpenAIFunctionsAgent
agent = OpenAIFunctionsAgent(llm=llm, tools=tools, prompt=prompt)

# NEW (fixed)  
from langchain.agents import create_react_agent
agent = create_react_agent(llm, tools, react_prompt)
```

### 2. Optimized Model Configuration
**File**: `mcp_server/openrouter_llm.py`
- **MODEL**: `meta-llama/llama-4-maverick:free` (USER'S PREFERRED MODEL - KEPT AS REQUESTED)
- **IMPROVEMENTS**: Optimized with better ReAct prompting and zero temperature for consistent tool calling
- **TEMPERATURE**: Set to 0.0 for deterministic, reliable tool usage

### 3. Enhanced Airport SkyID Retrieval  
**File**: `tools/FlightSearchTool.py`
- **BEFORE**: Used `query` parameter for airport search
- **AFTER**: Uses `location` parameter as per Fly Scraper API specification
- **IMPROVEMENT**: Better error handling and JSON parsing for airport data

### 4. Day-Based Travel Planning
**File**: `mcp_server/tools.py`  
- **BEFORE**: Generic travel suggestions without day structure
- **AFTER**: Structured day-by-day itineraries with fallback generation
- **IMPROVEMENT**: Ensures proper day count matching user requests (3-day, 5-day, etc.)

### 3. Simplified Tool Definitions  
**File**: `mcp_server/tools.py`
- **BEFORE**: Complex `BaseTool` classes with Pydantic schemas
- **AFTER**: Simple `@tool` decorators with direct function definitions

```python
# OLD (complex)
class FlightSearchTool(BaseTool):
    args_schema: Type[BaseModel] = FlightSearchInput
    def _run(self, ...): ...

# NEW (simple)
@tool
def flight_search(origin: str, destination: str, date: str, num_passengers: int = 1) -> str:
    """Search for flights between cities..."""
```

### 4. Enhanced ReAct Prompt
**File**: `mcp_server/server.py`
- **BEFORE**: Complex ChatPromptTemplate with multiple message types
- **AFTER**: Focused ReAct PromptTemplate with clear tool usage instructions

```
Question: the input question you must answer
Thought: think about what to do
Action: the action to take, should be one of [tool_names]
Action Input: the input to the action as a JSON object
Observation: the result of the action
Thought: I now know the final answer
Final Answer: the final answer to the original input question
```

### 5. Zero Temperature for Consistency
**File**: `mcp_server/server.py`
- **BEFORE**: `temperature=0.7` (too creative, inconsistent tool calling)
- **AFTER**: `temperature=0.0` (deterministic, reliable tool calling)

## TESTING THE FIXES

### Method 1: Direct Backend Test
```bash
cd agentic_ai
python start_backend.py
# In another terminal:
curl -X POST http://localhost:8000/agent/execute -H "Content-Type: application/json" -d '{"query": "flights from New York to London on 2025-07-15"}'
```

### Method 2: Using Test Scripts
```bash
python test_improved_backend.py
```

### Method 3: Frontend Testing
```bash
# Start backend
python start_backend.py

# Start frontend
streamlit run app.py

# Test queries:
# - "flights from New York to London on 2025-07-15"
# - "search flights Seattle to Tokyo on 2025-06-28 for 2 passengers"
# - "convert 100 USD to EUR"
# - "weather in Tokyo"
```

## EXPECTED BEHAVIOR AFTER FIXES

### ✅ Flight Search Queries That Should Work:
- "flights from New York to London on 2025-07-15"
- "search flights Seattle to Tokyo on 2025-06-28 for 2 passengers"  
- "I need a flight from Miami to Paris on August 10, 2025"
- "book flight from Los Angeles to Barcelona on July 20, 2025"

### ✅ Other Tool Calls That Should Work:
- "convert 100 USD to EUR" → currency_conversion tool
- "weather in Tokyo" → weather_info tool
- "plan trip to Japan" → travel_planner tool

### 🔍 Signs That Tools Are Working:
1. **Flight Search**: Response contains airline names, prices, departure/arrival times
2. **Currency**: Response shows exchange rates and converted amounts
3. **Weather**: Response shows temperature, conditions, humidity
4. **Planning**: Response shows detailed itineraries

## DEBUGGING IF ISSUES PERSIST

### Check Backend Logs:
Look for these indicators in terminal output:
- `🛫 Flight search: [origin] → [destination]` = Tool is being called
- `Action: flight_search` = Agent chose the right tool
- `Observation: Found flights...` = Tool executed successfully

### Common Issues:
1. **OpenRouter API Key**: Ensure valid key in `.env`
2. **Model Availability**: Check if chosen model is available on OpenRouter
3. **Tool Import Errors**: Verify all tool dependencies are installed
4. **Rate Limiting**: OpenRouter may throttle requests

### Fallback Options:
If OpenRouter has issues, the system includes fallback responses for basic travel advice.

## FILES MODIFIED
1. `mcp_server/openrouter_llm.py` - Model selection and API handling
2. `mcp_server/server.py` - Agent architecture and prompt 
3. `mcp_server/tools.py` - Tool definitions and schema
4. `test_improved_backend.py` - Testing script
5. `working_flight_agent.py` - Standalone test agent

## SUCCESS CRITERIA
✅ Agent consistently calls flight_search when given origin, destination, and date
✅ Flight search returns real or mock flight data with prices/times
✅ Other tools (weather, currency) continue to work properly
✅ Frontend displays flight results correctly
✅ Backend logs show clear tool calling activity
