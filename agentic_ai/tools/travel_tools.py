from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
from forex_python.converter import CurrencyRates
from overpass import API
from geopy.geocoders import Nominatim
from abc import ABC, abstractmethod
from transformers import pipeline, AutoTokenizer
try:
    from transformers import AutoModelForSeq2SeqGeneration
except ImportError:
    from transformers import AutoModelForCausalLM as AutoModelForSeq2SeqGeneration
import asyncio
import json
import os
import re
import traceback
from .travel_utils import logger

class BaseTravelTool(ABC):
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        
    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass

class FlightSearchTool(BaseTravelTool):
    """Enhanced flight search using Amadeus API for real-time flight data"""
    
    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        # Initialize Amadeus client
        self.amadeus_key = os.getenv('AMADEUS_API_KEY')
        self.amadeus_secret = os.getenv('AMADEUS_API_SECRET')
        
        if self.amadeus_key and self.amadeus_secret:
            try:
                from amadeus import Client
                self.amadeus = Client(
                    client_id=self.amadeus_key,
                    client_secret=self.amadeus_secret
                )
                self.use_amadeus = True
                logger.log_info("Amadeus API initialized for flight search", {})
            except ImportError:
                self.use_amadeus = False
                logger.log_warning("Amadeus package not installed, using fallback", {})
        else:
            self.use_amadeus = False
            logger.log_warning("Amadeus API credentials not found, using fallback", {})

    async def execute(self, origin: str, destination: str, date: datetime, return_date: datetime = None) -> List[Dict]:
        """
        Search for flights using Amadeus API or fallback to mock data.
        Supports both one-way and round-trip flight searches.
        """
        try:
            if self.use_amadeus:
                return await self._search_with_amadeus(origin, destination, date, return_date)
            else:
                return self._get_fallback_flights(origin, destination, date, return_date)
                
        except Exception as e:
            logger.log_error(e, "FlightSearchTool.execute")
            return self._get_fallback_flights(origin, destination, date, return_date)

    async def _search_with_amadeus(self, origin: str, destination: str, date: datetime, return_date: datetime = None) -> List[Dict]:
        """Search flights using Amadeus API"""
        try:
            # Convert city names to IATA codes
            origin_code = self._get_airport_code(origin)
            destination_code = self._get_airport_code(destination)
            
            print(f"🛫 Searching flights with Amadeus: {origin} ({origin_code}) → {destination} ({destination_code})")
            
            # Prepare search parameters
            search_params = {
                'originLocationCode': origin_code,
                'destinationLocationCode': destination_code,
                'departureDate': date.strftime('%Y-%m-%d'),
                'adults': 1,
                'max': 10
            }
            
            # Add return date for round-trip
            if return_date:
                search_params['returnDate'] = return_date.strftime('%Y-%m-%d')
                print(f"🔄 Round-trip search with return on {return_date.strftime('%Y-%m-%d')}")
            
            # Search flights
            response = self.amadeus.shopping.flight_offers_search.get(**search_params)
            
            if response.status_code != 200:
                raise Exception(f"Amadeus API returned status {response.status_code}")
            
            # Parse and format results
            flights = self._parse_amadeus_response(response.data, origin, destination)
            print(f"✅ Found {len(flights)} flights from Amadeus")
            
            return flights
            
        except Exception as e:
            print(f"⚠️ Amadeus search failed: {str(e)}")
            return self._get_fallback_flights(origin, destination, date, return_date)

    def _parse_amadeus_response(self, offers: List, origin: str, destination: str) -> List[Dict]:
        """Parse Amadeus flight offers into standardized format"""
        flights = []
        
        for offer in offers:
            try:
                # Extract basic offer info
                price = offer.get('price', {})
                itineraries = offer.get('itineraries', [])
                
                if not itineraries:
                    continue
                
                # Get outbound itinerary
                outbound = itineraries[0]
                segments = outbound.get('segments', [])
                
                if not segments:
                    continue
                
                first_segment = segments[0]
                last_segment = segments[-1]
                
                # Extract flight details
                flight_info = {
                    'airline': first_segment.get('carrierCode', 'Unknown'),
                    'flight_number': f"{first_segment.get('carrierCode', '')}{first_segment.get('number', '')}",
                    'departure': origin,
                    'arrival': destination,
                    'departure_time': first_segment.get('departure', {}).get('at', 'N/A'),
                    'arrival_time': last_segment.get('arrival', {}).get('at', 'N/A'),
                    'price': f"${price.get('total', 'N/A')}",
                    'duration': outbound.get('duration', 'N/A'),
                    'stops': len(segments) - 1,
                    'aircraft': first_segment.get('aircraft', {}).get('code', 'N/A'),
                    'booking_class': segments[0].get('cabin', 'ECONOMY') if segments else 'ECONOMY'
                }
                
                # Add return flight info if available
                if len(itineraries) > 1:
                    return_itinerary = itineraries[1]
                    return_segments = return_itinerary.get('segments', [])
                    if return_segments:
                        return_first = return_segments[0]
                        return_last = return_segments[-1]
                        
                        flight_info.update({
                            'return_departure_time': return_first.get('departure', {}).get('at', 'N/A'),
                            'return_arrival_time': return_last.get('arrival', {}).get('at', 'N/A'),
                            'return_duration': return_itinerary.get('duration', 'N/A'),
                            'return_stops': len(return_segments) - 1,
                            'trip_type': 'round-trip'
                        })
                else:
                    flight_info['trip_type'] = 'one-way'
                
                flights.append(flight_info)
                
            except Exception as e:
                print(f"⚠️ Error parsing flight offer: {e}")
                continue
        
        return flights[:10]  # Limit to 10 results

    def _get_airport_code(self, location: str) -> str:
        """Convert city/airport names to IATA codes"""
        location_upper = location.upper().strip()
        
        # IATA code mappings
        airport_codes = {
            # Major Indian cities
            'MUMBAI': 'BOM', 'BOMBAY': 'BOM',
            'DELHI': 'DEL', 'NEW DELHI': 'DEL',
            'BANGALORE': 'BLR', 'BENGALURU': 'BLR',
            'CHENNAI': 'MAA', 'MADRAS': 'MAA',
            'HYDERABAD': 'HYD',
            'KOLKATA': 'CCU', 'CALCUTTA': 'CCU',
            'PUNE': 'PNQ', 'GOA': 'GOI',
            'KOCHI': 'COK', 'COCHIN': 'COK',
            'AHMEDABAD': 'AMD', 'JAIPUR': 'JAI',
            
            # International major cities
            'LONDON': 'LHR', 'PARIS': 'CDG', 'NEW YORK': 'JFK',
            'TOKYO': 'NRT', 'DUBAI': 'DXB', 'SINGAPORE': 'SIN',
            'BANGKOK': 'BKK', 'HONG KONG': 'HKG',
            'LOS ANGELES': 'LAX', 'CHICAGO': 'ORD',
            'SYDNEY': 'SYD', 'MELBOURNE': 'MEL',
            'TORONTO': 'YYZ', 'VANCOUVER': 'YVR',
            'AMSTERDAM': 'AMS', 'FRANKFURT': 'FRA',
            'ZURICH': 'ZUR', 'MILAN': 'MXP',
            'ROME': 'FCO', 'MADRID': 'MAD',
            'BARCELONA': 'BCN', 'ISTANBUL': 'IST',
            'DOHA': 'DOH', 'ABU DHABI': 'AUH',
            'KUALA LUMPUR': 'KUL', 'MANILA': 'MNL',
            'JAKARTA': 'CGK', 'BALI': 'DPS',
            'SEOUL': 'ICN', 'BEIJING': 'PEK',
            'SHANGHAI': 'PVG', 'MOSCOW': 'SVO'
        }
        
        # Check direct mapping
        if location_upper in airport_codes:
            return airport_codes[location_upper]
        
        # If it's already a 3-letter IATA code, return as is
        if len(location_upper) == 3 and location_upper.isalpha():
            return location_upper
        
        # Default fallback - use first 3 letters
        return location_upper[:3].ljust(3, 'A')

    def _get_fallback_flights(self, origin: str, destination: str, date: datetime, return_date: datetime = None) -> List[Dict]:
        """
        Return fallback flight data when the API is unavailable.
        Supports both one-way and round-trip flights.
        """
        # Generate realistic-looking flight data
        airlines = ["Air India", "Emirates", "British Airways", "Lufthansa", "Singapore Airlines", "Qatar Airways"]
        base_prices = [450, 650, 850, 1200, 1500]
        
        flights = []
        trip_type = "round-trip" if return_date else "one-way"
        
        # Format dates for display
        departure_date_str = date.strftime('%Y-%m-%d')
        return_date_str = return_date.strftime('%Y-%m-%d') if return_date else None
        
        for i in range(3):  # Return 3 sample flights
            airline = airlines[i % len(airlines)]
            price = base_prices[i % len(base_prices)]
            
            # Adjust price for round-trip
            if return_date:
                price = int(price * 1.8)  # Round-trip typically costs more
            
            # Create departure time using the actual date and a sample time
            departure_hour = 8 + i * 2
            arrival_hour = departure_hour + 6 + i
            departure_datetime = date.replace(hour=departure_hour, minute=0, second=0, microsecond=0)
            arrival_datetime = date.replace(hour=arrival_hour, minute=30 + i * 15, second=0, microsecond=0)
            
            flight_info = {
                'airline': airline,
                'flight_number': f'{airline[:2].upper()}{1000 + i}',
                'departure': origin,
                'arrival': destination,
                'departure_time': departure_datetime.isoformat(),  # Full datetime with actual date
                'arrival_time': arrival_datetime.isoformat(),      # Full datetime with actual date
                'price': f'${price}',
                'duration': f'{6 + i}h {30 + i * 15}m',
                'stops': i,  # 0, 1, 2 stops
                'trip_type': trip_type,
                'departure_date': departure_date_str,  # Explicit date field
            }
            
            # Add return flight info for round-trip
            if return_date:
                return_departure_hour = 10 + i * 2
                return_arrival_hour = return_departure_hour + 6 + i
                return_departure_datetime = return_date.replace(hour=return_departure_hour, minute=0, second=0, microsecond=0)
                return_arrival_datetime = return_date.replace(hour=return_arrival_hour, minute=45 + i * 10, second=0, microsecond=0)
                
                flight_info.update({
                    'return_departure_time': return_departure_datetime.isoformat(),
                    'return_arrival_time': return_arrival_datetime.isoformat(),
                    'return_duration': f'{6 + i}h {45 + i * 10}m',
                    'return_date': return_date_str
                })
            
            flights.append(flight_info)
        
        return flights


