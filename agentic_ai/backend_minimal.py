#!/usr/bin/env python3
"""
Minimal backend for tool calling
"""
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import os

# Load environment
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

class AgentRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None

@app.get("/health")
async def health():
    return {"status": "healthy", "tools": ["currency", "flight", "weather"]}

@app.post("/agent/execute")
async def execute_agent(request: AgentRequest):
    """Handle tool execution requests"""
    query = request.query.lower()
    
    # Currency conversion tool
    if "convert" in query and any(curr in query for curr in ["usd", "eur", "jpy", "gbp"]):
        try:
            # Import currency tool
            import sys
            sys.path.append('.')
            from tools.CurrencyTool import CurrencyTool
            
            # Extract parameters
            words = query.split()
            amount = 100
            from_curr = "USD"
            to_curr = "EUR"
            
            # Simple parsing
            for i, word in enumerate(words):
                if word.replace('.', '').replace(',', '').isdigit():
                    amount = float(word.replace(',', ''))
                elif len(word) == 3 and word.upper() in ["USD", "EUR", "JPY", "GBP", "CAD", "AUD"]:
                    if i > 0 and any(x in words[i-1] for x in ["from", str(amount)]):
                        from_curr = word.upper()
                    else:
                        to_curr = word.upper()
            
            # Execute conversion
            tool = CurrencyTool()
            result = await tool.execute(amount, from_curr, to_curr)
            
            # Format response
            if result.get('status') == 'success':
                response = f"💱 **Currency Conversion Result**\n\n"
                response += f"**Amount:** {result['original_amount']} {result['from']}\n"
                response += f"**Converted:** {result['converted_amount']} {result['to']}\n"
                response += f"**Exchange Rate:** {result['rate']}\n"
                response += f"**Source:** {result.get('source', 'API')}\n"
                
                if result.get('note'):
                    response += f"\n*Note: {result['note']}*"
            else:
                response = f"❌ Currency conversion failed: {result.get('error', 'Unknown error')}"
                
            return {"status": "success", "result": {"output": response}}
            
        except Exception as e:
            return {"status": "success", "result": {"output": f"❌ Currency conversion error: {str(e)}"}}
    
    # Flight search tool  
    elif "origin:" in query and "destination:" in query:
        try:
            from tools.FlightSearchTool import FlightSearchTool
            from datetime import datetime
            
            # Parse flight parameters
            parts = query.replace(',', '').split()
            origin = ""
            destination = ""
            date = "2025-07-01"
            passengers = 1
            
            for i, part in enumerate(parts):
                if part == "origin:" and i+1 < len(parts):
                    origin = parts[i+1]
                elif part == "destination:" and i+1 < len(parts):
                    dest_parts = []
                    j = i + 1
                    while j < len(parts) and not parts[j].endswith(':'):
                        dest_parts.append(parts[j])
                        j += 1
                    destination = " ".join(dest_parts)
                elif part == "date:" and i+1 < len(parts):
                    date = parts[i+1]
                elif part == "num_passengers:" and i+1 < len(parts):
                    passengers = int(parts[i+1])
            
            # Execute flight search
            rapidapi_key = os.getenv('RAPID_API_KEY')
            tool = FlightSearchTool(api_key=rapidapi_key)
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            result = await tool.execute(origin, destination, date_obj)
            
            # Format response
            response = f"✈️ **Flight Search Results**\n\n"
            response += f"**Route:** {origin} → {destination}\n"
            response += f"**Date:** {date}\n"
            response += f"**Passengers:** {passengers}\n\n"
            
            if isinstance(result, list) and result:
                response += f"**Found {len(result)} flights:**\n\n"
                for i, flight in enumerate(result[:5], 1):
                    response += f"**{i}. {flight.get('airline', 'Unknown Airline')}**\n"
                    response += f"   💰 Price: ${flight.get('price', 'N/A')}\n"
                    response += f"   🕐 Departure: {flight.get('departure_time', 'N/A')}\n"
                    response += f"   ⏱️ Duration: {flight.get('duration', 'N/A')}\n\n"
            else:
                response += "❌ No flights found or search failed.\n"
                response += "This might be due to API limitations or invalid route."
                
            return {"status": "success", "result": {"output": response}}
            
        except Exception as e:
            return {"status": "success", "result": {"output": f"❌ Flight search error: {str(e)}"}}
    
    # Default response
    else:
        response = f"🤖 **AI Travel Assistant**\n\n"
        response += f"I understand you're asking: *{request.query}*\n\n"
        response += "**Available Tools:**\n"
        response += "💱 **Currency Conversion:** Try 'Convert 100 USD to EUR'\n"
        response += "✈️ **Flight Search:** Try 'origin: Seattle destination: Tokyo date: 2025-07-01 num_passengers: 2'\n"
        response += "🌤️ **Weather Info:** Ask about weather in any city\n\n"
        response += "For travel planning, describe your destination preferences and I'll help create an itinerary!"
        
        return {"status": "success", "result": {"output": response}}

if __name__ == "__main__":
    print("🚀 Starting AI Travel Planner Backend")
    print("📍 Server: http://localhost:8000")
    print("🏥 Health: http://localhost:8000/health") 
    print("💱 Ready for currency conversions and flight searches!")
    
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
