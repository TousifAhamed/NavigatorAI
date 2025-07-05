import streamlit as st
import asyncio
from datetime import datetime, timedelta
import nest_asyncio
from agents.travel_agent import TravelPreferences, ProcessedInput, TravelRequest
from tools.travel_utils import TravelUtils
from tools.travel_tools import ItineraryPlannerTool
from mcp_server import MCPServer, register_tools
import os
from dotenv import load_dotenv
from typing import Dict, Any, List, Tuple
import httpx
import json
import logging
import traceback
import sys
from pathlib import Path
import re

# Load environment variables
# Ensure we load from the correct path
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Setup enhanced logging
def setup_logging():
    """Setup logging with both console and file output"""
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp
    log_filename = logs_dir / f"travel_planner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Setup console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '\033[92m%(asctime)s\033[0m - \033[94m%(name)s\033[0m - \033[93m%(levelname)s\033[0m - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Setup file handler
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger

# Initialize logging
logger = setup_logging()

# Log startup
logger.info("🚀 AI Travel Planner Starting Up")

def extract_origin_destination(user_input: str, preferred_departure_city: str) -> Tuple[str, str]:
    """
    Extracts origin and destination from user input, with fallback to preferred city.
    Returns (origin, destination).
    """
    input_lower = user_input.lower()
    origin = None
    destination = None

    # IATA airport code to city mapping
    iata_to_city = {
        'dmm': 'Dammam', 'szx': 'Shenzhen', 'bom': 'Mumbai', 'del': 'Delhi', 
        'blr': 'Bangalore', 'maa': 'Chennai', 'hyd': 'Hyderabad', 'ccu': 'Kolkata',
        'lhr': 'London', 'cdg': 'Paris', 'nrt': 'Tokyo', 'jfk': 'New York', 
        'lga': 'New York', 'ewr': 'New York', 'dxb': 'Dubai', 'sin': 'Singapore',
        'bkk': 'Bangkok', 'dps': 'Bali', 'sfo': 'San Francisco', 'lax': 'Los Angeles',
        'ord': 'Chicago', 'syd': 'Sydney', 'mel': 'Melbourne', 'yyz': 'Toronto',
        'yvr': 'Vancouver', 'pvg': 'Shanghai', 'pek': 'Beijing', 'icn': 'Seoul',
        'hkg': 'Hong Kong', 'tpe': 'Taipei', 'kul': 'Kuala Lumpur'
    }

    # More comprehensive list of common cities for robustness
    common_cities = {
        'mumbai': 'Mumbai', 'delhi': 'Delhi', 'bangalore': 'Bangalore',
        'chennai': 'Chennai', 'hyderabad': 'Hyderabad', 'kolkata': 'Kolkata',
        'london': 'London', 'paris': 'Paris', 'tokyo': 'Tokyo',
        'new york': 'New York', 'dubai': 'Dubai', 'singapore': 'Singapore',
        'bangkok': 'Bangkok', 'bali': 'Bali', 'san francisco': 'San Francisco',
        'los angeles': 'Los Angeles', 'chicago': 'Chicago', 'sydney': 'Sydney',
        'melbourne': 'Melbourne', 'toronto': 'Toronto', 'vancouver': 'Vancouver',
        'dammam': 'Dammam', 'shenzhen': 'Shenzhen', 'shanghai': 'Shanghai',
        'beijing': 'Beijing', 'seoul': 'Seoul', 'hong kong': 'Hong Kong',
        'taipei': 'Taipei', 'kuala lumpur': 'Kuala Lumpur'
    }

    logger.info(f"Processing input: {user_input[:100]}...")

    # 1. First priority: Look for IATA codes in parentheses (e.g., "(DMM)" and "(SZX)")
    iata_matches = re.findall(r'\(([A-Z]{3})\)', user_input.upper())
    logger.info(f"Found IATA codes: {iata_matches}")
    
    if len(iata_matches) >= 2:
        origin_iata = iata_matches[0].lower()
        destination_iata = iata_matches[1].lower()
        
        origin = iata_to_city.get(origin_iata, origin_iata.upper())
        destination = iata_to_city.get(destination_iata, destination_iata.upper())
        
        logger.info(f"Extracted from IATA codes: {origin} ({origin_iata.upper()}) -> {destination} ({destination_iata.upper()})")
        return origin, destination

    # 2. Look for "from [origin] to [destination]" patterns with enhanced regex
    from_to_patterns = [
        r'from\s+([^,\n]+(?:,\s*[^,\n]+)*)\s+(?:\([A-Z]{3}\)\s+)?to\s+([^,\n]+(?:,\s*[^,\n]+)*)',
        r'from\s+([a-zA-Z\s,]+)\s+to\s+([a-zA-Z\s,]+)',
        r'flight.*from\s+([a-zA-Z\s,]+)\s+to\s+([a-zA-Z\s,]+)'
    ]
    
    for pattern in from_to_patterns:
        match = re.search(pattern, input_lower, re.IGNORECASE)
        if match:
            origin_text = match.group(1).strip().rstrip(',')
            destination_text = match.group(2).strip().rstrip(',')
            
            # Clean up text by removing extra phrases
            origin_text = re.sub(r'\s*\([A-Z]{3}\)', '', origin_text, flags=re.IGNORECASE)
            destination_text = re.sub(r'\s*\([A-Z]{3}\)', '', destination_text, flags=re.IGNORECASE)
            
            # Try to match against known cities
            for city_key, city_name in common_cities.items():
                if not origin and city_key in origin_text.lower():
                    origin = city_name
                if not destination and city_key in destination_text.lower():
                    destination = city_name
            
            # If still not found, use the cleaned text as-is (capitalized)
            if not origin:
                origin = origin_text.title()
            if not destination:
                destination = destination_text.title()
                
            if origin and destination:
                logger.info(f"Extracted from pattern: {origin} -> {destination}")
                return origin, destination

    # 3. Identify all cities mentioned and use context
    detected_cities = []
    for city_key, city_name in common_cities.items():
        if re.search(r'\b' + re.escape(city_key) + r'\b', input_lower):
            detected_cities.append(city_name)
    
    logger.info(f"Detected cities in input: {detected_cities}")

    # If only one city is detected, it's the destination
    if len(detected_cities) == 1:
        destination = detected_cities[0]
        if preferred_departure_city:
            origin = preferred_departure_city
            logger.info(f"Extracted from single detected city and preference: {origin} -> {destination}")
            return origin, destination

    # If multiple cities are detected, look for contextual clues
    if len(detected_cities) > 1:
        # Check if one of the detected cities is the preferred departure city
        if preferred_departure_city and preferred_departure_city in detected_cities:
            origin = preferred_departure_city
            # The other city is the destination
            remaining_cities = [city for city in detected_cities if city != origin]
            if remaining_cities:
                destination = remaining_cities[0]
                logger.info(f"Extracted from multiple cities with preference: {origin} -> {destination}")
                return origin, destination
        else:
            # Default to the first as origin and second as destination if no other clues
            origin, destination = detected_cities[0], detected_cities[1]
            logger.info(f"Extracted from multiple detected cities: {origin} -> {destination}")
            return origin, destination

    # 4. Fallback to preferred departure city if no destination is found
    if preferred_departure_city and not destination:
        origin = preferred_departure_city
        logger.info(f"Using preferred departure city as origin: {origin}")

    # Final check for any detected city as destination
    if origin and not destination and detected_cities:
        destination = detected_cities[0]

    logger.info(f"Final extracted entities: Origin='{origin}', Destination='{destination}'")
    return origin, destination

# JSON serialization helper
def json_serializable(obj):
    """Convert objects to JSON-serializable format"""
    logger.debug(f"Converting to JSON serializable: {type(obj)}")
    if isinstance(obj, datetime):
        result = obj.isoformat()
        logger.debug(f"Converted datetime {obj} to {result}")
        return result
    elif isinstance(obj, dict):
        return {key: json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [json_serializable(item) for item in obj]
    else:
        return obj

# Define constants
AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8000")  # Default to localhost if not set
logger.info(f"🌐 Using Agent URL: {AGENT_URL}")

# Set page config must be the first Streamlit command
st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="✈️",
    layout="wide"
)

# Enable nested asyncio for Streamlit
nest_asyncio.apply()

# Initialize session state for conversation management
if 'conversation_session_id' not in st.session_state:
    st.session_state.conversation_session_id = None
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = "Get Travel Suggestions"

# Initialize the MCP server and tools
@st.cache_resource(show_spinner="Loading AI Travel Planner...")
def initialize_mcp_server():
    """Initialize and cache the MCP server with all tools"""
    try:
        # Get API configuration
        rapidapi_key = os.getenv('RAPID_API_KEY')
        site_url = os.getenv('SITE_URL', 'http://localhost:8501')
        site_name = os.getenv('SITE_NAME', 'AI Travel Planner')
        
        if not rapidapi_key:
            st.warning("RapidAPI key not found. Flight and hotel data will be unavailable.")
        
        # Initialize the planner tool (now using Ollama, no OpenRouter key needed)
        planner_tool = ItineraryPlannerTool()
        
        # Initialize travel utils
        travel_utils = TravelUtils(rapidapi_key=rapidapi_key)
          # Initialize MCP server
        mcp_server = MCPServer()
        
        # Register tools and set up agent
        tools = register_tools(mcp_server, travel_utils, planner_tool)
        mcp_server.setup_agent(tools)
        
        # Note: MCP server should be started separately using start_mcp_server.py
        # The server will be available at http://localhost:8000
        print("MCP Server initialized. Make sure to start it separately if not already running.")
        
        return mcp_server, travel_utils, planner_tool
    
    except Exception as e:
        st.error(f"Error initializing AI Travel Planner: {str(e)}")
        st.stop()