class HotelSearchTool(BaseTravelTool):
    async def execute(self, location: str, check_in: datetime, check_out: datetime) -> List[Dict]:
        """
        Search for hotels using Hotels.com API through RapidAPI (free tier).
        """
        if not self.api_key:
            raise Exception("RapidAPI key not available for hotel search")
            
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'X-RapidAPI-Key': self.api_key,
                    'X-RapidAPI-Host': 'hotels4.p.rapidapi.com'
                }
                
                # Get location ID
                location_url = "https://hotels4.p.rapidapi.com/locations/v3/search"
                location_params = {
                    'q': location,
                    'locale': 'en_US',
                    'langid': '1033'
                }
                
                async with session.get(location_url, headers=headers, params=location_params) as response:
                    if response.status != 200:
                        raise Exception(f"Hotel location API returned status {response.status}")
                        
                    location_data = await response.json()
                    if not location_data.get('suggestions', []):
                        raise Exception(f"No location found for: {location}")
                    
                    # Get the first location ID
                    location_id = None
                    for suggestion in location_data['suggestions']:
                        if suggestion['group'] == 'CITY_GROUP':
                            if suggestion.get('entities'):
                                location_id = suggestion['entities'][0].get('destinationId')
                                break
                    
                    if not location_id:
                        raise Exception(f"Could not find location ID for: {location}")
                    
                    # Search for hotels with proper error handling
                    properties_url = "https://hotels4.p.rapidapi.com/properties/v2/list"
                    payload = {
                        "currency": "USD",
                        "eapid": 1,
                        "locale": "en_US",
                        "siteId": 300000001,
                        "destination": {"regionId": str(location_id)},
                        "checkInDate": {
                            "day": check_in.day,
                            "month": check_in.month,
                            "year": check_in.year
                        },
                        "checkOutDate": {
                            "day": check_out.day,
                            "month": check_out.month,
                            "year": check_out.year
                        },
                        "rooms": [{"adults": 1}],
                        "resultsStartingIndex": 0,
                        "resultsSize": 10
                    }
                    
                    async with session.post(properties_url, headers=headers, json=payload) as response:
                        if response.status != 200:
                            raise Exception(f"Hotel search API returned status {response.status}")
                            
                        hotels_data = await response.json()
                        hotels = []
                        
                        if hotels_data.get('data', {}).get('propertySearch', {}).get('properties'):
                            for hotel in hotels_data['data']['propertySearch']['properties']:
                                if isinstance(hotel, dict):  # Ensure hotel is a valid dictionary
                                    hotels.append({
                                        'name': hotel.get('name', 'Hotel Name Not Available'),
                                        'id': str(hotel.get('id', '')),
                                        'price': hotel.get('price', {}).get('formatted', 'Price Not Available'),
                                        'rating': hotel.get('reviews', {}).get('score', 'N/A'),
                                        'address': hotel.get('location', {}).get('address', {}).get('addressLine', 'Address Not Available'),
                                        'amenities': [amenity.get('text', '') for amenity in hotel.get('amenities', [])[:5] if isinstance(amenity, dict)]
                                    })
                        
                        return hotels
                        
        except Exception as e:
            logger.log_error(e, "HotelSearchTool.execute")
            # Return fallback hotel data when API fails
            return self._get_fallback_hotels(location, check_in, check_out)

    def _get_fallback_hotels(self, location: str, check_in: datetime, check_out: datetime) -> List[Dict]:
        """
        Return fallback hotel data when the API is unavailable.
        """
        # Generate realistic hotel data based on location
        hotel_types = [
            {"type": "Budget", "price_range": (40, 80), "suffix": "Inn"},
            {"type": "Mid-Range", "price_range": (90, 180), "suffix": "Hotel"},
            {"type": "Luxury", "price_range": (200, 400), "suffix": "Resort"}
        ]
        
        hotels = []
        for i, hotel_type in enumerate(hotel_types):
            price = hotel_type["price_range"][0] + (i * 20)
            rating = 3.5 + (i * 0.7)  # 3.5, 4.2, 4.9
            
            hotels.append({
                'name': f'{location} {hotel_type["suffix"]}',
                'id': f'hotel_{i+1}_{location.lower().replace(" ", "_")}',
                'price': f'${price}/night',
                'rating': f'{rating:.1f}',
                'address': f'Downtown {location}',
                'amenities': [
                    'Free WiFi',
                    'Air Conditioning', 
                    'Restaurant',
                    'Fitness Center' if i > 0 else '',
                    'Swimming Pool' if i > 1 else ''
                ]
            })
        
        return hotels

