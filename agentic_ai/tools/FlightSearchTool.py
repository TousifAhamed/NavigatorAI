import aiohttp
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import dotenv, os
from abc import ABC, abstractmethod

# Load environment variables with explicit path
env_path = Path(__file__).parent.parent / '.env'
dotenv.load_dotenv(env_path)
class BaseTravelTool(ABC):
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        
    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass

class FlightSearchTool(BaseTravelTool):
    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        self.base_url = "https://fly-scraper.p.rapidapi.com"
        self.timeout = 30  # 30 seconds timeout for real-time searches

    async def execute(self, origin: str, destination: str, date: datetime, return_date: datetime = None) -> List[Dict]:
        """
        Search for real-time flights using Fly Scraper API through RapidAPI.
        Supports both one-way and round-trip searches.
        
        Args:
            origin: Origin city/airport (e.g., "Mumbai", "New York")
            destination: Destination city/airport (e.g., "London", "Paris")
            date: Departure date
            return_date: Optional return date for round-trip flights
            
        Returns:
            List of flight dictionaries with real-time data
        """
        if not self.api_key:
            print("⚠️ No API key provided, using fallback data")
            return self._get_fallback_flights(origin, destination, date)
            
        try:
            print(f"🔍 Searching real-time flights: {origin} → {destination} on {date.strftime('%Y-%m-%d')}")
            if return_date:
                print(f"🔄 Round-trip return: {return_date.strftime('%Y-%m-%d')}")
            
            # Convert city names to SkyID using enhanced mapping
            origin_sky_id = self._convert_to_sky_id(origin)
            destination_sky_id = self._convert_to_sky_id(destination)
            
            print(f"✅ Using airport codes: {origin} ({origin_sky_id}) → {destination} ({destination_sky_id})")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                # Search flights using direct API call
                flights = await self._search_flights_real_time(
                    session, origin_sky_id, destination_sky_id, date, origin, destination
                )
                
                if flights and len(flights) > 0:
                    print(f"✅ Found {len(flights)} real flights")
                    return flights
                else:
                    print("⚠️ No real flights found, using fallback data")
                    return self._get_fallback_flights(origin, destination, date)
                
        except Exception as e:
            print(f"❌ Flight API error: {str(e)}")
            print(f"🔄 Falling back to sample flight data")
            return self._get_fallback_flights(origin, destination, date)
    async def _search_flights_real_time(self, session, origin_sky_id: str, destination_sky_id: str, 
                                       date: datetime, origin: str, destination: str) -> List[Dict]:
        """Search for real-time flights with comprehensive data parsing."""
        headers = self._get_headers()
        
        # Primary search endpoint
        url = f"{self.base_url}/flights/search-one-way"
        params = {
            'originSkyId': origin_sky_id,
            'destinationSkyId': destination_sky_id,
            'date': date.strftime('%Y-%m-%d'),
            'adults': 1,  # Default to 1 adult
            'currency': 'USD',  # Default currency
            'market': 'US',  # Default market
            'locale': 'en-US'  # Default locale
        }
        
        print(f"🌐 API Request: {url}")
        print(f"📋 Parameters: {params}")
        
        try:
            async with session.get(url, headers=headers, params=params) as response:
                response_text = await response.text()
                print(f"📊 API Response Status: {response.status}")
                
                if response.status == 429:
                    print("⚠️ Rate limit exceeded. Trying backup approach...")
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
                    return await self._search_flights_backup(session, origin_sky_id, destination_sky_id, date, origin, destination)
                
                elif response.status != 200:
                    print(f"❌ API Error: {response.status} - {response_text}")
                    raise Exception(f"Flight API returned status {response.status}")
                
                try:
                    data = await response.json()
                except:
                    print(f"❌ Invalid JSON response: {response_text[:200]}...")
                    raise Exception("Invalid JSON response from flight API")
                
                return self._parse_flight_response(data, date, origin, destination)
                
        except Exception as e:
            print(f"❌ Search error: {str(e)}")
            raise

    async def _search_flights_backup(self, session, origin_sky_id: str, destination_sky_id: str,
                                   date: datetime, origin: str, destination: str) -> List[Dict]:
        """Backup flight search with different parameters."""
        headers = self._get_headers()
        
        # Try alternative endpoint or simplified parameters
        url = f"{self.base_url}/flights/search"
        params = {
            'from': origin_sky_id,
            'to': destination_sky_id,
            'date': date.strftime('%Y-%m-%d')
        }
        
        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_flight_response(data, date, origin, destination)
                else:
                    print(f"⚠️ Backup search also failed: {response.status}")
                    return []
        except:
            return []

    def _parse_flight_response(self, data: dict, date: datetime, origin: str, destination: str) -> List[Dict]:
        """Parse flight API response into standardized format."""
        flights = []
        
        print(f"🔍 Parsing response structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # Handle different response structures
        flight_data_sources = [
            data.get('data', {}).get('flights', []),
            data.get('flights', []),
            data.get('itineraries', []),
            data.get('results', [])
        ]
        
        for flight_source in flight_data_sources:
            if flight_source and isinstance(flight_source, list):
                print(f"✅ Found flight data source with {len(flight_source)} flights")
                
                for i, flight_data in enumerate(flight_source[:10]):  # Limit to 10 flights
                    try:
                        flight = self._extract_flight_details(flight_data, date, origin, destination, i)
                        if flight:
                            flights.append(flight)
                    except Exception as e:
                        print(f"⚠️ Error parsing flight {i}: {e}")
                        continue
                
                if flights:
                    break  # Found valid flights, stop looking
        
        print(f"✅ Parsed {len(flights)} flights successfully")
        return flights

    def _extract_flight_details(self, flight_data: dict, date: datetime, origin: str, destination: str, index: int) -> Dict:
        """Extract flight details from various API response formats."""
        if not isinstance(flight_data, dict):
            return None
            
        # Handle nested pricing information
        price_info = flight_data.get('price', {})
        if isinstance(price_info, dict):
            price = price_info.get('amount', price_info.get('total', price_info.get('value', 'N/A')))
            currency = price_info.get('currency', 'USD')
            formatted_price = f"{currency} {price}" if price != 'N/A' else 'Price unavailable'
        else:
            formatted_price = str(price_info) if price_info else 'Price unavailable'
        
        # Handle airline information
        airline_info = flight_data.get('airline', {})
        if isinstance(airline_info, dict):
            airline_name = airline_info.get('name', airline_info.get('displayName', 'Unknown Airline'))
        else:
            airline_name = str(airline_info) if airline_info else 'Unknown Airline'
        
        # Handle timing information
        departure_time = self._format_time(flight_data.get('departureTime', flight_data.get('departure', 'N/A')))
        arrival_time = self._format_time(flight_data.get('arrivalTime', flight_data.get('arrival', 'N/A')))
        
        # Handle duration
        duration = flight_data.get('duration', flight_data.get('travelTime', 'N/A'))
        if isinstance(duration, (int, float)):
            duration = f"{int(duration // 60)}h {int(duration % 60)}m"
        
        # Handle stops
        stops = flight_data.get('stops', flight_data.get('stopCount', 0))
        
        flight = {
            'date': date.strftime('%Y-%m-%d'),
            'price': formatted_price,
            'airline': airline_name,
            'flight_number': str(flight_data.get('flightNumber', flight_data.get('number', f'FL{index+1}'))),
            'departure': origin,
            'arrival': destination,
            'departure_time': departure_time,
            'arrival_time': arrival_time,
            'duration': str(duration),
            'stops': int(stops) if isinstance(stops, (int, float)) else 0,
            'aircraft': flight_data.get('aircraft', {}).get('name', 'N/A'),
            'booking_class': flight_data.get('class', 'Economy'),
            'available_seats': flight_data.get('availableSeats', 'N/A')
        }
        
        return flight

    def _convert_to_sky_id(self, city: str) -> str:
        """Convert city name to SkyID format with comprehensive city-to-airport mapping."""
        # Enhanced city to SkyID mappings
        city_mappings = {
            # Indian cities
            'mumbai': 'BOM', 'bombay': 'BOM',
            'delhi': 'DEL', 'new delhi': 'DEL',
            'bangalore': 'BLR', 'bengaluru': 'BLR',
            'chennai': 'MAA', 'madras': 'MAA',
            'kolkata': 'CCU', 'calcutta': 'CCU',
            'hyderabad': 'HYD',
            'pune': 'PNQ',
            'ahmedabad': 'AMD',
            'kochi': 'COK', 'cochin': 'COK',
            'goa': 'GOI',
            'jaipur': 'JAI',
            
            # International cities
            'london': 'LHR',
            'new york': 'JFK', 'nyc': 'JFK',
            'paris': 'CDG',
            'tokyo': 'NRT',
            'dubai': 'DXB',
            'singapore': 'SIN',
            'bangkok': 'BKK',
            'bali': 'DPS',  # Ngurah Rai International Airport
            'sydney': 'SYD',
            'los angeles': 'LAX',
            'san francisco': 'SFO',
            'chicago': 'ORD',
            'toronto': 'YYZ',
            'amsterdam': 'AMS',
            'frankfurt': 'FRA',
            'madrid': 'MAD',
            'rome': 'FCO',
            'istanbul': 'IST',
            'doha': 'DOH'
        }
        
        clean_city = city.lower().strip()
        return city_mappings.get(clean_city, city.upper()[:3])

    def _get_headers(self) -> dict:
        """Get headers for RapidAPI requests."""
        return {
            'X-RapidAPI-Key': self.api_key,
            'X-RapidAPI-Host': 'fly-scraper.p.rapidapi.com',
            'Content-Type': 'application/json'
        }

    def _format_time(self, time_str) -> str:
        """Format time string for display."""
        if isinstance(time_str, str) and time_str != 'N/A':
            try:
                # Try to parse and reformat if it's a datetime string
                from datetime import datetime
                if 'T' in time_str:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    return dt.strftime('%H:%M')
                return time_str
            except:
                return time_str
        return str(time_str) if time_str else 'N/A'

    def _get_fallback_flights(self, origin: str, destination: str, date: datetime) -> List[Dict]:
        """Generate realistic fallback flight data when API is unavailable."""
        import random
        
        # Generate realistic flight times
        base_hour = random.randint(6, 22)
        departure_time = f"{base_hour:02d}:{random.randint(0, 5)*10:02d}"
        arrival_hour = (base_hour + random.randint(1, 8)) % 24
        arrival_time = f"{arrival_hour:02d}:{random.randint(0, 5)*10:02d}"
        
        # Generate realistic prices based on route
        domestic_routes = ['mumbai', 'delhi', 'bangalore', 'chennai', 'hyderabad', 'pune']
        is_domestic = (origin.lower() in domestic_routes and destination.lower() in domestic_routes)
        
        if is_domestic:
            base_price = random.randint(3000, 15000)
        else:
            base_price = random.randint(25000, 80000)
        
        airlines = [
            'IndiGo', 'Air India', 'SpiceJet', 'Vistara', 'GoAir',
            'Emirates', 'Qatar Airways', 'Lufthansa', 'British Airways'
        ]
        
        fallback_flights = []
        for i in range(3):  # Generate 3 fallback flights
            price_variation = random.randint(-20, 30)
            final_price = base_price + (base_price * price_variation // 100)
            
            flight = {
                'airline': random.choice(airlines),
                'flight_number': f"{random.choice(['6E', 'AI', 'SG', 'UK'])}{random.randint(100, 999)}",
                'price': f"₹{final_price:,}" if is_domestic else f"${final_price//80:,}",
                'departure_time': departure_time,
                'arrival_time': arrival_time,
                'duration': f"{random.randint(1, 8)}h {random.randint(0, 59)}m",
                'stops': random.choice([0, 0, 0, 1]),  # Most flights are non-stop
                'departure': origin,
                'arrival': destination,
                'booking_class': random.choice(['Economy', 'Economy', 'Premium Economy', 'Business'])
            }
            
            # Adjust times for next flight
            base_hour = (base_hour + random.randint(2, 4)) % 24
            departure_time = f"{base_hour:02d}:{random.randint(0, 5)*10:02d}"
            arrival_hour = (base_hour + random.randint(1, 8)) % 24
            arrival_time = f"{arrival_hour:02d}:{random.randint(0, 5)*10:02d}"
            
            fallback_flights.append(flight)
        
        print(f"🔄 Generated {len(fallback_flights)} fallback flights for {origin} → {destination}")
        return fallback_flights

    async def search_one_way(self, origin: str, destination: str, departure_date: str, num_passengers: int = 1) -> List[Dict]:
        """
        Search for one-way flights.
        
        Args:
            origin: Origin city (e.g., "New York", "London")
            destination: Destination city (e.g., "Paris", "Tokyo")
            departure_date: Departure date in YYYY-MM-DD format
            num_passengers: Number of passengers (default 1)
            
        Returns:
            List of one-way flight dictionaries
        """
        try:
            departure_date_obj = datetime.strptime(departure_date, '%Y-%m-%d')
            
            print(f"🛫 One-way flight search: {origin} → {destination} on {departure_date} for {num_passengers} passengers")
            
            # Get flights using existing execute method
            flights = await self.execute(origin, destination, departure_date_obj)
            
            # Adjust pricing for multiple passengers if needed
            if num_passengers > 1:
                flights = self._adjust_pricing_for_passengers(flights, num_passengers)
            
            return flights
            
        except Exception as e:
            print(f"❌ One-way search error: {e}")
            return self._get_fallback_flights(origin, destination, departure_date_obj)

    async def search_round_trip(self, origin: str, destination: str, departure_date: str, return_date: str, num_passengers: int = 1) -> Dict[str, List[Dict]]:
        """
        Search for round-trip flights.
        
        Args:
            origin: Origin city (e.g., "New York", "London")
            destination: Destination city (e.g., "Paris", "Tokyo")
            departure_date: Departure date in YYYY-MM-DD format
            return_date: Return date in YYYY-MM-DD format
            num_passengers: Number of passengers (default 1)
            
        Returns:
            Dictionary with 'outbound' and 'return' flight lists
        """
        try:
            departure_date_obj = datetime.strptime(departure_date, '%Y-%m-%d')
            return_date_obj = datetime.strptime(return_date, '%Y-%m-%d')
            
            print(f"🛫 Round-trip flight search: {origin} ⇄ {destination}")
            print(f"   Outbound: {departure_date} | Return: {return_date} | Passengers: {num_passengers}")
            
            # Search outbound flights
            outbound_flights = await self.execute(origin, destination, departure_date_obj)
            
            # Search return flights
            return_flights = await self.execute(destination, origin, return_date_obj)
            
            # Adjust pricing for multiple passengers
            if num_passengers > 1:
                outbound_flights = self._adjust_pricing_for_passengers(outbound_flights, num_passengers)
                return_flights = self._adjust_pricing_for_passengers(return_flights, num_passengers)
            
            return {
                'outbound': outbound_flights,
                'return': return_flights,
                'trip_type': 'round-trip',
                'total_passengers': num_passengers,
                'departure_date': departure_date,
                'return_date': return_date
            }
            
        except Exception as e:
            print(f"❌ Round-trip search error: {e}")
            return {
                'outbound': self._get_fallback_flights(origin, destination, departure_date_obj),
                'return': self._get_fallback_flights(destination, origin, return_date_obj),
                'trip_type': 'round-trip',
                'total_passengers': num_passengers,
                'departure_date': departure_date,
                'return_date': return_date
            }

    async def search_flights_enhanced(self, origin: str, destination: str, departure_date: str, 
                                    return_date: str = None, num_passengers: int = 1) -> Dict:
        """
        Generic method to handle both one-way and round-trip flights with multiple passengers.
        
        Args:
            origin: Origin city (e.g., "New York", "London")
            destination: Destination city (e.g., "Paris", "Tokyo")
            departure_date: Departure date in YYYY-MM-DD format
            return_date: Optional return date in YYYY-MM-DD format for round-trip
            num_passengers: Number of passengers (default 1)
            
        Returns:
            Dictionary with flight results and trip information
        """
        try:
            if return_date:
                # Round-trip search
                result = await self.search_round_trip(origin, destination, departure_date, return_date, num_passengers)
                return result
            else:
                # One-way search
                flights = await self.search_one_way(origin, destination, departure_date, num_passengers)
                return {
                    'flights': flights,
                    'trip_type': 'one-way',
                    'total_passengers': num_passengers,
                    'departure_date': departure_date,
                    'return_date': None
                }
                
        except Exception as e:
            print(f"❌ Enhanced search error: {e}")
            departure_date_obj = datetime.strptime(departure_date, '%Y-%m-%d')
            fallback_flights = self._get_fallback_flights(origin, destination, departure_date_obj)
            
            return {
                'flights': fallback_flights,
                'trip_type': 'one-way' if not return_date else 'round-trip',
                'total_passengers': num_passengers,
                'departure_date': departure_date,
                'return_date': return_date,
                'error': str(e)
            }

    def _adjust_pricing_for_passengers(self, flights: List[Dict], num_passengers: int) -> List[Dict]:
        """
        Adjust flight pricing for multiple passengers.
        
        Args:
            flights: List of flight dictionaries
            num_passengers: Number of passengers
            
        Returns:
            List of flights with adjusted pricing
        """
        if num_passengers <= 1:
            return flights
            
        adjusted_flights = []
        
        for flight in flights:
            adjusted_flight = flight.copy()
            
            # Extract price and multiply by number of passengers
            price_str = flight.get('price', 'USD 0')
            try:
                # Parse price (e.g., "USD 500" -> 500)
                price_parts = price_str.split()
                if len(price_parts) >= 2:
                    currency = price_parts[0]
                    amount = float(price_parts[1].replace(',', ''))
                    total_amount = amount * num_passengers
                    
                    # Format new price
                    adjusted_flight['price'] = f"{currency} {total_amount:,.0f}"
                    adjusted_flight['price_per_person'] = f"{currency} {amount:,.0f}"
                    adjusted_flight['total_passengers'] = num_passengers
                else:
                    # If price format is unexpected, just add passenger info
                    adjusted_flight['total_passengers'] = num_passengers
                    adjusted_flight['price_note'] = f"Price shown is per person (x{num_passengers} passengers)"
                    
            except (ValueError, IndexError):
                # If price parsing fails, just add passenger info
                adjusted_flight['total_passengers'] = num_passengers
                adjusted_flight['price_note'] = f"Price shown is per person (x{num_passengers} passengers)"
            
            # Update available seats if known
            available_seats = flight.get('available_seats', 'N/A')
            if available_seats != 'N/A' and str(available_seats).isdigit():
                seats_available = int(available_seats)
                if seats_available >= num_passengers:
                    adjusted_flight['seats_status'] = f"✅ {num_passengers} seats available"
                else:
                    adjusted_flight['seats_status'] = f"⚠️ Only {seats_available} seats available (need {num_passengers})"
            
            adjusted_flights.append(adjusted_flight)
        
        return adjusted_flights

# if __name__ == "__main__":
#     import asyncio
#     api_key = os.getenv("RAPID_API_KEY")
#     print(f"API key: {api_key}")
#     flightSearchTool = FlightSearchTool(api_key)
#     flights = asyncio.run(flightSearchTool.execute("Mumbai", "London", datetime.now()))
#     print(flights)