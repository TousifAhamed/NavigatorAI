#!/usr/bin/env python3
"""
MCP Server runner for AI Travel Planner
This script starts the MCP server that provides travel planning tools.
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Ensure we're in the right directory and can import our modules
current_dir = Path(__file__).parent
os.chdir(current_dir)
sys.path.insert(0, str(current_dir))

def main():
    """Main entry point for the MCP server"""
    try:
        # Load environment variables with explicit path
        env_path = Path(__file__).parent / '.env'
        load_dotenv(env_path)
        
        # Import required modules
        import uvicorn
        from mcp_server.server import MCPServer
        from mcp_server.tools import register_tools
        from tools.travel_tools import ItineraryPlannerTool
        from tools.travel_utils import TravelUtils
        
        # Get API configuration
        openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        rapidapi_key = os.getenv('RAPID_API_KEY')
        
        # Initialize components
        planner_tool = ItineraryPlannerTool(
            openrouter_api_key=openrouter_api_key,
            site_url=os.getenv('SITE_URL', 'http://localhost:8501'),
            site_name=os.getenv('SITE_NAME', 'AI Travel Planner')
        )
        
        travel_utils = TravelUtils(rapidapi_key=rapidapi_key)
        mcp_server = MCPServer()
        
        # Register tools and setup agent
        tools = register_tools(mcp_server, travel_utils, planner_tool)
        mcp_server.setup_agent(tools)
        
        print(f"🌍 AI Travel Planner MCP Server starting...")
        print(f"🔧 Tools registered: {len(tools)}")
        print(f"🔑 OpenRouter API: {'✅' if openrouter_api_key else '❌'}")
        print(f"🔑 RapidAPI: {'✅' if rapidapi_key else '❌'}")
        print(f"🚀 Server URL: http://localhost:8000")
        
        # Start the server
        uvicorn.run(
            mcp_server.app, 
            host="0.0.0.0", 
            port=8000, 
            log_level="info"
        )
        
    except Exception as e:
        print(f"❌ Error starting MCP server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