class WeatherTool(BaseTravelTool):
    async def execute(self, location: str, date: datetime) -> Dict:
        """
        Get weather information using python_weather (free).
        """
        try:
            async with python_weather.Client(unit=python_weather.METRIC) as client:
                weather = await client.get(location)
                
                # Get the current weather  # Use first forecast as current
                return {
                    'temperature': weather.temperature,
                    'description': weather.description,
                    'humidity': weather.humidity or 50  # Default if not available
                }
        except Exception as e:
            print(f"Weather API error: {str(e)}")
            return {
                'temperature': 'N/A',
                'description': 'Weather data unavailable',
                'humidity': 'N/A'
            }

class CurrencyTool(BaseTravelTool):
    def __init__(self):
        super().__init__()
        self.c = CurrencyRates()
        
    async def execute(self, amount: float, from_currency: str, to_currency: str) -> Dict:
        """
        Convert currency using forex-python (free).
        """
        rate = self.c.get_rate(from_currency, to_currency)
        converted = self.c.convert(from_currency, to_currency, amount)
        
        return {
            'original_amount': amount,
            'converted_amount': converted,
            'rate': rate,
            'from': from_currency,
            'to': to_currency
        }

class LocationInfoTool(BaseTravelTool):
    def __init__(self):
        super().__init__()
        self.geolocator = Nominatim(user_agent="travel_planner")
        
    async def execute(self, location: str) -> Dict:
        """Get location information and points of interest."""
        try:
            # Get location coordinates
            loc = self.geolocator.geocode(location)
            if not loc:
                raise Exception(f"Location not found: {location}")
            
            # Simplified query for better reliability
            query = f"""
            [out:json];
            area[name="{location}"]->.searchArea;
            (
                node["tourism"="information"](area.searchArea);
                node["tourism"="attraction"](area.searchArea);
            );
            out body;
            """
            
            api = API()
            result = api.get(query, responseformat="json")
            
            tips = []
            if result and 'elements' in result:
                for element in result['elements'][:5]:  # Limit to 5 POIs
                    if 'tags' in element:
                        name = element['tags'].get('name', 'Point of Interest')
                        tips.append(f"Visit {name}")
            
            if not tips:
                raise Exception(f"No points of interest found for: {location}")
            
            return {"tips": tips}
        except Exception as e:
            logger.log_error(e, "LocationInfoTool.execute")
            # Return fallback location info when API fails
            return self._get_fallback_location_info(location)

    def _get_fallback_location_info(self, location: str) -> Dict:
        """
        Return fallback location information when APIs are unavailable.
        """
        # Generic travel tips based on common destination types
        generic_tips = [
            f"Explore the historic downtown area of {location}",
            f"Visit local markets and try authentic {location} cuisine",
            f"Take guided tours to learn about {location}'s culture and history",
            f"Visit popular landmarks and monuments in {location}",
            f"Experience the local nightlife and entertainment scene"
        ]
        
        return {"tips": generic_tips}

