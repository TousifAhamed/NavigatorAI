"""
LangChain tools implementation for the travel planner using @tool decorators.
"""

from langchain.tools import tool
from typing import Dict, Any, List, Optional
from tools.travel_tools import ItineraryPlannerTool
from tools.Weathertool import WeatherTool
from tools.travel_utils import TravelUtils
import os
import asyncio

def convert_city_to_skyid(city: str) -> str:
    """
    Convert city name to proper SkyID format using enhanced mapping.
    
    Args:
        city: City name (e.g., "Hyderabad", "Mumbai", "Bombay")
        
    Returns:
        SkyID code (e.g., "HYD", "BOM")
    """
    # Enhanced city to SkyID mappings based on real airport codes
    city_mappings = {
        # Indian cities
        'mumbai': 'BOM',
        'bombay': 'BOM',  # Mumbai's old name
        'hyderabad': 'HYD',
        'delhi': 'DEL',
        'new delhi': 'DEL',
        'chennai': 'MAA',
        'madras': 'MAA',  # Chennai's old name
        'bangalore': 'BLR',
        'bengaluru': 'BLR',  # Bangalore's official name
        'kolkata': 'CCU',
        'calcutta': 'CCU',  # Kolkata's old name
        'pune': 'PNQ',
        'goa': 'GOI',
        'ahmedabad': 'AMD',
        'kochi': 'COK',
        'cochin': 'COK',  # Kochi's alternate name
        'thiruvananthapuram': 'TRV',
        'trivandrum': 'TRV',  # Thiruvananthapuram's common name
        'jaipur': 'JAI',
        'lucknow': 'LKO',
        'chandigarh': 'IXC',
        'indore': 'IDR',
        'nagpur': 'NAG',
        'vadodara': 'BDQ',
        'visakhapatnam': 'VTZ',
        'bhubaneswar': 'BBI',
        'coimbatore': 'CJB',
        'vijayawada': 'VGA',
        'srinagar': 'SXR',
        'agartala': 'IXA',
        'imphal': 'IMF',
        'dibrugarh': 'DIB',
        'guwahati': 'GAU',
        'raipur': 'RPR',
        'ranchi': 'IXR',
        'jodhpur': 'JDH',
        'udaipur': 'UDR',
        'jammu': 'IXJ',
        'patna': 'PAT',
        'varanasi': 'VNS',
        'aurangabad': 'IXU',
        'mangalore': 'IXE',
        'hubli': 'HBX',
        'tirupati': 'TIR',
        'rajkot': 'RAJ',
        'bhavnagar': 'BHU',
        'porbandar': 'PBD',
        
        # International cities
        'london': 'LHR',
        'new york': 'JFK',
        'paris': 'CDG',
        'tokyo': 'NRT',
        'dubai': 'DXB',
        'singapore': 'SIN',
        'kuala lumpur': 'KUL',
        'bangkok': 'BKK',
        'bali': 'DPS',  # Ngurah Rai International Airport
        'hong kong': 'HKG',
        'san francisco': 'SFO',
        'los angeles': 'LAX',
        'chicago': 'ORD',
        'toronto': 'YYZ',
        'sydney': 'SYD',
        'melbourne': 'MEL',
        'auckland': 'AKL',
        'amsterdam': 'AMS',
        'frankfurt': 'FRA',
        'istanbul': 'IST',
        'doha': 'DOH',
        'moscow': 'SVO',
        'beijing': 'PEK',
        'shanghai': 'PVG',
        'seoul': 'ICN',
        'cairo': 'CAI',
        'johannesburg': 'JNB',
        'rio de janeiro': 'GIG',
        'buenos aires': 'EZE',
    }
    
    return city_mappings.get(city.lower(), city.upper())  # Default to uppercase if not found

