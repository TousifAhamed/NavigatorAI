# NavigatorAI - AI-Powered Travel Planner 🌍✈️

A sophisticated AI travel planning assistant powered by local Ollama LLM and real-time API integrations.

## 🚀 Features

### ✨ Core Capabilities
- **Local AI Processing**: Powered by Ollama LLM (devstral:latest) for privacy and offline capability
- **Real-time Flight Search**: Integrated with Amadeus API for live flight data
- **Intelligent Request Processing**: Smart detection of flight searches vs. comprehensive travel planning
- **Enhanced UI**: Modern Streamlit interface with progress tracking and rich formatting

### 🛫 Flight Integration
- **Mandatory Flight Search**: Every travel suggestion includes relevant flight options
- **Smart Origin/Destination Extraction**: Robust parsing of complex user prompts
- **Date Intelligence**: Automatic extraction and parsing of travel dates
- **Real-time Results**: Live flight search with fallback to mock data

### 🎯 Travel Planning
- **Comprehensive Suggestions**: Detailed destination recommendations with activities, accommodation, and local tips
- **Day-by-Day Itineraries**: Structured travel plans with daily activities
- **Visa Information**: Essential travel documentation requirements
- **Local Insights**: Cultural tips and practical advice for each destination

## 🏗️ Architecture

### Technology Stack
- **Frontend**: Streamlit with enhanced UI components
- **AI Engine**: Ollama LLM with Model Context Protocol (MCP)
- **APIs**: 
  - Amadeus (Flight Search)
  - RapidAPI (Hotel Search, Weather)
  - Currency Conversion APIs
- **Backend**: Python with async processing

### Project Structure
```
agentic_ai/
├── app.py                 # Main Streamlit application
├── agents/
│   └── travel_agent.py    # AI agent with enhanced prompts
├── tools/
│   ├── travel_tools.py    # Core travel planning tools
│   ├── amadeus_flight_search.py
│   ├── CurrencyTool.py
│   └── HotelSearchTool.py
├── mcp_server/
│   ├── server.py          # MCP server implementation
│   ├── ollama_llm.py      # Ollama integration
│   └── tools.py           # Tool definitions
└── requirements.txt
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Ollama installed with devstral:latest model
- API keys for Amadeus and other services

### Installation
1. **Clone the repository**
   ```bash
   git clone https://github.com/TousifAhamed/NavigatorAI.git
   cd NavigatorAI
   ```

2. **Install dependencies**
   ```bash
   cd agentic_ai
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env_template.txt .env
   # Edit .env with your API keys
   ```

4. **Start Ollama and pull the model**
   ```bash
   ollama serve
   ollama pull devstral:latest
   ```

5. **Run the application**
   ```bash
   # Start backend
   python start_backend.py
   
   # In another terminal, start frontend
   streamlit run app.py
   ```

### Environment Variables Required
```env
AMADEUS_CLIENT_ID=your_amadeus_client_id
AMADEUS_CLIENT_SECRET=your_amadeus_client_secret
RAPIDAPI_KEY=your_rapidapi_key
CURRENCY_API_KEY=your_currency_api_key
WEATHER_API_KEY=your_weather_api_key
```

## 📖 Usage

### Travel Suggestions Mode
1. Enter your travel preferences in the sidebar
2. Describe your travel desires in natural language
3. The AI will provide personalized suggestions with flight options

### Flight Search Mode
1. Use specific flight queries like "flights from NYC to Paris"
2. Get real-time flight options with prices and schedules

### Itinerary Planning
1. Request detailed day-by-day planning
2. Receive structured itineraries with activities and logistics

## 🎯 Key Features Explained

### Smart Request Detection
The system automatically detects whether you're asking for:
- Pure flight searches
- Comprehensive travel planning
- Detailed itinerary creation

### Enhanced UI Experience
- **Progress Tracking**: Real-time status updates during processing
- **Rich Formatting**: Beautiful cards and layouts for suggestions
- **Flight Integration**: Seamless display of flight options with each suggestion
- **Metrics Display**: Key information at a glance

### Robust Data Extraction
- **Origin/Destination**: Smart parsing from complex user inputs
- **Travel Dates**: Intelligent date extraction and defaulting
- **User Preferences**: Sidebar controls for personalization

## 🔧 API Integration

### Amadeus Flight Search
- Real-time flight data
- Price comparison
- Schedule information
- Fallback to mock data if API unavailable

### Additional APIs
- **Hotels**: RapidAPI integration for accommodation
- **Weather**: Current and forecast information
- **Currency**: Real-time exchange rates

## 📊 Migration History

This project represents a complete migration from OpenRouter to local Ollama LLM:

### ✅ Completed Migrations
- ❌ OpenRouter API → ✅ Ollama LLM (devstral:latest)
- ❌ Mock flight data → ✅ Amadeus API integration
- ❌ Basic UI → ✅ Enhanced progress tracking and formatting
- ❌ Simple prompts → ✅ Sophisticated prompt engineering
- ❌ Limited extraction → ✅ Robust context and date parsing

### 🧹 Cleanup
- Removed all legacy OpenRouter dependencies
- Cleaned up obsolete directories (base_llm, geoclip_api, sft)
- Consolidated duplicate tools and configurations
- Removed test files after successful validation

## 🚀 Deployment

The application is designed for easy deployment:

1. **Local Development**: Run with Ollama on local machine
2. **Cloud Deployment**: Can be deployed to any cloud platform supporting Python
3. **Docker Ready**: Containerization possible for consistent deployment

## 📝 Documentation

See the `/agentic_ai/` directory for detailed documentation:
- `OLLAMA_MIGRATION_GUIDE.md` - Migration details
- `QUICK_START.md` - Getting started guide
- `RUN_INSTRUCTIONS.md` - Detailed setup instructions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Ollama team for the excellent local LLM framework
- Amadeus for comprehensive travel APIs
- Streamlit for the intuitive UI framework
- The open-source community for various tools and libraries

---

**NavigatorAI** - Your intelligent travel companion, powered by cutting-edge AI and real-time data integration.
