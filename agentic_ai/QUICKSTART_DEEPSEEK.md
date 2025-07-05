# Quick Start Guide - Meta Llama Model Configuration

## ✅ Your Model Configuration
- **Model**: `meta-llama/llama-4-maverick:free` (Your preferred choice!)
- **Status**: ✅ Correctly configured and optimized
- **Temperature**: 0.0 (for consistent tool calling)

## 🚀 Quick Start
```bash
# Terminal 1: Start Backend
cd agentic_ai
python start_backend.py

# Terminal 2: Start Frontend  
streamlit run app.py
```

## 🧪 Test Queries
Once running, try these in the web interface:

### Flight Search
- "Find flights from New York to London on July 15, 2025"
- "Search for flights Mumbai to Delhi tomorrow"
- "Show me flights from San Francisco to Tokyo next week"

### Travel Planning
- "Plan a 3-day trip to Tokyo"
- "Create a 5-day itinerary for Paris with weather info"
- "Plan a week in Thailand with budget and currency info"

### Multi-Tool Usage
- "I need flights from NYC to London, weather forecast, and currency conversion USD to GBP"

## 🎯 Model Benefits
Your chosen model `meta-llama/llama-4-maverick:free` offers:
- ✅ Free usage via OpenRouter
- ✅ Good reasoning capabilities  
- ✅ Compatible with tool calling (with proper prompting)
- ✅ Reliable for travel planning tasks

## 🔧 Optimizations Made
All improvements were designed to work optimally with your preferred model:
- ReAct agent pattern for better tool calling
- Zero temperature for consistency
- Enhanced prompting for tool usage
- Simplified tool definitions
- Better error handling

**Your model choice is preserved and optimized! 🎉**