def convert_city_to_hotel_code(city: str) -> str:
    """
    Convert city name to proper hotel search city code.
    
    Args:
        city: City name (e.g., "Paris", "London", "Mumbai")
        
    Returns:
        City code for hotel search (e.g., "PAR", "LON", "BOM")
    """
    # City to hotel city code mappings
    hotel_city_mappings = {
        # Major international cities
        'paris': 'PAR',
        'london': 'LON', 
        'new york': 'NYC',
        'tokyo': 'TYO',
        'dubai': 'DXB',
        'singapore': 'SIN',
        'bangkok': 'BKK',
        'hong kong': 'HKG',
        'madrid': 'MAD',
        'barcelona': 'BCN',
        'rome': 'ROM',
        'milan': 'MIL',
        'amsterdam': 'AMS',
        'berlin': 'BER',
        'munich': 'MUC',
        'vienna': 'VIE',
        'zurich': 'ZUR',
        'istanbul': 'IST',
        'moscow': 'MOW',
        'sydney': 'SYD',
        'melbourne': 'MEL',
        
        # Indian cities  
        'mumbai': 'BOM',
        'delhi': 'DEL',
        'bangalore': 'BLR',
        'chennai': 'MAA',
        'kolkata': 'CCU',
        'hyderabad': 'HYD',
        'pune': 'PNQ',
        'ahmedabad': 'AMD',
        'jaipur': 'JAI',
        'kochi': 'COK',
        'goa': 'GOI',
    }
    
    return hotel_city_mappings.get(city.lower(), city[:3].upper())  # Default to first 3 letters uppercase

# All tool definitions moved to create_langchain_tools() for efficiency and maintainability