def get_cached_pipeline(model_id: str = "microsoft/phi-2"):
    """Get a cached instance of the text generation pipeline."""
    return pipeline("text-generation", model=model_id, trust_remote_code=True)

class ItineraryPlannerTool(BaseTravelTool):
    """Tool for planning itineraries using local Ollama AI"""
    
    def __init__(self, model: str = "devstral:latest", host: str = "http://localhost:11434"):
        """Initialize the tool with Ollama configuration"""
        self.model = model
        self.host = host

    async def execute(self, location: str, duration: int, preferences: Dict) -> List[Dict]:
        """Execute the planning tool using local Ollama"""
        try:
            # Import ollama here to avoid import errors if not installed
            try:
                import ollama
            except ImportError:
                logger.log_warning("Ollama package not installed. Using fallback response.", {})
                return self._get_fallback_suggestions(location, duration)

            # Check if Ollama is running and model is available
            try:
                models = ollama.list()
                available_models = [model.model for model in models.models]
                
                if self.model not in available_models:
                    logger.log_warning(f"Model {self.model} not available. Using fallback response.", {})
                    return self._get_fallback_suggestions(location, duration)
                    
            except Exception as e:
                logger.log_warning(f"Cannot connect to Ollama: {e}. Using fallback response.", {})
                return self._get_fallback_suggestions(location, duration)

            # Create a more structured system prompt
            system_prompt = """You are a travel expert AI assistant. Your task is to generate EXACTLY 2 complete travel suggestions in valid JSON format.

CRITICAL: You must return ONLY the JSON array. Do not include any other text, explanations, or markdown formatting.

Format (return ONLY this JSON structure):
[
    {
        "destination": "Bangkok, Thailand",
        "description": "A vibrant city known for its street food, temples, and nightlife. Perfect for budget travelers seeking cultural experiences.",
        "best_time_to_visit": "November to March during the dry season",
        "estimated_budget": "$50-100 per day",
        "duration": "5",
        "activities": [
            "Visit the Grand Palace and Wat Phra Kaew",
            "Explore Chatuchak Weekend Market",
            "Take a Thai cooking class",
            "Temple hop to Wat Arun and Wat Pho",
            "Evening street food tour in Chinatown"
        ],
        "accommodation_suggestions": [
            "Lub d Bangkok Hostel ($15-20/night)",
            "Hotel Buddy Lodge ($40-60/night)",
            "Anantara Riverside ($150-200/night)"
        ],
        "transportation": [
            "BTS Skytrain and MRT ($1-2 per trip)",
            "Tuk-tuk and taxi ($3-10 per ride)"
        ],
        "local_tips": [
            "Always negotiate prices at markets",
            "Carry temple-appropriate clothing",
            "Use metered taxis instead of tuk-tuks at night"
        ],
        "weather_info": "Tropical climate with temperatures between 25-35°C year-round",
        "safety_info": "Generally safe for tourists. Be careful of scams near major attractions."
    },
    {
        "destination": "Prague, Czech Republic",
        "description": "A medieval city with stunning architecture, affordable beer, and rich history perfect for cultural exploration.",
        "best_time_to_visit": "May to September for warm weather",
        "estimated_budget": "$40-80 per day",
        "duration": "4",
        "activities": [
            "Explore Prague Castle and St. Vitus Cathedral",
            "Walk across Charles Bridge at sunset",
            "Visit the Astronomical Clock in Old Town Square",
            "Take a brewery tour in the Czech Republic's beer capital",
            "Wander through the Jewish Quarter"
        ],
        "accommodation_suggestions": [
            "Hostel One Home ($12-18/night)",
            "Hotel Golden Well ($80-120/night)",
            "Augustine Hotel ($200-300/night)"
        ],
        "transportation": [
            "Public transport pass ($5-8 per day)",
            "Walking tours and bike rentals ($15-25)"
        ],
        "local_tips": [
            "Try traditional Czech beer and goulash",
            "Book restaurants in advance during peak season",
            "Keep valuables secure in tourist areas"
        ],
        "weather_info": "Continental climate with warm summers and cold winters",
        "safety_info": "Very safe for tourists. Watch for pickpockets in crowded areas."
    }
]

Remember: Return ONLY the JSON array. No additional text or formatting. Focus on travel suggestions only.
"""
            
            # Prepare the prompt from preferences
            prompt = preferences.get('prompt', '')
            context = preferences.get('context', '')
            
            # Combine prompt and context
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            
            logger.log_info("Sending Request to Local Ollama", {
                "system_prompt": system_prompt,
                "user_prompt": full_prompt,
                "location": location,
                "duration": duration,
                "model": self.model
            })
            
            # Create the complete prompt for Ollama
            complete_prompt = f"System: {system_prompt}\n\nUser: {full_prompt}\n\nAssistant:"
            
            logger.log_info("Making request to Ollama", {"model": self.model, "prompt_length": len(complete_prompt)})
            
            # Make Ollama call
            try:
                response = ollama.generate(
                    model=self.model,
                    prompt=complete_prompt,
                    options={
                        'temperature': 0.7,
                        'num_predict': 3000,
                        'stop': ['```', '</json>']
                    },
                    stream=False
                )
                
                if 'response' not in response:
                    logger.log_error(Exception("Invalid response from Ollama"), "Ollama API Call")
                    return self._get_fallback_suggestions(location, duration)
                
                response_text = response['response']
                logger.log_info("Extracted Response Text", {"text": response_text[:200]})
                
                # Check if response is empty or incomplete
                if not response_text or response_text.strip() in ['', '[', ']']:
                    logger.log_warning("Received empty or incomplete response from Ollama")
                    return self._get_fallback_suggestions(location, duration)
                
                try:
                    suggestions = json.loads(response_text)
                    if isinstance(suggestions, list):
                        validated = self._validate_suggestions(suggestions)
                        logger.log_info("Successfully parsed JSON response", {"suggestions": validated})
                        return validated
                    elif isinstance(suggestions, dict):
                        validated = self._validate_suggestions([suggestions])
                        logger.log_info("Successfully parsed single suggestion", {"suggestions": validated})
                        return validated
                except json.JSONDecodeError:
                    logger.log_warning("JSON parse failed, attempting structured text parse")
                    return self._parse_structured_text(response_text)
                    
            except Exception as ollama_error:
                logger.log_error(ollama_error, "Ollama API Call")
                return self._get_fallback_suggestions(location, duration)
                
        except Exception as e:
            logger.log_error(e, "ItineraryPlannerTool.execute")
            return self._get_fallback_suggestions(location, duration)

    def _get_fallback_suggestions(self, location: str, duration: int) -> List[Dict]:
        """Returns pre-formatted fallback suggestions when API is unavailable."""
        # Extract actual destination from the location string
        destination = self._extract_destination(location)
        
        return [
            {
                "destination": destination,
                "description": f"Explore the vibrant culture and attractions of {destination}. A perfect destination for travelers seeking authentic experiences.",
                "best_time_to_visit": "Check local weather patterns for optimal timing",
                "estimated_budget": "$50-150 per day depending on preferences",
                "duration": str(duration),
                "activities": [
                    "Visit historic landmarks and cultural sites",
                    "Explore local markets and shopping districts", 
                    "Try authentic local cuisine and restaurants",
                    "Take guided tours of major attractions",
                    "Experience local nightlife and entertainment"
                ],
                "accommodation_suggestions": [
                    "Budget hostels ($20-40/night)",
                    "Mid-range hotels ($60-120/night)",
                    "Luxury resorts ($150-300/night)"
                ],
                "transportation": [
                    "Public transportation (buses, trains)",
                    "Taxi services and ride-sharing apps"
                ],
                "local_tips": [
                    "Learn basic local phrases",
                    "Research cultural customs and etiquette", 
                    "Keep copies of important documents"
                ],
                "weather_info": "Check current weather forecasts before traveling",
                "safety_info": "Follow standard travel safety precautions"
            },
            {
                "destination": f"Alternative destinations in {destination}",
                "description": f"Discover nearby attractions and hidden gems around {destination}. Perfect for extending your trip or exploring off-the-beaten-path destinations.",
                "best_time_to_visit": "Similar climate to main destination",
                "estimated_budget": "$40-120 per day for local experiences",
                "duration": str(max(2, duration - 1)),
                "activities": [
                    "Day trips to nearby towns and villages",
                    "Nature walks and outdoor activities",
                    "Local festivals and cultural events",
                    "Photography tours of scenic locations",
                    "Visit local museums and galleries"
                ],
                "accommodation_suggestions": [
                    "Local guesthouses ($25-50/night)",
                    "Boutique hotels ($70-140/night)",
                    "Eco-lodges ($100-200/night)"
                ],
                "transportation": [
                    "Rental cars for flexibility",
                    "Local bus services"
                ],
                "local_tips": [
                    "Book accommodations in advance",
                    "Try local specialties and street food",
                    "Respect local environment and wildlife"
                ],
                "weather_info": "Generally similar to main destination weather",
                "safety_info": "Check local conditions and travel advisories"
            }
        ]

    def _extract_destination(self, location_text: str) -> str:
        """Extract the actual destination from user input."""
        # Common destination patterns
        import re
        
        # Look for country names
        countries = ["Japan", "India", "China", "Thailand", "France", "Italy", "Spain", "Germany", "UK", "USA", "Australia", "Canada"]
        for country in countries:
            if country.lower() in location_text.lower():
                return country
        
        # Look for city names
        cities = ["Tokyo", "Paris", "London", "New York", "Bangkok", "Rome", "Barcelona", "Berlin", "Sydney", "Toronto"]
        for city in cities:
            if city.lower() in location_text.lower():
                return city
        
        # Extract words that might be destinations (capitalized words)
        words = location_text.split()
        for word in words:
            if word and word[0].isupper() and len(word) > 3 and word.isalpha():
                return word
        
        # Fallback to a generic destination
        return "Your chosen destination"
    
    def _validate_suggestions(self, suggestions: List[Dict]) -> List[Dict]:
        """Validate and fix suggestions to ensure they meet requirements"""
        validated_data = []
        for suggestion in suggestions:
            if isinstance(suggestion, dict):
                # Parse duration to ensure it's a number
                try:
                    duration_str = str(suggestion.get("duration", "5"))
                    duration_val = int(''.join(c for c in duration_str if c.isdigit()) or '5')
                except (ValueError, TypeError):
                    duration_val = 5

                # Ensure all required fields are present
                validated_suggestion = {
                    "destination": suggestion.get("destination", "Unknown Location"),
                    "description": suggestion.get("description", "A great destination matching your preferences."),
                    "best_time_to_visit": suggestion.get("best_time_to_visit", "Year-round"),
                    "estimated_budget": suggestion.get("estimated_budget", "Varies based on preferences"),
                    "duration": str(duration_val),
                    "activities": suggestion.get("activities", [
                        "Local sightseeing",
                        "Cultural experiences",
                        "Food tasting",
                        "Nature exploration",
                        "Local markets"
                    ])[:5],
                    "accommodation_suggestions": suggestion.get("accommodation_suggestions", [
                        "Local hotel",
                        "Budget guesthouse",
                        "Boutique hostel"
                    ])[:3],
                    "transportation": suggestion.get("transportation", [
                        "Public transport",
                        "Walking tours"
                    ])[:2],
                    "local_tips": suggestion.get("local_tips", [
                        "Research local customs",
                        "Learn basic phrases",
                        "Follow local guidelines"
                    ])[:3],
                    "weather_info": suggestion.get("weather_info", "Check local weather before booking"),
                    "safety_info": suggestion.get("safety_info", "Follow standard travel precautions")
                }
                validated_data.append(validated_suggestion)
        
        # Ensure exactly 2 suggestions
        while len(validated_data) < 2:
            validated_data.append({
                "destination": f"Alternative Destination {len(validated_data) + 1}",
                "description": "A great destination matching your preferences.",
                "best_time_to_visit": "Year-round",
                "estimated_budget": "Within your specified budget",
                "duration": "5",
                "activities": [
                    "Local sightseeing",
                    "Cultural experiences",
                    "Food tasting",
                    "Nature exploration",
                    "Local markets"
                ],
                "accommodation_suggestions": [
                    "Local hotel",
                    "Budget guesthouse",
                    "Boutique hostel"
                ],
                "transportation": [
                    "Public transport",
                    "Walking tours"
                ],
                "local_tips": [
                    "Research local customs",
                    "Learn basic phrases",
                    "Follow local guidelines"
                ],
                "weather_info": "Check local weather before booking",
                "safety_info": "Follow standard travel precautions"
            })
        
        return validated_data[:2]  # Return exactly 2 suggestions

    def _parse_structured_text(self, text: str) -> List[Dict]:
        """Parse structured text response"""
        suggestions = []
        current_suggestion = {}
        
        # Split by numbered sections or clear delimiters
        sections = re.split(r'(?:\d+[\)\.:]|Suggestion \d+:|\n\n+)', text)
        
        for section in sections:
            if not section.strip():
                continue
            
            lines = section.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Try to match key-value pairs
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()
                    
                    # Handle lists
                    if key in ['activities', 'accommodation_suggestions', 'transportation', 'local_tips']:
                        if '[' in value and ']' in value:
                            value = [v.strip().strip('"') for v in value.strip('[]').split(',')]
                        else:
                            value = [value]
                    
                    current_suggestion[key] = value
            
            if current_suggestion:
                suggestions.append(current_suggestion)
                current_suggestion = {}
        
        if suggestions:
            return self._validate_suggestions(suggestions)
        
        raise ValueError("Could not parse suggestions from text")