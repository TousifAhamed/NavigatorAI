#!/usr/bin/env python3
"""
All-in-one startup script for the AI Travel Planner backend
"""

import os
import sys
import subprocess
import time
import asyncio
from pathlib import Path

def main():
    print("=" * 50)
    print("    AI Travel Planner - Backend Startup")
    print("=" * 50)
    print()
    
    # Check if we're in the right directory
    if not os.path.exists("mcp_server"):
        print("❌ Error: mcp_server directory not found")
        print("Please run this script from the agentic_ai directory")
        input("Press Enter to exit...")
        return
    
    # Test imports first
    print("[1/3] Testing imports...")
    try:
        import uvicorn
        from fastapi import FastAPI
        print("   ✓ FastAPI and uvicorn available")
        
        # Try importing our modules
        from mcp_server.server import MCPServer
        print("   ✓ MCPServer import successful")
        
        from mcp_server.tools import register_tools
        print("   ✓ Tools import successful")
        
        from tools.travel_tools import ItineraryPlannerTool
        from tools.travel_utils import TravelUtils
        print("   ✓ Travel tools import successful")
        
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        input("Press Enter to exit...")
        return
    
    print("\n[2/3] Setting up server...")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Get API keys
        rapidapi_key = os.getenv('RAPID_API_KEY')
        
        print(f"   RapidAPI Key: {'SET' if rapidapi_key else 'NOT SET'}")
        
        # Initialize components (now using Ollama, no OpenRouter needed)
        planner_tool = ItineraryPlannerTool()
        
        travel_utils = TravelUtils(rapidapi_key=rapidapi_key)
        mcp_server = MCPServer()
        
        # Register tools
        tools = register_tools(mcp_server, travel_utils, planner_tool)
        mcp_server.setup_agent(tools)
        
        print(f"   ✓ Server initialized with {len(tools)} tools")
        
    except Exception as e:
        print(f"   ❌ Setup error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        return
    
    print("\n[3/3] Starting server...")
    print("🚀 MCP Server starting on http://localhost:8000")
    print("📋 Health check: http://localhost:8000/health")
    print("🤖 Agent endpoint: http://localhost:8000/agent/execute")
    print("\nPress Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        uvicorn.run(mcp_server.app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