# Get or create the MCP server and tools
mcp_server, travel_utils, planner_tool = initialize_mcp_server()

# Title and description
st.title("🌍 AI Travel Planner")
st.markdown("""
This intelligent travel planner helps you create personalized travel itineraries and get destination suggestions 
based on your preferences. You can ask follow-up questions to refine your travel plans!
""")

# Add conversation management buttons
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    if st.button("🔄 New Conversation"):
        st.session_state.conversation_session_id = None
        st.session_state.conversation_history = []
        st.rerun()
with col2:
    if st.button("🗑️ Clear History"):
        st.session_state.conversation_history = []
        st.rerun()
with col3:
    if st.session_state.conversation_session_id:
        st.info(f"Session: {st.session_state.conversation_session_id[:8]}...")

# Add export functionality
if st.session_state.conversation_history:
    col4, col5 = st.columns([1, 1])
    with col4:
        if st.button("📄 Export Conversation"):
            # Create export data
            export_data = {
                "session_id": st.session_state.conversation_session_id,
                "export_date": datetime.now().isoformat(),
                "conversation_history": st.session_state.conversation_history,
                # Note: user_preferences will be added later when preferences are defined
            }
            
            # Create downloadable JSON
            import json
            json_str = json.dumps(export_data, indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_str,
                file_name=f"travel_conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    with col5:
        if st.button("📋 Copy Summary"):
            # Create a text summary
            summary_lines = ["# Travel Planning Conversation Summary\n"]
            summary_lines.append(f"**Session ID:** {st.session_state.conversation_session_id}\n")
            summary_lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for msg in st.session_state.conversation_history:
                role = "User" if msg["role"] == "user" else "AI Assistant"
                summary_lines.append(f"**{role}:** {msg['content']}\n")
            
            summary_text = "\n".join(summary_lines)
            st.text_area("Conversation Summary", summary_text, height=200)

# Display conversation history
if st.session_state.conversation_history:
    st.subheader("💬 Conversation History")
    conversation_container = st.container()
    
    with conversation_container:
        for i, message in enumerate(st.session_state.conversation_history):
            if message["role"] == "user":
                st.markdown(f"**You:** {message['content']}")
            else:
                st.markdown(f"**AI:** {message['content']}")
            st.divider()

# Sidebar for mode selection
mode = st.sidebar.radio(
    "Choose Planning Mode",
    ["Get Travel Suggestions", "Create Detailed Itinerary", "Search Flights"]
)

# Add intelligent mode detection
def detect_request_type(user_input: str) -> str:
    """Detect if the user is asking for suggestions, itinerary, or flight search"""
    input_lower = user_input.lower()
    
    # Keywords that indicate comprehensive travel planning (even if flights are mentioned)
    comprehensive_keywords = [
        'curate', 'experience', 'activities', 'places to visit', 'things to do', 
        'romantic experience', 'island escape', 'day by day', 'itinerary',
        'recommend resorts', 'recommend hotels', 'attractions', 'sightseeing',
        'what to do', 'where to go', 'travel guide', 'complete details',
        'day-by-day', 'personalized tips', 'unforgettable', 'honeymoon'
    ]
    
    # Keywords that indicate a pure flight search request (simple, direct)
    pure_flight_keywords = [
        'search flights only', 'find flights only', 'flight prices only',
        'compare flights', 'cheapest flights', 'flight deals only'
    ]
    
    # Keywords that indicate a specific itinerary request
    itinerary_keywords = [
        'create itinerary', 'make itinerary', 'detailed itinerary', 'travel plan',
        'schedule', 'day 1', 'day 2', 'day 3', 'morning', 'afternoon', 'evening'
    ]
    
    # Check for comprehensive travel planning first (highest priority)
    comprehensive_count = sum(1 for keyword in comprehensive_keywords if keyword in input_lower)
    if comprehensive_count >= 2:  # Multiple indicators of comprehensive planning
        return "suggestions"
    
    # Check for pure flight search (only if no comprehensive indicators)
    for keyword in pure_flight_keywords:
        if keyword in input_lower:
            return "flights"
    
    # Check for itinerary keywords
    for keyword in itinerary_keywords:
        if keyword in input_lower:
            return "itinerary"
    
    # If flight keywords are mentioned with travel content, treat as suggestions
    has_flight_words = any(word in input_lower for word in ['flight', 'flights', 'round-trip', 'round trip'])
    has_travel_content = any(word in input_lower for word in ['recommend', 'suggest', 'experience', 'activities', 'places', 'resort', 'hotel'])
    
    if has_flight_words and has_travel_content:
        return "suggestions"  # Comprehensive travel planning that includes flights
    
    # Simple flight-only requests
    if has_flight_words and not has_travel_content:
        return "flights"
    
    # Default to suggestions for travel-related queries
    return "suggestions"

# Common preferences input
with st.sidebar:
    st.subheader("Your Travel Preferences")
    departure_city = st.text_input("Departure City (e.g., 'New York', 'LHR')", help="Your home city for flight searches.")
    budget_range = st.selectbox(
        "Budget Range",
        ["Budget", "Moderate", "Luxury"]
    )
    
    travel_style = st.selectbox(
        "Travel Style",
        list(TravelUtils.get_travel_style_descriptions().keys())
    )
    
    interests = st.multiselect(
        "Interests",
        ["Culture", "Nature", "Food", "Adventure", "Shopping", "History", "Art", "Nightlife"],
        default=["Culture", "Food"]
    )
    
    group_size = st.number_input("Number of Travelers", min_value=1, value=2)
    
    language = st.selectbox("Preferred Language", ["English", "Spanish", "French", "German", "Japanese"])
    
    dietary_restrictions = st.multiselect(
        "Dietary Restrictions",
        ["None", "Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free"],
        default=["None"]
    )
    
    accommodation_type = st.selectbox(
        "Preferred Accommodation",
        ["Hotel", "Hostel", "Resort", "Apartment", "Boutique Hotel"]
    )

# Create preferences object
preferences = TravelPreferences(
    departure_city=departure_city,
    budget_range=budget_range,
    travel_style=travel_style,
    interests=interests,
    group_size=group_size,
    language_preference=language.lower(),
    dietary_restrictions=[r for r in dietary_restrictions if r != "None"],
    accommodation_type=accommodation_type
)

def extract_travel_entities(text: str) -> Dict[str, Any]:
    """Extract travel-related entities from text"""
    # Simple keyword-based extraction
    travel_keywords = {
        'duration': [r'(\d+)\s*(day|days|week|weeks|month|months)', r'for\s+(\d+)\s*(day|days|week|weeks|month|months)'],
        'destinations': ['city', 'country', 'beach', 'mountain', 'hotel', 'resort'],
        'activities': ['hiking', 'sightseeing', 'museum', 'restaurant', 'shopping', 'adventure', 'cultural', 'food'],
        'budget_terms': ['budget', 'cheap', 'expensive', 'luxury', 'affordable', 'cost']
    }
    
    entities = {}
    text_lower = text.lower()
    
    # Extract duration using regex
    import re
    for pattern in travel_keywords['duration']:
        match = re.search(pattern, text_lower)
        if match:
            number = int(match.group(1))
            unit = match.group(2)
            if 'week' in unit:
                number *= 7
            elif 'month' in unit:
                number *= 30
            entities['duration'] = f"{number} days"
            break
    
    # Extract other entities
    for category, keywords in travel_keywords.items():
        if category != 'duration':  # Skip duration as it's handled above
            found_keywords = [kw for kw in keywords if kw in text_lower]
            if found_keywords:
                entities[category] = found_keywords
    
    return entities

def extract_travel_dates(user_input: str) -> Tuple[datetime, datetime]:
    """
    Extracts departure and return dates from user input.
    Returns (departure_date, return_date).
    """
    
    # Default dates (30 days from now for departure, 7 days later for return)
    default_departure = datetime.now() + timedelta(days=30)
    default_return = default_departure + timedelta(days=7)
    
    try:
        # Look for specific date patterns
        date_patterns = [
            r'departing on\s+([^,\n]+?)(?:\s+and|\s+returning)',  # "departing on July 10th and"
            r'departure.*?(\w+ \d{1,2}(?:st|nd|rd|th)?)',          # "departure July 10th"
            r'depart.*?(\w+ \d{1,2}(?:st|nd|rd|th)?)',             # "depart July 10th"
            r'leaving.*?(\w+ \d{1,2}(?:st|nd|rd|th)?)',            # "leaving July 10th"
        ]
        
        return_patterns = [
            r'returning on\s+([^,\n]+?)(?:\s+for|\s+\.|$)',        # "returning on July 18th"
            r'return.*?(\w+ \d{1,2}(?:st|nd|rd|th)?)',             # "return July 18th"
            r'coming back.*?(\w+ \d{1,2}(?:st|nd|rd|th)?)',        # "coming back July 18th"
        ]
        
        departure_date = None
        return_date = None
        
        # Extract departure date
        for pattern in date_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                departure_date = parse_date_string(date_str)
                logger.info(f"Extracted departure date: {departure_date}")
                break
        
        # Extract return date
        for pattern in return_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                return_date = parse_date_string(date_str)
                logger.info(f"Extracted return date: {return_date}")
                break
        
        # Use defaults if not found
        if not departure_date:
            departure_date = default_departure
            logger.info(f"Using default departure date: {departure_date}")
            
        if not return_date:
            return_date = default_return
            logger.info(f"Using default return date: {return_date}")
        
        return departure_date, return_date
        
    except Exception as e:
        logger.warning(f"Error extracting dates: {e}, using defaults")
        return default_departure, default_return

def parse_date_string(date_str: str) -> datetime:
    """Parse a date string like 'July 10th' into a datetime object"""
    import re
    from datetime import datetime
    
    # Remove ordinal suffixes (st, nd, rd, th)
    clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
    
    # Common date formats to try
    formats = [
        '%B %d',      # July 10
        '%b %d',      # Jul 10
        '%m/%d',      # 7/10
        '%m-%d',      # 7-10
        '%d %B',      # 10 July
        '%d %b',      # 10 Jul
    ]
    
    current_year = datetime.now().year
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(clean_date, fmt)
            # Add current year
            return parsed.replace(year=current_year)
        except ValueError:
            continue
    
    # If all parsing fails, return a default date
    logger.warning(f"Could not parse date: {date_str}")
    return datetime.now() + timedelta(days=30)

if mode == "Get Travel Suggestions":
    st.header("🔍 Get Travel Suggestions")
    
    # Input for travel preferences
    travel_input = st.text_area(
        "Describe your ideal trip",
        "I want to travel for about a week, interested in cultural experiences and good food."
    )
    
    if st.button("Get Suggestions"):
        # Create a placeholder for progress updates
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        details_placeholder = st.empty()
        
        with st.spinner("Generating travel suggestions..."):
            logger.info("🎯 Starting travel suggestion process")
            
            # Show initial processing status
            with progress_placeholder.container():
                st.info("🔄 **Processing your request...**")
                progress_bar = st.progress(0)
                progress_bar.progress(10)
            
            # Create context with preferences
            context = {
                "preferences": preferences.model_dump(exclude_none=True),
                "mode": "suggestions"
            }
            logger.debug(f"📋 Context created: {context}")
            
            # Update progress
            progress_bar.progress(20)
            with status_placeholder.container():
                st.success("✅ **Context prepared** - User preferences loaded")
                
            # Show detailed extraction information
            with details_placeholder.container():
                with st.expander("🔍 **Processing Details**", expanded=True):
                    st.write("**📋 User Input Analysis:**")
                    st.code(f"Input: {travel_input[:100]}{'...' if len(travel_input) > 100 else ''}")
                    
                    # Show date extraction
                    departure_date, return_date = extract_travel_dates(travel_input)
                    st.write("**📅 Date Extraction:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Departure Date", departure_date.strftime('%Y-%m-%d'))
                    with col2:
                        st.metric("Return Date", return_date.strftime('%Y-%m-%d'))
                    
                    # Show origin/destination extraction
                    origin, destination = extract_origin_destination(travel_input, preferences.departure_city)
                    st.write("**🌍 Location Analysis:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Origin", origin if origin else "Not specified")
                    with col2:
                        if destination:
                            st.metric("Destination", destination)
                        else:
                            st.write("*Destination will be determined from suggestions*")
                    
                    # Show request type detection
                    request_type = detect_request_type(travel_input)
                    st.write("**🧠 Request Classification:**")
                    st.info(f"Detected as: **{request_type.upper()}** request")
            
            progress_bar.progress(40)
            
            # Flight search helper function
            async def handle_flight_search_request(user_input: str):
                """Handle flight search requests directly using FlightSearchTool"""
                try:
                    logger.info("🛫 Processing flight search request")
                    
                    # Import and initialize FlightSearchTool
                    from tools.travel_tools import FlightSearchTool
                    flight_tool = FlightSearchTool()
                    
                    # Extract origin and destination
                    origin, destination = extract_origin_destination(user_input, preferences.departure_city)

                    if not origin or not destination:
                        st.warning("Could not determine the origin and destination for the flight search. Please specify them clearly (e.g., 'flights from New York to Paris') or set your departure city in the sidebar.")
                        return {
                            "type": "flights",
                            "content": "Could not determine the origin and destination for the flight search. Please specify them clearly (e.g., 'flights from New York to Paris') or set your departure city in the sidebar."
                        }
                    
                    departure_date = datetime.now() + timedelta(days=30)
                    
                    logger.info(f"🛫 Searching flights: {origin} → {destination}")
                    
                    # Search for flights
                    flights = await flight_tool.execute(
                        origin=origin,
                        destination=destination,
                        date=departure_date
                    )
                    
                    # Format the response
                    if flights and len(flights) > 0:
                        flight_response = f"## ✈️ Flight Options: {origin} → {destination}\n\n"
                        
                        for i, flight in enumerate(flights[:5], 1):  # Show top 5 flights
                            flight_response += f"**Flight {i}:**\n"
                            flight_response += f"- Airline: {flight.get('airline', 'N/A')}\n"
                            flight_response += f"- Price: {flight.get('price', 'N/A')}\n"
                            flight_response += f"- Duration: {flight.get('duration', 'N/A')}\n"
                            flight_response += f"- Stops: {flight.get('stops', 'N/A')}\n"
                            flight_response += f"- Departure: {flight.get('departure_time', 'N/A')}\n"
                            flight_response += f"- Arrival: {flight.get('arrival_time', 'N/A')}\n\n"
                        
                        return {"type": "flights", "content": flight_response}
                    else:
                        return {
                            "type": "flights", 
                            "content": f"Sorry, no flights found for {origin} to {destination}. Please try the dedicated Flight Search mode for better results."
                        }
                        
                except Exception as e:
                    logger.error(f"❌ Error in flight search: {str(e)}")
                    return {
                        "type": "flights",
                        "content": f"Unable to search flights at the moment. Please try using the 'Search Flights' mode from the sidebar for better flight search functionality."
                    }
            
            # Enhanced flight search integration function
            async def enhance_suggestions_with_flights(suggestions: List[Dict], user_input: str) -> List[Dict]:
                """Enhance travel suggestions with mandatory flight search results"""
                try:
                    logger.info("✈️ Enhancing suggestions with flight search results")
                    
                    # Update progress
                    progress_bar.progress(60)
                    with status_placeholder.container():
                        st.info("✈️ **Searching flights** for each destination...")
                    
                    # Import and initialize FlightSearchTool
                    from tools.travel_tools import FlightSearchTool
                    flight_tool = FlightSearchTool()
                    
                    # Extract travel dates from user input
                    departure_date, return_date = extract_travel_dates(user_input)
                    
                    # Try to extract origin from user preferences or input
                    extracted_origin, _ = extract_origin_destination(user_input, preferences.departure_city)
                    origin = extracted_origin if extracted_origin else "New York" # Fallback to default
                    logger.info(f"Using '{origin}' as the departure city for all suggestions.")
                    logger.info(f"Using dates: {departure_date.strftime('%Y-%m-%d')} to {return_date.strftime('%Y-%m-%d')}")

                    # Show flight search details
                    with details_placeholder.container():
                        with st.expander("✈️ **Flight Search Details**", expanded=True):
                            st.write("**🛫 Flight Search Configuration:**")
                            
                            flight_config_col1, flight_config_col2, flight_config_col3 = st.columns(3)
                            with flight_config_col1:
                                st.metric("Origin City", origin)
                            with flight_config_col2:
                                st.metric("Departure", departure_date.strftime('%Y-%m-%d'))
                            with flight_config_col3:
                                st.metric("Return", return_date.strftime('%Y-%m-%d'))
                            
                            flight_progress_placeholder = st.empty()
                    
                    # Process each suggestion and add flight information
                    enhanced_suggestions = []
                    total_suggestions = len(suggestions)
                    
                    for idx, suggestion in enumerate(suggestions):
                        if isinstance(suggestion, dict):
                            destination_name = suggestion.get('destination', '')
                            
                            if not destination_name:
                                enhanced_suggestions.append(suggestion)
                                continue

                            # Extract city name from destination
                            destination = destination_name.split(',')[0].strip()
                            
                            # Update flight search progress
                            with flight_progress_placeholder.container():
                                st.write(f"**🔍 Searching flights {idx+1}/{total_suggestions}:** {origin} → {destination}")
                                flight_search_progress = st.progress((idx + 1) / total_suggestions)
                            
                            # Search for flights to this destination
                            try:
                                logger.info(f"🛫 Searching flights: {origin} → {destination}")
                                flights = await flight_tool.execute(
                                    origin=origin,
                                    destination=destination,
                                    date=departure_date,
                                    return_date=return_date
                                )
                                
                                # Add flight information to suggestion
                                suggestion['flight_options'] = flights[:3]  # Top 3 flights
                                suggestion['flight_summary'] = {
                                    'origin': origin,
                                    'destination': destination,
                                    'departure_date': departure_date.strftime('%Y-%m-%d'),
                                    'return_date': return_date.strftime('%Y-%m-%d'),
                                    'total_flights_found': len(flights)
                                }
                                
                                # Show flight search results in real-time
                                with flight_progress_placeholder.container():
                                    if len(flights) > 0:
                                        st.success(f"✅ Found **{len(flights)} flights** for {destination}")
                                        # Show a preview of the best flight
                                        best_flight = flights[0]
                                        st.write(f"💰 Best price: **{best_flight.get('price', 'N/A')}** ({best_flight.get('airline', 'N/A')})")
                                    else:
                                        st.warning(f"⚠️ No flights found for {destination}")
                                
                                # Update estimated budget to include flight costs
                                if flights and len(flights) > 0:
                                    try:
                                        # Extract price from first flight
                                        first_flight_price = flights[0].get('price', '$500')
                                        price_num = int(''.join(filter(str.isdigit, first_flight_price)))
                                        current_budget = suggestion.get('estimated_budget', '$100 per day')
                                        
                                        # Add flight cost to daily budget estimate
                                        suggestion['total_estimated_cost'] = f"${price_num} (flights) + {current_budget}"
                                    except:
                                        suggestion['total_estimated_cost'] = suggestion.get('estimated_budget', 'Budget varies')
                                
                                logger.info(f"✅ Added {len(flights)} flight options to {destination}")
                                
                            except Exception as flight_error:
                                logger.warning(f"⚠️ Could not get flights for {destination}: {flight_error}")
                                with flight_progress_placeholder.container():
                                    st.error(f"❌ Flight search failed for {destination}: {str(flight_error)}")
                                
                                # Add placeholder flight info
                                suggestion['flight_options'] = []
                                suggestion['flight_summary'] = {
                                    'origin': origin,
                                    'destination': destination,
                                    'note': 'Flight search temporarily unavailable'
                                }
                        
                        enhanced_suggestions.append(suggestion)
                    
                    # Update final progress
                    progress_bar.progress(80)
                    with status_placeholder.container():
                        st.success(f"✅ **Flight search completed** - Enhanced {len(enhanced_suggestions)} suggestions")
                    
                    logger.info(f"✅ Enhanced {len(enhanced_suggestions)} suggestions with flight data")
                    return enhanced_suggestions
                    
                except Exception as e:
                    logger.error(f"❌ Error enhancing suggestions with flights: {e}")
                    with status_placeholder.container():
                        st.error(f"❌ **Error in flight enhancement:** {str(e)}")
                    return suggestions  # Return original suggestions if enhancement fails
            
            # Define async function to make the request using the agent
            async def get_suggestions():
                """Get travel suggestions from the agent."""
                try:
                    logger.info("🔍 Starting suggestion generation using MCP agent")
                    
                    # Detect if this is actually a flight search, itinerary, or suggestion request
                    request_type = detect_request_type(travel_input)
                    logger.info(f"🧠 Detected request type: {request_type}")
                    
                    # Handle flight search requests directly
                    if request_type == "flights":
                        logger.info("🛫 Routing to flight search tool")
                        return await handle_flight_search_request(travel_input)
                    
                    # Use the MCP agent executor directly instead of HTTP calls
                    if mcp_server.agent_executor:
                        logger.info("🤖 Using local MCP agent executor")
                          # Create agent input with proper structure
                        agent_input = {
                            "input": travel_input,
                            "context": context,
                            "chat_history": []  # Add empty chat history for now
                        }
                          # Execute using the agent
                        result = await mcp_server.agent_executor.ainvoke(agent_input)
                        logger.info(f"✅ Agent result received: {result}")
                        
                        suggestions = result.get("output", "")
                        logger.debug(f"📝 Raw suggestions content: {suggestions[:200]}...")
                        
                        # If the agent output is already formatted suggestions, use it directly
                        # Otherwise, try to parse it as structured suggestions
                        if isinstance(suggestions, str):
                            # Check if it looks like suggestions format
                            if "* " in suggestions or "Day " in suggestions:
                                # Direct formatted response from agent
                                return {"type": request_type, "content": suggestions}
                            else:
                                # Try to convert to suggestion format for display
                                return {"type": "suggestions", "content": suggestions}
                        
                        # Enhance suggestions with mandatory flight search results
                        if isinstance(suggestions, list) and request_type == "suggestions":
                            enhanced_suggestions = await enhance_suggestions_with_flights(suggestions, travel_input)
                            return {"type": "suggestions", "content": enhanced_suggestions}
                        
                        # Determine response type and return properly structured result
                        if request_type == "itinerary":
                            return {"type": "itinerary", "content": suggestions}
                        else:
                            return {"type": "suggestions", "content": suggestions}
                    else:
                        # Fallback to direct tool usage if agent not available
                        logger.warning("⚠️ MCP agent not available, using direct tool fallback")
                        return await get_suggestions_fallback()
                        
                except Exception as e:
                    error_msg = f"Error in get_suggestions: {str(e)}"
                    logger.error(f"❌ {error_msg}\n{traceback.format_exc()}")
                    # Try fallback approach
                    logger.info("� Attempting fallback approach")
                    try:
                        return await get_suggestions_fallback()
                    except Exception as fallback_error:
                        logger.error(f"❌ Fallback also failed: {str(fallback_error)}")
                        # Return demo data when everything fails
                        logger.info("🎪 Using demo data for testing")
                        return {"type": "suggestions", "content": _get_demo_suggestions()}

            async def get_suggestions_fallback():
                """Fallback method using direct tool calls"""
                logger.info("🛠️ Using direct tool calls for suggestions")
                
                try:
                    # Use the planner tool directly
                    suggestions = await planner_tool.execute(
                        location=travel_input, 
                        duration=7, 
                        preferences={"prompt": travel_input, "context": context}
                    )
                    
                    # Enhance with flight data if we got valid suggestions
                    if isinstance(suggestions, list):
                        enhanced_suggestions = await enhance_suggestions_with_flights(suggestions, travel_input)
                        return {"type": "suggestions", "content": enhanced_suggestions}
                    else:
                        return {"type": "suggestions", "content": suggestions}
                except:
                    # Return demo suggestions if everything fails, also enhanced with flights
                    demo_suggestions = _get_demo_suggestions()
                    try:
                        enhanced_demo = await enhance_suggestions_with_flights(demo_suggestions, travel_input)
                        return {"type": "suggestions", "content": enhanced_demo}
                    except:
                        return {"type": "suggestions", "content": demo_suggestions}

            def _get_demo_suggestions():
                """Return demo suggestions when API is unavailable"""
                return [
                    {
                        "destination": "Malé, Maldives",
                        "description": "A tropical paradise of pristine beaches, crystal-clear lagoons, and luxurious overwater villas. Perfect for a romantic island escape with world-class diving, spa treatments, and sunset dinners.",
                        "best_time_to_visit": "November to April (dry season)",
                        "estimated_budget": "$400-800 per day",
                        "duration": "7-9 days",
                        "activities": [
                            "Stay in overwater villas with glass floors",
                            "Sunset dinner on private beach sandbank",
                            "Couples spa treatments with ocean views",
                            "Snorkeling in pristine coral reefs",
                            "Private boat excursions to uninhabited islands",
                            "Swimming with whale sharks and manta rays",
                            "Romantic beach picnics at sunset",
                            "Dolphin watching cruise",
                            "Underwater restaurant dining experience",
                            "Traditional Maldivian fishing trip"
                        ],
                        "accommodation_suggestions": [
                            "Conrad Maldives Rangali Island (luxury overwater villas)",
                            "Soneva Jani (eco-luxury with slides from villa to lagoon)",
                            "Four Seasons Resort Maldives at Landaa Giraavaru",
                            "COMO Maalifushi (boutique luxury)",
                            "Anantara Kihavah Maldives Villas"
                        ],
                        "transportation": [
                            "Seaplane transfers to resort (scenic aerial views)",
                            "Speedboat transfers for nearby resorts",
                            "Private yacht charter between islands",
                            "Resort bicycles for island exploration"
                        ],
                        "local_tips": [
                            "Book overwater villa in advance for best views",
                            "Pack reef-safe sunscreen (coral protection)",
                            "Bring underwater camera for snorkeling",
                            "Respect local customs on inhabited islands",
                            "Try traditional Maldivian fish curry",
                            "Book spa treatments early (popular at sunset)",
                            "Bring formal attire for resort dinners"
                        ],
                        "weather_info": "Tropical climate, dry season Nov-Apr ideal for travel",
                        "safety_info": "Very safe destination, follow water safety guidelines",
                        "visa_info": "Visa on arrival for Indian citizens (30 days free)",
                        "daily_itinerary": {
                            "Day 1": "Arrival, seaplane transfer, check into overwater villa, sunset welcome dinner",
                            "Day 2": "Snorkeling excursion, couples spa treatment, private beach dinner",
                            "Day 3": "Island hopping tour, dolphin watching, beach picnic",
                            "Day 4": "Diving/snorkeling at Manta Point, underwater restaurant lunch",
                            "Day 5": "Private boat to sandbank, romantic sunset dinner setup",
                            "Day 6": "Traditional fishing trip, local island visit, cultural experience",
                            "Day 7": "Final spa session, leisure time, farewell dinner",
                            "Day 8": "Departure preparation, last-minute shopping",
                            "Day 9": "Check out, seaplane to airport, departure"
                        }
                    },
                    {
                        "destination": "Bali, Indonesia",  
                        "description": "An enchanting island of temples, rice terraces, and pristine beaches. Perfect blend of culture, adventure, and relaxation with luxury resorts and romantic settings.",
                        "best_time_to_visit": "April to October (dry season)",
                        "estimated_budget": "$100-300 per day",
                        "duration": "7-10 days",
                        "activities": [
                            "Visit ancient temples like Tanah Lot and Uluwatu",
                            "Sunrise trek to Mount Batur volcano",
                            "Couples massage at luxury spa resorts",
                            "Rice terrace tours in Jatiluwih",
                            "Beach clubs and sunset cocktails in Seminyak",
                            "Traditional cooking classes in Ubud",
                            "Private villa with infinity pool",
                            "White water rafting adventure",
                            "Art galleries and markets in Ubud",
                            "Beach hopping in Nusa Penida"
                        ],
                        "accommodation_suggestions": [
                            "Four Seasons Resort Bali at Sayan (luxury jungle setting)",
                            "The Mulia Resort (beachfront luxury)",
                            "Hanging Gardens of Bali (infinity pool villa)",
                            "Alila Villas Uluwatu (cliffside luxury)",
                            "COMO Shambhala Estate (wellness retreat)"
                        ],
                        "transportation": [
                            "Private driver for sightseeing",
                            "Scooter rental for local exploration",
                            "Fast boat to Gili Islands",
                            "Private helicopter tours"
                        ],
                        "local_tips": [
                            "Respect temple dress codes (sarong required)",
                            "Bargain at local markets",
                            "Try authentic nasi goreng and satay",
                            "Book volcano trek in advance",
                            "Avoid drinking tap water",
                            "Learn basic Indonesian phrases",
                            "Tip service staff appropriately"
                        ],
                        "weather_info": "Tropical climate, dry season April-October ideal",
                        "safety_info": "Generally safe, watch for traffic and petty theft"
                    }
                ]

            async def get_weather(destination: str) -> Dict:
                """Get weather information for the destination"""
                try:
                    logger.info(f"🌤️ Getting weather for {destination}")
                    from tools.Weathertool import WeatherTool
                    weather_tool = WeatherTool()
                    weather_info = await weather_tool.execute(destination, datetime.now())
                    logger.debug(f"🌤️ Weather info: {weather_info}")
                    return weather_info
                except Exception as e:
                    logger.warning(f"⚠️ Error getting weather: {str(e)}")
                    return {"status": "unavailable", "message": "Weather data unavailable"}

            async def get_local_tips(destination: str) -> List[str]:
                """Get local tips for the destination"""
                try:
                    print(f"\n=== Getting local tips for {destination} ===")
                    # Use itinerary planner for local tips since LocationInfoTool was removed
                    from tools.travel_tools import ItineraryPlannerTool
                    planner = ItineraryPlannerTool()
                    query = f"Local tips and recommendations for visiting {destination}"
                    tips_result = await planner.execute(query, 1, {"destination": destination})
                    if tips_result:
                        # Extract tips from the result
                        tips = [tip.strip() for tip in tips_result.split('\n') if tip.strip() and not tip.startswith('Day')]
                        return tips[:5] if tips else ["Explore local culture and cuisine"]
                    return ["Explore local culture and cuisine"]
                except Exception as e:
                    print(f"Error getting local tips: {str(e)}")
                    return ["Local tips unavailable"]

            async def get_hotels(destination: str) -> List[Dict]:
                """Get hotel suggestions for the destination"""
                try:
                    print(f"\n=== Getting hotels for {destination} ===")
                    from tools.HotelSearchTool import HotelSearchTool
                    hotel_tool = HotelSearchTool()
                    check_in = datetime.now() + timedelta(days=30)  # 30 days from now
                    check_out = check_in + timedelta(days=7)  # 7 days stay
                    
                    hotels = hotel_tool.hotel_search(
                        location=destination,
                        check_in=check_in.strftime('%Y-%m-%d'),
                        check_out=check_out.strftime('%Y-%m-%d'),
                        adults=2
                    )
                    
                    if isinstance(hotels, dict) and hotels.get('data'):
                        hotel_list = hotels.get('data', [])[:3]  # Top 3 hotels
                        formatted_hotels = []
                        for hotel in hotel_list:
                            formatted_hotels.append({
                                "name": hotel.get('hotel', {}).get('name', 'Unknown Hotel'),
                                "price": hotel.get('offers', [{}])[0].get('price', {}).get('total', 'N/A'),
                                "rating": hotel.get('hotel', {}).get('rating', 'N/A'),
                                "address": hotel.get('hotel', {}).get('address', {}).get('lines', ['N/A'])[0],
                                "amenities": hotel.get('hotel', {}).get('amenities', ['N/A'])[:3]
                            })
                        return formatted_hotels
                    else:
                        return [{"name": "Hotel search unavailable", "price": "N/A", "rating": "N/A", "address": "N/A", "amenities": ["Data unavailable"]}]
                except Exception as e:
                    print(f"Error getting hotels: {str(e)}")
                    return [{"name": "Hotel data unavailable", "price": "N/A", "rating": "N/A", "address": "N/A", "amenities": ["Data unavailable"]}]

            async def get_flights(destination: str) -> List[Dict]:
                """Get flight suggestions for the destination"""
                try:
                    print(f"\n=== Getting flights for {destination} ===")
                    from tools.travel_tools import FlightSearchTool
                    flight_tool = FlightSearchTool()
                    origin = "NYC"  # Default origin - could be made configurable
                    departure_date = datetime.now() + timedelta(days=30)
                    
                    flights = await flight_tool.execute(
                        origin=origin,
                        destination=destination,
                        date=departure_date
                    )
                    
                    if flights and isinstance(flights, list):
                        # FlightSearchTool already returns formatted data
                        return flights[:3]  # Top 3 flights
                    else:
                        return [{"airline": "Flight search unavailable", "flight_number": "N/A", "departure": "N/A", "arrival": "N/A", "departure_time": "N/A", "arrival_time": "N/A", "price": "N/A", "duration": "N/A", "stops": "N/A"}]
                except Exception as e:
                    print(f"Error getting flights: {str(e)}")
                    return [{"airline": "Flight data unavailable", "flight_number": "N/A", "departure": "N/A", "arrival": "N/A", "departure_time": "N/A", "arrival_time": "N/A", "price": "N/A", "duration": "N/A", "stops": "N/A"}]

            async def get_best_time(destination: str) -> str:
                """Get best time to visit using ItineraryPlanner"""
                try:
                    print(f"\n=== Getting best time to visit for {destination} ===")
                    planner = ItineraryPlannerTool()
                    suggestions = await planner.execute(destination, 7, {"focus": "best time"})
                    best_time = suggestions[0].get("best_time_to_visit", "Contact travel agent for details") if suggestions and len(suggestions) > 0 else "Contact travel agent for details"
                    print(f"Best time to visit: {best_time}")
                    return best_time
                except Exception as e:
                    print(f"Error getting best time: {str(e)}")
                    return "Best time data unavailable"

            async def get_estimated_budget(destination: str) -> str:
                """Get estimated budget using ItineraryPlanner"""
                try:
                    print(f"\n=== Getting estimated budget for {destination} ===")
                    planner = ItineraryPlannerTool()
                    suggestions = await planner.execute(destination, 7, {"focus": "budget"})
                    budget = suggestions[0].get("estimated_budget", "Varies by season") if suggestions and len(suggestions) > 0 else "Varies by season"
                    print(f"Estimated budget: {budget}")
                    return budget
                except Exception as e:
                    print(f"Error getting estimated budget: {str(e)}")
                    return "Budget data unavailable"            # Run the async function
            progress_bar.progress(50)
            with status_placeholder.container():
                st.info("🤖 **Generating suggestions** using AI agent...")
            
            result = asyncio.run(get_suggestions())
            
            # Complete progress
            progress_bar.progress(100)
            with status_placeholder.container():
                st.success("✅ **Processing completed!** Displaying your personalized travel suggestions...")
            
            # Clear progress indicators after a brief moment
            import time
            time.sleep(1)
            progress_placeholder.empty()
            status_placeholder.empty()
            details_placeholder.empty()
            
            print(f"\n=== Got result: {result} ===")
            
            # Check if result is valid
            if result is None:
                st.error("Failed to get response from the travel agent. Please try again.")
                st.stop()
            
            if not isinstance(result, dict) or "type" not in result:
                st.error("Invalid response format. Please try again.")
                st.stop()
            
            # Show processing summary before results
            with st.expander("📊 **Processing Summary**", expanded=False):
                summary_col1, summary_col2, summary_col3 = st.columns(3)
                with summary_col1:
                    st.metric("Request Type", result["type"].title())
                with summary_col2:
                    if isinstance(result["content"], list):
                        st.metric("Suggestions Generated", len(result["content"]))
                    else:
                        st.metric("Response Type", "Text")
                with summary_col3:
                    if result["type"] == "suggestions" and isinstance(result["content"], list):
                        flight_count = sum(1 for s in result["content"] if s.get('flight_options'))
                        st.metric("Destinations with Flights", flight_count)
            
            # Display results based on type
            if result["type"] == "flights":
                # Display flight search results
                st.subheader("✈️ Flight Search Results")
                st.markdown(result["content"])
                
                # Add helpful information for flight search
                st.info("💡 **Tip**: For more detailed flight search with specific dates and preferences, use the 'Search Flights' mode from the sidebar.")
                
            elif result["type"] == "itinerary":
                # Display itinerary response
                st.subheader("📝 Your Travel Itinerary")
                st.markdown(result["content"])
                
                # Add some helpful information
                st.info("💡 **Tip**: This itinerary was generated based on your preferences. You can modify the details or ask for specific changes.")
                
            elif result["type"] == "suggestions":
                # Parse and display suggestions
                suggestions = result["content"]
                
                # Handle both string and list formats
                if isinstance(suggestions, list):
                    # Direct list of suggestions from fallback tool
                    suggestions_list = suggestions
                    
                    # Display suggestions directly
                    st.subheader("🌟 Personalized Travel Suggestions")
                    st.write(f"*Based on your preferences: {travel_style} style, {', '.join(interests)} interests, ${budget_range} budget*")
                    
                    for i, suggestion in enumerate(suggestions_list, 1):
                        try:
                            # Create a distinctive container for each suggestion
                            with st.container():
                                # Header with destination and key info
                                st.markdown(f"""
                                <div style="background: linear-gradient(90deg, #1f4e79, #2563eb); padding: 1rem; border-radius: 10px; margin: 1rem 0;">
                                    <h2 style="color: white; margin: 0; font-size: 1.8rem;">
                                        🌍 Suggestion {i}: {suggestion['destination']}
                                    </h2>
                                    <p style="color: #e2e8f0; margin: 0.5rem 0 0 0; font-size: 1.1rem;">
                                        {suggestion['description'][:150]}{'...' if len(suggestion['description']) > 150 else ''}
                                    </p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Key information in highlighted boxes
                                info_col1, info_col2, info_col3, info_col4 = st.columns(4)
                                with info_col1:
                                    best_time = suggestion.get('best_time_to_visit', 'Year-round')
                                    st.metric("🌤️ Best Time", best_time, help="Optimal travel season")
                                with info_col2:
                                    budget = suggestion.get('estimated_budget', 'Varies')
                                    st.metric("💰 Daily Budget", budget, help="Estimated cost per day")
                                with info_col3:
                                    duration = suggestion.get('duration', '7')
                                    st.metric("📅 Duration", f"{duration} days", help="Recommended stay length")
                                with info_col4:
                                    if suggestion.get('flight_summary', {}).get('total_flights_found', 0) > 0:
                                        flight_count = suggestion['flight_summary']['total_flights_found']
                                        st.metric("✈️ Flights", f"{flight_count} found", help="Available flight options")
                                    else:
                                        st.metric("✈️ Flights", "Searching...", help="Flight search in progress")
                                
                                # Full description
                                st.write("**📝 Full Description:**")
                                st.write(suggestion['description'])
                                
                                # Activities in a more visual format
                                if suggestion.get('activities'):
                                    st.write("**🎯 Top Activities & Experiences:**")
                                    
                                    # Split activities into columns for better display
                                    activities = suggestion['activities']
                                    cols = st.columns(2)
                                    for idx, activity in enumerate(activities):
                                        with cols[idx % 2]:
                                            st.write(f"🔸 {activity}")
                                
                                # Expandable sections with better formatting
                                tab1, tab2, tab3, tab4 = st.tabs(["🏨 Accommodation", "🚗 Transportation", "💡 Local Tips", "📋 Detailed Info"])
                                
                                with tab1:
                                    if suggestion.get('accommodation_suggestions'):
                                        st.write("**🏨 Recommended Accommodations:**")
                                        for accommodation in suggestion['accommodation_suggestions']:
                                            st.write(f"• **{accommodation.split('(')[0].strip()}**")
                                            if '(' in accommodation:
                                                st.write(f"  *{accommodation.split('(')[1].replace(')', '')}*")
                                    else:
                                        st.info("Accommodation recommendations will be provided based on your specific dates and preferences.")
                                
                                with tab2:
                                    if suggestion.get('transportation'):
                                        st.write("**🚗 Transportation Options:**")
                                        for transport in suggestion['transportation']:
                                            st.write(f"🔹 {transport}")
                                    else:
                                        st.info("Transportation options will be customized for your itinerary.")
                                
                                with tab3:
                                    if suggestion.get('local_tips'):
                                        st.write("**💡 Insider Tips & Local Advice:**")
                                        for tip in suggestion['local_tips']:
                                            st.write(f"💡 {tip}")
                                    else:
                                        st.info("Local tips and cultural insights will be provided for your specific interests.")
                                
                                with tab4:
                                    detail_col1, detail_col2 = st.columns(2)
                                    
                                    with detail_col1:
                                        if suggestion.get('weather_info'):
                                            st.write("**🌤️ Weather Information:**")
                                            st.info(suggestion['weather_info'])
                                        
                                        if suggestion.get('visa_info'):
                                            st.write("**🛂 Visa Information:**")
                                            st.info(suggestion['visa_info'])
                                    
                                    with detail_col2:
                                        if suggestion.get('safety_info'):
                                            st.write("**🛡️ Safety Information:**")
                                            st.info(suggestion['safety_info'])
                                
                                # Day-by-day itinerary in an enhanced format
                                if suggestion.get('daily_itinerary'):
                                    st.write("**📅 Suggested Day-by-Day Itinerary:**")
                                    with st.expander("View Full Itinerary", expanded=True):
                                        for day, activities in suggestion['daily_itinerary'].items():
                                            st.markdown(f"""
                                            <div style="background: #f8fafc; padding: 0.8rem; border-left: 4px solid #3b82f6; margin: 0.5rem 0; border-radius: 5px;">
                                                <strong style="color: #1e40af;">{day}</strong><br>
                                                <span style="color: #475569;">{activities}</span>
                                            </div>
                                            """, unsafe_allow_html=True)
                            
                                # Enhanced Flight Information Display
                                if suggestion.get('flight_options') or suggestion.get('flight_summary'):
                                    st.markdown("---")
                                    st.markdown("""
                                    <div style="background: linear-gradient(90deg, #059669, #10b981); padding: 1rem; border-radius: 10px; margin: 1rem 0;">
                                        <h3 style="color: white; margin: 0; font-size: 1.4rem;">
                                            ✈️ Flight Information & Booking Options
                                        </h3>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    # Flight summary with enhanced display
                                    if suggestion.get('flight_summary'):
                                        flight_summary = suggestion['flight_summary']
                                        
                                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                                        with summary_col1:
                                            st.metric(
                                                "🛫 From", 
                                                flight_summary.get('origin', 'N/A'),
                                                help="Departure city"
                                            )
                                        with summary_col2:
                                            st.metric(
                                                "🛬 To", 
                                                flight_summary.get('destination', 'N/A'),
                                                help="Destination city"
                                            )
                                        with summary_col3:
                                            departure_date = flight_summary.get('departure_date', 'N/A')
                                            return_date = flight_summary.get('return_date', 'N/A')
                                            if departure_date != 'N/A':
                                                st.metric("📅 Departure", departure_date)
                                                if return_date != 'N/A':
                                                    st.caption(f"Return: {return_date}")
                                        with summary_col4:
                                            total_flights = flight_summary.get('total_flights_found', 0)
                                            if total_flights > 0:
                                                st.metric(
                                                    "✈️ Options", 
                                                    f"{total_flights} flights",
                                                    delta="Available now",
                                                    delta_color="normal"
                                                )
                                            else:
                                                st.metric("🔍 Status", "Searching...", delta="In progress")
                                    
                                    # Enhanced flight options display
                                    if suggestion.get('flight_options') and len(suggestion['flight_options']) > 0:
                                        st.write("**🛫 Available Flight Options:**")
                                        
                                        # Create tabs for different flights
                                        flight_tabs = st.tabs([f"Flight {i+1}" for i in range(min(3, len(suggestion['flight_options'])))])
                                        
                                        for tab_idx, (tab, flight) in enumerate(zip(flight_tabs, suggestion['flight_options'][:3])):
                                            with tab:
                                                # Flight header with airline and price
                                                flight_header_col1, flight_header_col2 = st.columns([2, 1])
                                                with flight_header_col1:
                                                    airline = flight.get('airline', 'N/A')
                                                    flight_num = flight.get('flight_number', 'N/A')
                                                    st.markdown(f"**🛩️ {airline}** - Flight {flight_num}")
                                                with flight_header_col2:
                                                    price = flight.get('price', 'N/A')
                                                    st.markdown(f"**💰 {price}**")
                                                
                                                # Flight details in organized layout
                                                detail_col1, detail_col2, detail_col3 = st.columns(3)
                                                
                                                with detail_col1:
                                                    st.write("**🕐 Schedule:**")
                                                    departure_time = flight.get('departure_time', 'N/A')
                                                    arrival_time = flight.get('arrival_time', 'N/A')
                                                    
                                                    # Format datetime if it's in ISO format
                                                    if departure_time != 'N/A' and 'T' in str(departure_time):
                                                        try:
                                                            dt = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
                                                            departure_time = dt.strftime('%Y-%m-%d %H:%M')
                                                        except:
                                                            pass
                                                    
                                                    if arrival_time != 'N/A' and 'T' in str(arrival_time):
                                                        try:
                                                            dt = datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
                                                            arrival_time = dt.strftime('%Y-%m-%d %H:%M')
                                                        except:
                                                            pass
                                                    
                                                    st.write(f"🛫 **Departure:** {departure_time}")
                                                    st.write(f"🛬 **Arrival:** {arrival_time}")
                                                
                                                with detail_col2:
                                                    st.write("**⏱️ Journey Details:**")
                                                    duration = flight.get('duration', 'N/A')
                                                    stops = flight.get('stops', 'N/A')
                                                    st.write(f"⏳ **Duration:** {duration}")
                                                    
                                                    if stops == 0:
                                                        st.write("🎯 **Direct flight** (no stops)")
                                                    elif stops == 1:
                                                        st.write(f"🔄 **{stops} stop**")
                                                    else:
                                                        st.write(f"🔄 **{stops} stops**")
                                                
                                                with detail_col3:
                                                    st.write("**💼 Additional Info:**")
                                                    trip_type = flight.get('trip_type', 'one-way')
                                                    st.write(f"🎫 **Type:** {trip_type.title()}")
                                                    
                                                    # Show return flight info if available
                                                    if flight.get('return_departure_time'):
                                                        st.write("**� Return Flight:**")
                                                        return_dep = flight.get('return_departure_time', 'N/A')
                                                        if 'T' in str(return_dep):
                                                            try:
                                                                dt = datetime.fromisoformat(return_dep.replace('Z', '+00:00'))
                                                                return_dep = dt.strftime('%Y-%m-%d %H:%M')
                                                            except:
                                                                pass
                                                        st.write(f"🛫 {return_dep}")
                                                
                                                # Add a booking suggestion
                                                st.info("💡 **Tip:** Prices and availability change frequently. Book soon for the best deals!")
                                                
                                                if tab_idx < len(suggestion['flight_options']) - 1:
                                                    st.markdown("---")
                                    else:
                                        st.warning("🔍 Flight search temporarily unavailable for this destination. Please try the dedicated 'Search Flights' mode for more options.")
                                    
                                    # Display total cost estimate
                                    if suggestion.get('total_estimated_cost'):
                                        st.markdown("---")
                                        st.markdown(f"""
                                        <div style="background: #fef3c7; padding: 1rem; border-radius: 8px; border-left: 4px solid #f59e0b;">
                                            <h4 style="margin: 0; color: #92400e;">💰 Total Trip Cost Estimate</h4>
                                            <p style="margin: 0.5rem 0 0 0; color: #78350f; font-size: 1.1rem; font-weight: 600;">
                                                {suggestion['total_estimated_cost']}
                                            </p>
                                            <small style="color: #a16207;">*Includes flights + accommodation estimates. Actual costs may vary.</small>
                                        </div>
                                        """, unsafe_allow_html=True)
                                
                                # Add visual separator between suggestions
                                st.markdown("<br><hr style='border: 2px solid #e5e7eb; margin: 2rem 0;'><br>", unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.error(f"Error displaying suggestion {i}: {str(e)}")
                            print(f"Error details: {traceback.format_exc()}")
                    
                else:
                    # String format - use existing processing logic
                    # Convert the suggestions into a structured format
                    async def process_suggestions(suggestions_text):
                        """Process suggestions and add additional information"""
                        suggestions_list = []
                        if isinstance(suggestions_text, str):
                            # Parse the text response into structured suggestions
                            import re
                            # Look for bullet points or numbered items
                            suggestion_items = re.split(r'\n\s*[\*\•\-]\s*|\n\d+\.\s+', suggestions_text)
                            suggestion_items = [s.strip() for s in suggestion_items if s.strip()]
                            
                            for item in suggestion_items[:2]:  # Limit to 2 suggestions
                                if item:
                                    destination = item.split(" for ")[0] if " for " in item else item
                                    description = item.split(" for ")[1] if " for " in item else ""
                                    
                                    print(f"\n=== Processing suggestion for {destination} ===")
                                    
                                    # Create suggestion with additional information
                                    suggestion = {
                                        "destination": destination.replace('*', '').strip(),
                                        "description": description,
                                        "best_time_to_visit": await get_best_time(destination),
                                        "estimated_budget": await get_estimated_budget(destination),
                                        "duration": "7",  # Default to a week as per user request
                                        "weather": await get_weather(destination),
                                        "local_tips": await get_local_tips(destination),
                                        "hotels": await get_hotels(destination),
                                        "flights": await get_flights(destination)
                                    }
                                    suggestions_list.append(suggestion)
                                    print(f"\n=== Completed processing for {destination} ===")
                        
                        return suggestions_list
                    
                    # Process suggestions
                    suggestions_list = asyncio.run(process_suggestions(suggestions))
                
                # Display suggestions
                if suggestions_list:
                    st.subheader("Travel Suggestions")
                    for i, suggestion in enumerate(suggestions_list, 1):
                        print(f"\n=== Displaying suggestion {i} ===")
                        print(f"Type: {type(suggestion)}")
                        print(f"Content: {json.dumps(suggestion, indent=2)}")
                        
                        try:
                            st.write(f"## Suggestion {i}: {suggestion['destination']}")
                            
                            # Basic Information
                            st.write(f"**Description:** {suggestion['description']}")
                            
                            # Create three columns for key info
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                best_time = suggestion['best_time_to_visit']
                                if best_time == "Best time data unavailable":
                                    st.warning("Best time data unavailable")
                                else:
                                    st.write(f"**Best Time:** {best_time}")
                            with col2:
                                budget = suggestion['estimated_budget']
                                if budget == "Budget data unavailable":
                                    st.warning("Budget data unavailable")
                                else:
                                    st.write(f"**Budget:** {budget}")
                            with col3:
                                st.write(f"**Duration:** {suggestion['duration']} days")
                            

                            # Display additional information in expandable sections
                            with st.expander("🌤️ Weather Information"):
                                weather_info = suggestion.get('weather_info')
                                if weather_info and weather_info != "Weather data unavailable":
                                    st.write(weather_info)
                                elif isinstance(suggestion.get('weather'), dict):
                                    weather = suggestion['weather']
                                    if weather.get('status') == 'unavailable':
                                        st.warning("Weather data unavailable")
                                    else:
                                        st.write(f"**Temperature:** {weather.get('temperature', 'N/A')}°C")
                                        st.write(f"**Conditions:** {weather.get('description', 'N/A')}")
                                        st.write(f"**Humidity:** {weather.get('humidity', 'N/A')}%")
                                else:
                                    st.warning("Weather data unavailable")
                            
                            with st.expander("💡 Local Tips"):
                                local_tips = suggestion.get('local_tips', [])
                                if local_tips and local_tips[0] != "Local tips unavailable":
                                    for tip in local_tips:
                                        st.write(f"• {tip}")
                                else:
                                    st.warning("Local tips unavailable")
                            
                            with st.expander("🏨 Hotel Options"):
                                accommodation = suggestion.get('accommodation_suggestions', [])
                                hotels = suggestion.get('hotels', [])
                                
                                if accommodation:
                                    for acc in accommodation:
                                        st.write(f"• {acc}")
                                elif hotels and hotels[0].get('name') != "Hotel data unavailable":
                                    for hotel in hotels:
                                        st.write(f"**{hotel['name']}** - {hotel['price']} ({hotel['rating']})")
                                        st.write(f"*{hotel['address']}*")
                                        st.write("Amenities: " + ", ".join(hotel['amenities']))
                                        st.divider()
                                else:
                                    st.warning("Hotel data unavailable")
                            
                            with st.expander("✈️ Flight Options"):
                                transportation = suggestion.get('transportation', [])
                                flights = suggestion.get('flights', [])
                                
                                if transportation:
                                    st.write("**Transportation Options:**")
                                    for transport in transportation:
                                        st.write(f"• {transport}")
                                elif flights and flights[0].get('airline') != "Flight data unavailable":
                                    for flight in flights:
                                        st.write(f"**{flight['airline']}** - Flight {flight.get('flight_number', 'N/A')}")
                                        st.write(f"**{flight['departure']} → {flight['arrival']}**")
                                        st.write(f"**{flight['departure_time']} - {flight['arrival_time']}** ({flight['duration']})")
                                        st.write(f"**Price:** {flight['price']} | **Stops:** {flight['stops']}")
                                        st.divider()
                                else:
                                    st.warning("Flight data unavailable")
                            
                            # Display day-by-day itinerary if available
                            if suggestion.get('daily_itinerary'):
                                with st.expander("📅 Day-by-Day Itinerary", expanded=True):
                                    st.write("**Suggested Daily Activities:**")
                                    for day, activities in suggestion['daily_itinerary'].items():
                                        st.write(f"**{day}:** {activities}")
                            
                            # Display visa information if available
                            if suggestion.get('visa_info'):
                                with st.expander("🛂 Visa Information"):
                                    st.write(suggestion['visa_info'])
                            

                            st.divider()  # Add a visual separator between suggestions
                            
                        except Exception as e:
                            st.error(f"Error displaying suggestion {i}: {str(e)}")
                            print(f"Error details: {traceback.format_exc()}")
                else:
                    st.warning("No structured suggestions found. Here's the raw response:")
                    st.markdown(suggestions)
                    
            elif result["type"] == "error":
                st.error(f"An error occurred: {result['content']}")
            else:
                st.error("Unexpected response type received.")

elif mode == "Create Detailed Itinerary":
    st.header("📝 Create Detailed Itinerary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        destination = st.text_input("Destination", "Paris, France")
        start_date = st.date_input(
            "Start Date",
            datetime.now() + timedelta(days=30)
        )
    
    with col2:
        duration = st.number_input("Duration (days)", min_value=1, max_value=30, value=7)
        origin = st.text_input("Origin City (for flights)", "New York, USA")
    
    if st.button("Create Itinerary"):
        with st.spinner("Creating your personalized itinerary..."):
            try:                # Create travel request
                end_date = datetime.combine(start_date, datetime.min.time()) + timedelta(days=duration)
                travel_request = TravelRequest(
                    origin=origin,
                    destination=destination,
                    start_date=datetime.combine(start_date, datetime.min.time()),
                    end_date=end_date,
                    num_travelers=preferences.group_size,
                    preferences=preferences.__dict__,
                    budget=None
                )
                
                # Convert travel request to JSON-serializable format
                travel_request_dict = json_serializable(travel_request.__dict__)
                
                # Create context with request details
                context = {
                    "travel_request": travel_request_dict,
                    "mode": "itinerary"
                }
                
                # Use MCP server's agent to create itinerary
                async def create_itinerary():
                    async with httpx.AsyncClient() as client:
                        request_data = {
                            "query": f"Create a detailed itinerary for a trip from {origin} to {destination}",
                            "context": context,
                            "session_id": st.session_state.conversation_session_id,
                            "conversation_history": st.session_state.conversation_history
                        }
                        response = await client.post(
                            f"{AGENT_URL}/agent/execute",
                            json=request_data,
                            timeout=30.0
                        )
                        return response.json()
                
                result = asyncio.run(create_itinerary())
                
                if result.get("status") == "success":
                    # Update session state
                    if "session_id" in result:
                        st.session_state.conversation_session_id = result["session_id"]
                    if "conversation_history" in result:
                        st.session_state.conversation_history = result["conversation_history"]
                    
                    itinerary_response = result["result"].get("output", "")
                    
                    # Display itinerary
                    st.subheader("📝 Your Travel Itinerary")
                    st.markdown(itinerary_response)
                    
                    # Add some helpful information
                    st.info("💡 **Tip**: You can ask follow-up questions below to modify or get more details about your itinerary.")
                else:
                    st.error("Failed to create itinerary")

            except Exception as e:
                st.error(f"An error occurred while creating the itinerary: {str(e)}")

else:  # Search Flights
    st.header("✈️ Search Flights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        origin = st.text_input("From (Origin)", "New York")
        departure_date = st.date_input(
            "Departure Date",
            datetime.now() + timedelta(days=30)
        )
    
    with col2:
        destination = st.text_input("To (Destination)", "London")
        return_date = st.date_input(
            "Return Date (optional)",
            datetime.now() + timedelta(days=37),
            help="Leave blank for one-way flights"
        )
    
    # Trip type selection
    trip_type = st.radio("Trip Type", ["Round Trip", "One Way"], horizontal=True)
    
    if st.button("🔍 Search Flights"):
        with st.spinner("Searching for flights..."):
            try:
                from tools.travel_tools import FlightSearchTool
                flight_tool = FlightSearchTool()
                
                # Prepare search parameters
                search_date = datetime.combine(departure_date, datetime.min.time())
                return_search_date = None
                
                if trip_type == "Round Trip" and return_date > departure_date:
                    return_search_date = datetime.combine(return_date, datetime.min.time())
                
                # Search for flights
                logger.info(f"🛫 Searching flights: {origin} → {destination}")
                flights = asyncio.run(flight_tool.execute(
                    origin=origin,
                    destination=destination,
                    date=search_date,
                    return_date=return_search_date
                ))
                
                if flights and len(flights) > 0:
                    st.success(f"✅ Found {len(flights)} flight options")
                    
                    # Display flights in cards
                    for i, flight in enumerate(flights, 1):
                        with st.expander(f"✈️ Flight Option {i} - {flight.get('airline', 'N/A')} {flight.get('flight_number', '')}", expanded=(i <= 3)):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Price", flight.get('price', 'N/A'))
                                st.write(f"**Airline:** {flight.get('airline', 'N/A')}")
                                st.write(f"**Flight #:** {flight.get('flight_number', 'N/A')}")
                            
                            with col2:
                                st.write(f"**Departure:** {flight.get('departure_time', 'N/A')}")
                                st.write(f"**Arrival:** {flight.get('arrival_time', 'N/A')}")
                                st.write(f"**Duration:** {flight.get('duration', 'N/A')}")
                            
                            with col3:
                                stops = flight.get('stops', 0)
                                if stops == 0:
                                    st.write("**🛫 Direct Flight**")
                                else:
                                    st.write(f"**✈️ {stops} Stop(s)**")
                                
                                st.write(f"**Trip Type:** {flight.get('trip_type', 'N/A').title()}")
                                
                                # Show return flight info if available
                                if flight.get('return_departure_time'):
                                    st.write("**Return Flight:**")
                                    st.write(f"Departure: {flight.get('return_departure_time', 'N/A')}")
                                    st.write(f"Arrival: {flight.get('return_arrival_time', 'N/A')}")
                            
                            # Add booking button (placeholder for now)
                            if st.button(f"Select Flight {i}", key=f"select_flight_{i}"):
                                st.success(f"Flight {i} selected! (Booking integration coming soon)")
                    
                    # Add flight comparison
                    if len(flights) > 1:
                        st.markdown("---")
                        st.subheader("📊 Flight Comparison")
                        
                        comparison_data = []
                        for i, flight in enumerate(flights, 1):
                            comparison_data.append({
                                "Option": f"Flight {i}",
                                "Airline": flight.get('airline', 'N/A'),
                                "Price": flight.get('price', 'N/A'),
                                "Duration": flight.get('duration', 'N/A'),
                                "Stops": f"{flight.get('stops', 0)} stops" if flight.get('stops', 0) > 0 else "Direct"
                            })
                        
                        st.table(comparison_data)
                        
                else:
                    st.warning("❌ No flights found for the specified route and dates. Please try different search criteria.")
                    
                    # Show fallback suggestions
                    st.info("💡 **Suggestions:**")
                    st.write("• Try different departure/return dates")
                    st.write("• Check if the city names are spelled correctly")
                    st.write("• Consider nearby airports")
                    
            except Exception as e:
                st.error(f"❌ Flight search error: {str(e)}")
                logger.error(f"Flight search failed: {e}")
                
                # Show fallback message
                st.info("💡 **Alternative Options:**")
                st.write("• Use the Travel Suggestions mode for destination recommendations")
                st.write("• Try the Detailed Itinerary mode for complete trip planning")
                st.write("• Check airline websites directly for flight bookings")

# Backend server status check (simplified)
def check_backend_status():
    """Check if the local MCP agent is properly initialized"""
    try:
        return mcp_server and mcp_server.agent_executor is not None
    except:
        return False

# Show backend status in sidebar
with st.sidebar:
    if check_backend_status():
        st.success("✅ AI Agent Ready")
    else:
        st.warning("⚠️ Limited Functionality")

# Add chat interface for follow-up questions
st.markdown("---")
st.subheader("💬 Ask Follow-up Questions")

# Show conversation context if available
if st.session_state.conversation_history:
    with st.expander("📋 Conversation Context"):
        st.write("**Recent conversation summary:**")
        recent_messages = st.session_state.conversation_history[-4:]  # Show last 4 messages
        for msg in recent_messages:
            role_icon = "��" if msg["role"] == "user" else "🤖"
            st.write(f"{role_icon} **{msg['role'].title()}:** {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")

# Example follow-up questions
with st.expander("💡 Example Follow-up Questions"):
    st.write("Try asking questions like:")
    example_questions = [
        "Can you add more details about the restaurants?",
        "What about transportation options?",
        "Can you suggest alternative activities?",
        "What's the weather like during that time?",
        "Can you modify the itinerary for a different budget?",
        "What are the best photo spots?",
        "Can you add more cultural activities?",
        "What about safety considerations?"
    ]
    for question in example_questions:
        st.write(f"• {question}")

# Chat input
follow_up_question = st.text_input(
    "Ask a follow-up question about your travel plans...",
    placeholder="e.g., 'Can you add more details about the restaurants?' or 'What about transportation options?'",
    key="follow_up_input"
)

# Initialize session state for follow-up responses
if 'follow_up_responses' not in st.session_state:
    st.session_state.follow_up_responses = []

if st.button("Send Follow-up", key="send_follow_up"):
    if follow_up_question.strip():
        logger.info(f"💬 Processing follow-up question: {follow_up_question}")
        
        with st.spinner("Processing your follow-up question..."):
            try:
                # Create context with current preferences
                context = {
                    "preferences": preferences.model_dump(exclude_none=True),
                    "mode": "follow_up"
                }
                logger.debug(f"📋 Context prepared: {context}")
                
                # Prepare request with conversation state
                request_data = {
                    "query": follow_up_question,
                    "context": context,
                    "session_id": st.session_state.conversation_session_id,
                    "conversation_history": st.session_state.conversation_history
                }
                logger.debug(f"🚀 Sending request data: {json.dumps(request_data, indent=2)}")
                  # Send follow-up question using local agent
                async def send_follow_up():
                    logger.info(f"🤖 Processing follow-up with local MCP agent")
                    
                    if mcp_server.agent_executor:
                        # Use the MCP agent executor directly
                        agent_input = {
                            "input": follow_up_question,
                            "context": context,
                            "chat_history": []  # Add empty chat history for now
                        }
                        
                        result = await mcp_server.agent_executor.ainvoke(agent_input)
                        logger.info(f"✅ Follow-up result from agent: {result}")
                        
                        return {
                            "status": "success",
                            "result": {"output": result.get("output", "")},
                            "session_id": st.session_state.conversation_session_id or "local_session"
                        }
                    else:
                        # Fallback to direct tool usage
                        logger.warning("⚠️ Agent not available, using direct tool fallback")
                        response_content = await planner_tool.execute(
                            location=follow_up_question, 
                            duration=7, 
                            preferences={"prompt": follow_up_question, "context": context}
                        )
                        
                        # Format the response
                        if isinstance(response_content, list) and len(response_content) > 0:
                            formatted_response = ""
                            for suggestion in response_content:
                                if isinstance(suggestion, dict):
                                    dest = suggestion.get("destination", "")
                                    desc = suggestion.get("description", "")
                                    formatted_response += f"**{dest}**: {desc}\n\n"
                            response_text = formatted_response or "Here are some suggestions based on your question."
                        else:
                            response_text = "I've processed your question. Could you please be more specific about what you'd like to know?"
                        
                        return {
                            "status": "success",
                            "result": {"output": response_text},
                            "session_id": st.session_state.conversation_session_id or "local_session"
                        }
                
                result = asyncio.run(send_follow_up())
                logger.debug(f"✅ Follow-up result: {result}")
                
                if result.get("status") == "success":
                    # Update session state
                    if "session_id" in result:
                        st.session_state.conversation_session_id = result["session_id"]
                        logger.debug(f"🔄 Updated session ID: {result['session_id']}")
                    if "conversation_history" in result:
                        st.session_state.conversation_history = result["conversation_history"]
                        logger.debug(f"📚 Updated conversation history length: {len(result['conversation_history'])}")
                    
                    # Store the response to display it persistently
                    response_content = result["result"].get("output", "")
                    follow_up_entry = {
                        "question": follow_up_question,
                        "response": response_content,
                        "timestamp": datetime.now().isoformat()
                    }
                    st.session_state.follow_up_responses.append(follow_up_entry)
                    logger.info(f"✅ Follow-up response stored successfully")
                    
                    # Clear the input by rerunning (but response will persist)
                    st.rerun()
                else:
                    error_msg = "Failed to process follow-up question"
                    logger.error(f"❌ {error_msg}: {result}")
                    st.error(error_msg)
                    
            except Exception as e:
                error_msg = f"Error processing follow-up: {str(e)}"
                logger.error(f"❌ {error_msg}\n{traceback.format_exc()}")
                st.error(error_msg)

# Display follow-up responses
if st.session_state.follow_up_responses:
    st.markdown("---")
    st.subheader("🔄 Follow-up Responses")
    
    for i, entry in enumerate(st.session_state.follow_up_responses, 1):
        with st.expander(f"Q{i}: {entry['question'][:50]}..." if len(entry['question']) > 50 else f"Q{i}: {entry['question']}", expanded=True):
            st.markdown(f"**Question:** {entry['question']}")
            st.markdown(f"**AI Response:**")
            st.markdown(entry['response'])
            st.caption(f"Asked at: {datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Clear follow-up responses button
    if st.button("🗑️ Clear Follow-up History"):
        st.session_state.follow_up_responses = []
        logger.info("🗑️ Follow-up responses cleared")
        st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>Powered by AI Travel Planner • Built with ❤️ using Streamlit</p>
</div>
""", unsafe_allow_html=True)