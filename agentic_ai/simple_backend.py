#!/usr/bin/env python3
"""
Simplified backend server for tool calling
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import asyncio
import os
from typing import Dict, Any, Optional

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="AI Travel Planner Backend")

class AgentRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

class ToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]

# Initialize tools
tools = {}

def setup_tools():
    """Setup tools for the backend"""
    global tools
    
    try:
        # Import tools
        from tools.CurrencyTool import CurrencyTool
        from tools.FlightSearchTool import FlightSearchTool
        from tools.Weathertool import WeatherTool
        
        # Create tool instances
        rapidapi_key = os.getenv('RAPID_API_KEY')
        
        tools['currency'] = CurrencyTool()
        tools['flight'] = FlightSearchTool(api_key=rapidapi_key)
        tools['weather'] = WeatherTool()
        
        print(f"✅ {len(tools)} tools initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Tool setup failed: {e}")
        return False

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "tools_available": len(tools),
        "tools": list(tools.keys()),
        "backend": "simplified"
    }

@app.post("/agent/execute")
async def execute_agent(request: AgentRequest):
    """Execute agent with tool calling"""
    try:
        query = request.query.lower()
        
        # Simple tool routing based on query content
        if "convert" in query and ("usd" in query or "eur" in query or "jpy" in query):
            # Currency conversion
            print(f"💱 Currency request detected: {request.query}")
            
            # Extract currency conversion parameters (simple parsing)
            words = request.query.split()
            amount = 100  # default
            from_curr = "USD"
            to_curr = "EUR"
            
            # Try to extract amount and currencies
            for i, word in enumerate(words):
                if word.replace('.', '').isdigit():
                    amount = float(word)
                if len(word) == 3 and word.isupper():
                    if "from" in words[max(0, i-2):i] or i > 0 and words[i-1].isdigit():
                        from_curr = word
                    elif "to" in words[max(0, i-2):i]:
                        to_curr = word
            
            if 'currency' in tools:
                result = await tools['currency'].execute(amount, from_curr, to_curr)
                
                response = f"💱 Currency Conversion Result:\n"
                response += f"Amount: {result.get('original_amount', amount)} {result.get('from', from_curr)}\n"
                response += f"Converted: {result.get('converted_amount', 'N/A')} {result.get('to', to_curr)}\n"
                response += f"Exchange Rate: {result.get('rate', 'N/A')}\n"
                response += f"Source: {result.get('source', 'unknown')}"
                
                return {"status": "success", "result": {"output": response}}
            
        elif "origin:" in query and "destination:" in query:
            # Flight search
            print(f"✈️ Flight search request detected: {request.query}")
            
            # Extract flight parameters
            parts = request.query.split()
            origin = ""
            destination = ""
            date = "2025-07-01"
            passengers = 1
            
            for i, part in enumerate(parts):
                if part == "origin:" and i+1 < len(parts):
                    origin = parts[i+1]
                elif part == "destination:" and i+1 < len(parts):
                    destination = " ".join(parts[i+1:i+3])  # Handle multi-word destinations
                elif part == "date:" and i+1 < len(parts):
                    date = parts[i+1]
                elif part == "num_passengers:" and i+1 < len(parts):
                    passengers = int(parts[i+1])
            
            if 'flight' in tools and origin and destination:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                result = await tools['flight'].execute(origin, destination, date_obj)
                
                response = f"✈️ Flight Search Results:\n"
                response += f"Route: {origin} → {destination}\n"
                response += f"Date: {date}\n"
                response += f"Passengers: {passengers}\n\n"
                
                if isinstance(result, list) and result:
                    response += f"Found {len(result)} flights:\n"
                    for i, flight in enumerate(result[:3], 1):  # Show first 3 flights
                        response += f"\n{i}. {flight.get('airline', 'Unknown')} - ${flight.get('price', 'N/A')}\n"
                        response += f"   Departure: {flight.get('departure_time', 'N/A')}\n"
                        response += f"   Duration: {flight.get('duration', 'N/A')}\n"
                else:
                    response += "No flights found or search failed."
                
                return {"status": "success", "result": {"output": response}}
        
        # Default response for other queries
        response = f"I received your query: '{request.query}'\n\n"
        response += "Available tools:\n"
        response += "💱 Currency conversion: 'Convert 100 USD to EUR'\n"
        response += "✈️ Flight search: 'origin: Seattle destination: Tokyo date: 2025-07-01 num_passengers: 2'\n"
        response += "🌤️ Weather info: Ask about weather in any city"
        
        return {"status": "success", "result": {"output": response}}
        
    except Exception as e:
        print(f"❌ Agent execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🚀 Starting Simplified AI Travel Planner Backend")
    print("=" * 50)
    
    # Setup tools
    if setup_tools():
        print("🌐 Starting server on http://localhost:8000")
        print("📋 Health check: http://localhost:8000/health")
        print("🤖 Agent endpoint: http://localhost:8000/agent/execute")
        print("=" * 50)
        
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    else:
        print("❌ Failed to setup tools. Cannot start server.")