def create_langchain_tools(travel_utils: TravelUtils, itinerary_planner: ItineraryPlannerTool) -> List:
    """Create LangChain tools using @tool decorators for better compatibility."""
    
    # Import the new Amadeus-based tools
    from tools.AmadeusFlightSearchTool import AmadeusFlightSearchTool
    from tools.HotelSearchTool import HotelSearchTool
    from tools.CurrencyTool import CurrencyTool as CurrencyImpl
    from tools.Weathertool import WeatherTool as WeatherImpl
    
    print("✅ Using Amadeus-based FlightSearchTool and HotelSearchTool")
    
    # Initialize actual tool instances
    amadeus_key = os.getenv('AMADEUS_API_KEY')
    amadeus_secret = os.getenv('AMADEUS_API_SECRET')
    print(f"🔧 Initializing tools with Amadeus API: {'✅ Available' if amadeus_key and amadeus_secret else '❌ Missing'}")
    
    amadeus_flight_tool = AmadeusFlightSearchTool()
    amadeus_hotel_tool = HotelSearchTool()
    currency_tool = CurrencyImpl()
    weather_tool = WeatherImpl()

    @tool
    def flight_search(origin: str, destination: str = None, departure_date: str = None, return_date: str = None, num_passengers: int = 1) -> str:
        """Search for flights between cities with support for both one-way and round-trip bookings.
        
        Use this tool when you have complete flight information (origin, destination, departure date).
        For natural language queries, use intelligent_flight_search instead.
        
        Args:
            origin: Origin city or airport code (e.g., "Mumbai", "New York", "BOM", "JFK")
            destination: Destination city or airport code (e.g., "Delhi", "London", "DEL", "LHR") 
            departure_date: Departure date in YYYY-MM-DD format (e.g., "2025-07-15")
            return_date: Optional return date in YYYY-MM-DD format for round-trip (e.g., "2025-07-22")
            num_passengers: Number of passengers (default 1)
            
        Returns:
            Flight search results with pricing and schedule information for one-way or round-trip flights
        """
        try:
            # Handle case where entire JSON might be passed as origin parameter
            if isinstance(origin, str) and origin.startswith('{"'):
                try:
                    import json
                    parsed_input = json.loads(origin)
                    origin = parsed_input.get('origin', origin)
                    destination = parsed_input.get('destination', destination)
                    departure_date = parsed_input.get('departure_date', departure_date)
                    return_date = parsed_input.get('return_date', return_date)
                    num_passengers = parsed_input.get('num_passengers', num_passengers)
                    print("🔧 Fixed malformed JSON input in flight_search")
                except json.JSONDecodeError:
                    print("⚠️ Failed to parse JSON input, using parameters as provided")
            
            # Handle case where origin might contain the entire parameter string
            if isinstance(origin, str) and ('origin' in origin and 'destination' in origin):
                try:
                    # Try to extract parameters from the string
                    import re
                    origin_match = re.search(r'"origin":\s*"([^"]+)"', origin)
                    dest_match = re.search(r'"destination":\s*"([^"]+)"', origin)
                    date_match = re.search(r'"departure_date":\s*"([^"]+)"', origin)
                    return_match = re.search(r'"return_date":\s*"([^"]*)"', origin)
                    pass_match = re.search(r'"num_passengers":\s*(\d+)', origin)
                    
                    if origin_match and dest_match and date_match:
                        origin = origin_match.group(1)
                        destination = dest_match.group(1)
                        departure_date = date_match.group(1)
                        if return_match and return_match.group(1):
                            return_date = return_match.group(1)
                        if pass_match:
                            num_passengers = int(pass_match.group(1))
                        print("🔧 Extracted parameters from string input")
                except Exception as e:
                    print(f"⚠️ Failed to extract parameters: {e}")
            
            # Additional validation to ensure we have required parameters
            if not destination or destination == 'None':
                return "❌ Error: Destination is required for flight search"
            if not departure_date or departure_date == 'None':
                return "❌ Error: Departure date is required for flight search"
            
            from datetime import datetime
            trip_type = "round-trip" if return_date else "one-way"
            
            # Convert city names to proper SkyID format
            origin_skyid = convert_city_to_skyid(origin)
            destination_skyid = convert_city_to_skyid(destination)
            
            print(f"🛫 Flight search: {origin} ({origin_skyid}) → {destination} ({destination_skyid}) on {departure_date} ({trip_type}) for {num_passengers} passengers")
            
            # Parse departure date
            departure_date_obj = datetime.strptime(departure_date, '%Y-%m-%d')
            
            # Use the new Amadeus flight search tool
            try:
                origin_skyid = convert_city_to_skyid(origin)
                destination_skyid = convert_city_to_skyid(destination)
                
                result = amadeus_flight_tool.flight_search(
                    origin=origin_skyid,
                    destination=destination_skyid,
                    departure_date=departure_date,
                    return_date=return_date,
                    adults=num_passengers
                )
                
                if isinstance(result, dict) and result.get('data'):
                    flights = result.get('data', [])
                    if flights:
                        response_text = f"Found {len(flights)} flights from {origin} to {destination} on {departure_date}\n"
                        if num_passengers > 1:
                            response_text += f"Showing prices for {num_passengers} passengers:\n\n"
                        
                        for i, flight in enumerate(flights[:5], 1):
                            response_text += f"{i}. ✈️ Flight {flight.get('id', 'N/A')}\n"
                            response_text += f"   - Price: {flight.get('price', {}).get('total', 'N/A')}\n"
                            response_text += f"   - Carrier: {flight.get('validatingAirlineCodes', ['Unknown'])[0]}\n"
                            response_text += f"   - Duration: {flight.get('itineraries', [{}])[0].get('duration', 'N/A')}\n\n"
                        
                        return response_text
                    else:
                        return f"Sorry, no flights found from {origin} to {destination} on {departure_date}."
                else:
                    return f"Unable to search flights at this time. Please try again later."
                    
            except Exception as api_error:
                print(f"⚠️ Amadeus flight search failed: {api_error}")
                return f"Flight search encountered an error: {str(api_error)}"
        
        except Exception as e:
            print(f"❌ Error in flight search: {e}")
            return f"❌ Error processing flight request: {str(e)}"

    # Enhanced flight query parsing
    def parse_flight_query(query_text: str) -> dict:
        """Parse natural language flight query to extract flight details"""
        try:
            from enhanced_flight_parser import FlightQueryParser
            parser = FlightQueryParser()
            return parser.parse_flight_query(query_text)
        except ImportError:
            # Fallback parsing if enhanced parser not available
            import re
            result = {
                'origin': None,
                'destination': None, 
                'departure_date': None,
                'return_date': None,
                'num_passengers': 1
            }
            
            # Simple route extraction
            route_match = re.search(r'\bfrom\s+([^,\s]+(?:\s+[^,\s]+)*)\s+to\s+([^,\s]+(?:\s+[^,\s]+)*)', query_text, re.IGNORECASE)
            if route_match:
                result['origin'] = route_match.group(1).strip()
                result['destination'] = route_match.group(2).strip()
            
            # Simple date extraction
            date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', query_text)
            if date_match:
                result['departure_date'] = date_match.group(1)
                
            return result

    @tool
    def intelligent_flight_search(query: str) -> str:
        """
        Intelligent flight search that can parse natural language queries and extract flight details.
        
        Use this tool when users ask about flights in natural language without clearly structured parameters.
        This tool will parse the query to extract origin, destination, dates, and passengers automatically.
        
        Args:
            query: Natural language flight query (e.g., "flights from Mumbai to Delhi tomorrow")
            
        Returns:
            Flight search results or request for missing information
        """
        try:
            print(f"🧠 Intelligent flight search for: '{query}'")
            
            # Parse the query to extract flight details
            parsed = parse_flight_query(query)
            print(f"📝 Parsed query: {parsed}")
            
            # Check if we have enough information
            missing_info = []
            if not parsed.get('origin'):
                missing_info.append('origin city')
            if not parsed.get('destination'):
                missing_info.append('destination city')
            if not parsed.get('departure_date'):
                missing_info.append('departure date')
            
            # If information is missing, ask for it
            if missing_info:
                missing_str = ', '.join(missing_info)
                return f"To search for flights, I need the {missing_str}. Could you please provide these details? For example: 'flights from Mumbai to Delhi on 2025-07-15'"
            
            # Use the regular flight search with extracted parameters
            return flight_search(
                origin=parsed['origin'],
                destination=parsed['destination'],
                departure_date=parsed['departure_date'],
                return_date=parsed.get('return_date'),
                num_passengers=parsed.get('num_passengers', 1)
            )
            
        except Exception as e:
            print(f"❌ Error in intelligent flight search: {e}")
            return f"I'd be happy to help you search for flights! Please provide the origin city, destination city, and departure date. For example: 'flights from Mumbai to Delhi on 2025-07-15'"

    @tool
    def currency_conversion(amount: float, from_currency: str, to_currency: str) -> str:
        """Convert currency from one type to another with current exchange rates.
        
        Args:
            amount: Amount to convert (e.g., 100.0)
            from_currency: Source currency code (e.g., "USD", "EUR", "GBP")
            to_currency: Target currency code (e.g., "EUR", "JPY", "CAD")
            
        Returns:
            Conversion result with exchange rate information
        """
        try:
            print(f"💱 Currency conversion: {amount} {from_currency} → {to_currency}")
            result = asyncio.run(currency_tool.execute(amount, from_currency, to_currency))
            
            if result:
                converted_amount = result.get('converted_amount', 'N/A')
                rate = result.get('exchange_rate', 'N/A')
                return f"{amount} {from_currency} = {converted_amount} {to_currency}\nExchange rate: 1 {from_currency} = {rate} {to_currency}"
            else:
                return f"Could not convert {amount} {from_currency} to {to_currency}. Please check currency codes."
                
        except Exception as e:
            print(f"❌ Currency conversion error: {e}")
            return f"Error converting currency: {str(e)}"

    @tool 
    def weather_info(location: str, date: Optional[str] = None) -> str:
        """Get current weather information for a location.
        
        Args:
            location: Location to get weather for (e.g., "Tokyo", "New York", "London")
            date: Optional date for weather forecast (YYYY-MM-DD format)
            
        Returns:
            Weather information including temperature, conditions, and forecast
        """
        try:
            from datetime import datetime
            print(f"🌤️ Weather info for: {location} on {date or 'current'}")
            date_obj = datetime.now() if not date else datetime.strptime(date, '%Y-%m-%d')
            result = asyncio.run(weather_tool.execute(location, date_obj))
            
            if result:
                temp = result.get('temperature', 'N/A')
                condition = result.get('condition', 'N/A')
                humidity = result.get('humidity', 'N/A')
                return f"Weather in {location}:\n- Temperature: {temp}\n- Condition: {condition}\n- Humidity: {humidity}"
            else:
                return f"Could not get weather information for {location}. Please check the location name."
                
        except Exception as e:
            print(f"❌ Weather info error: {e}")
            return f"Error getting weather information: {str(e)}"

    @tool
    def travel_planner(destination: str, duration: int = 7, preferences: str = "general sightseeing") -> str:
        """Create detailed day-by-day travel itineraries for destinations.
        
        Use this tool when users ask for trip planning, itineraries, or what to do in a city.
        
        Args:
            destination: Destination city/country (e.g., "Tokyo", "Paris", "Thailand")
            duration: Number of days for the trip (e.g., 3, 7, 10)
            preferences: Travel preferences (e.g., "culture and food", "adventure", "relaxation")
            
        Returns:
            Detailed day-by-day itinerary with activities, dining, and recommendations
        """
        try:
            print(f"📝 Travel planner: {destination} for {duration} days ({preferences})")
            
            # Create enhanced query for better itinerary generation
            enhanced_query = f"Create a detailed {duration}-day itinerary for {destination} focusing on {preferences}"
            
            result = asyncio.run(itinerary_planner.execute(enhanced_query, duration, {
                "prompt": enhanced_query,
                "destination": destination,
                "duration": duration,
                "preferences": preferences
            }))
            
            if result:
                # Ensure the result includes day-by-day breakdown
                formatted_result = f"🌍 {duration}-Day Travel Itinerary for {destination}\n"
                formatted_result += f"Focus: {preferences}\n\n"
                
                # If the result doesn't have proper day structure, enhance it
                if "Day" not in result or result.count("Day") < duration:
                    formatted_result += f"{result}\n\n"
                    formatted_result += "📅 Day-by-Day Breakdown:\n\n"
                    
                    # Generate basic day structure if missing
                    for day in range(1, duration + 1):
                        formatted_result += f"Day {day}:\n"
                        formatted_result += f"- Morning: Explore local attractions\n"
                        formatted_result += f"- Afternoon: Cultural activities and dining\n"
                        formatted_result += f"- Evening: Local entertainment\n\n"
                else:
                    formatted_result += result
                
                return formatted_result
            else:
                # Fallback day-by-day structure
                fallback_itinerary = f"🌍 {duration}-Day Travel Guide for {destination}\n\n"
                
                for day in range(1, duration + 1):
                    fallback_itinerary += f"Day {day}:\n"
                    fallback_itinerary += f"- Morning: Explore {destination}'s main attractions\n"
                    fallback_itinerary += f"- Afternoon: Local cuisine and cultural sites\n"
                    fallback_itinerary += f"- Evening: Experience local nightlife/entertainment\n\n"
                
                fallback_itinerary += f"💡 Tips: Research local transportation, book accommodations in advance, and try local specialties!\n"
                return fallback_itinerary
                
        except Exception as e:
            print(f"❌ Travel planner error: {e}")
            # Return structured fallback even on error
            fallback = f"🌍 Basic {duration}-Day Guide for {destination}\n\n"
            for day in range(1, duration + 1):
                fallback += f"Day {day}: Plan activities, dining, and sightseeing\n"
            return fallback

    @tool
    def search_flights_flexible(flight_request: str) -> str:
        """Flexible flight search tool that accepts JSON-formatted flight request.
        
        Use this tool when the regular flight_search has parameter issues.
        
        Args:
            flight_request: JSON string containing flight search parameters:
                {
                    "origin": "Mumbai", 
                    "destination": "Delhi", 
                    "departure_date": "2025-07-15",
                    "return_date": "2025-07-22" (optional),
                    "num_passengers": 1
                }
                
        Returns:
            Flight search results with pricing and schedule information
        """
        try:
            import json
            import re
            
            # Try to parse as JSON first
            try:
                if flight_request.startswith('{') and flight_request.endswith('}'):
                    params = json.loads(flight_request)
                else:
                    # If not proper JSON, try to extract parameters with regex
                    params = {}
                    origin_match = re.search(r'"origin":\s*"([^"]+)"', flight_request)
                    dest_match = re.search(r'"destination":\s*"([^"]+)"', flight_request)
                    date_match = re.search(r'"departure_date":\s*"([^"]+)"', flight_request)
                    return_match = re.search(r'"return_date":\s*"([^"]*)"', flight_request)
                    pass_match = re.search(r'"num_passengers":\s*(\d+)', flight_request)
                    
                    if origin_match:
                        params['origin'] = origin_match.group(1)
                    if dest_match:
                        params['destination'] = dest_match.group(1)
                    if date_match:
                        params['departure_date'] = date_match.group(1)
                    if return_match and return_match.group(1):
                        params['return_date'] = return_match.group(1)
                    if pass_match:
                        params['num_passengers'] = int(pass_match.group(1))
            except (json.JSONDecodeError, AttributeError):
                return "❌ Error: Could not parse flight request. Please provide JSON format with origin, destination, and departure_date."
            
            # Extract required parameters
            origin = params.get('origin')
            destination = params.get('destination')
            departure_date = params.get('departure_date')
            return_date = params.get('return_date')
            num_passengers = params.get('num_passengers', 1)
            
            # Validate required parameters
            if not origin:
                return "❌ Error: Origin is required"
            if not destination:
                return "❌ Error: Destination is required"
            if not departure_date:
                return "❌ Error: Departure date is required"
            
            # Call the regular flight search logic
            from datetime import datetime
            trip_type = "round-trip" if return_date else "one-way"
            
            # Convert city names to proper SkyID format
            origin_skyid = convert_city_to_skyid(origin)
            destination_skyid = convert_city_to_skyid(destination)
            
            print(f"🛫 Flexible flight search: {origin} ({origin_skyid}) → {destination} ({destination_skyid}) on {departure_date} ({trip_type}) for {num_passengers} passengers")
            
            # Parse departure date
            departure_date_obj = datetime.strptime(departure_date, '%Y-%m-%d')
            
            # Use the Amadeus flight tool
            try:
                result = amadeus_flight_tool.flight_search(
                    origin=origin_skyid,
                    destination=destination_skyid,
                    departure_date=departure_date,
                    return_date=return_date,
                    adults=num_passengers
                )
                
                if isinstance(result, dict) and result.get('data'):
                    flights = result.get('data', [])
                    if flights:
                        response_text = f"Found {len(flights)} flights from {origin} to {destination} on {departure_date}\n"
                        if num_passengers > 1:
                            response_text += f"Showing prices for {num_passengers} passengers:\n\n"
                        
                        for i, flight in enumerate(flights[:5], 1):
                            response_text += f"{i}. ✈️ Flight {flight.get('id', 'N/A')}\n"
                            response_text += f"   - Price: {flight.get('price', {}).get('total', 'N/A')}\n"
                            response_text += f"   - Carrier: {flight.get('validatingAirlineCodes', ['Unknown'])[0]}\n"
                            response_text += f"   - Duration: {flight.get('itineraries', [{}])[0].get('duration', 'N/A')}\n\n"
                        
                        return response_text
                    else:
                        return f"No flights found for {origin} to {destination} on {departure_date}"
                else:
                    return f"No flights found for {origin} to {destination} on {departure_date}"
                    
            except Exception as search_error:
                print(f"❌ Flight search error: {search_error}")
                return f"❌ Flight search failed: {str(search_error)}"
            
        except Exception as e:
            print(f"❌ Error in flexible flight search: {e}")
            return f"❌ Error processing flight request: {str(e)}"

    return [flight_search, intelligent_flight_search, currency_conversion, weather_info, travel_planner, search_flights_flexible]

def register_tools(mcp_server, travel_utils: TravelUtils, itinerary_planner: ItineraryPlannerTool):
    """Register all tools with the MCP server."""
    tools = create_langchain_tools(travel_utils, itinerary_planner)
    for tool in tools:
        mcp_server.register_tool(tool.name, tool)
    return tools