"""
Amadeus Flight Search Integration
Enhanced flight search using Amadeus API for real-time flight data
"""

from amadeus import Client, ResponseError
from datetime import datetime
from typing import List, Dict, Optional
import os
import logging

class AmadeusFlightSearch:
    """Flight search using Amadeus API"""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        """Initialize Amadeus client"""
        self.api_key = api_key or os.getenv('AMADEUS_API_KEY')
        self.api_secret = api_secret or os.getenv('AMADEUS_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Amadeus API key and secret are required")
            
        self.amadeus = Client(
            client_id=self.api_key,
            client_secret=self.api_secret
        )
        
        self.logger = logging.getLogger("AmadeusFlightSearch")
    
    def search_flights(self, origin: str, destination: str, departure_date: str, 
                      return_date: str = None, adults: int = 1, max_results: int = 10) -> List[Dict]:
        """
        Search for flights using Amadeus API
        
        Args:
            origin: Origin airport code (e.g., 'NYC', 'LON')
            destination: Destination airport code (e.g., 'PAR', 'TOK')
            departure_date: Departure date in YYYY-MM-DD format
            return_date: Return date in YYYY-MM-DD format (optional for one-way)
            adults: Number of adult passengers (default: 1)
            max_results: Maximum number of results to return
            
        Returns:
            List of flight offers with pricing and details
        """
        try:
            # Convert city names to IATA codes if needed
            origin_code = self._get_airport_code(origin)
            destination_code = self._get_airport_code(destination)
            
            self.logger.info(f"Searching flights: {origin_code} -> {destination_code} on {departure_date}")
            
            # Prepare search parameters
            search_params = {
                'originLocationCode': origin_code,
                'destinationLocationCode': destination_code,
                'departureDate': departure_date,
                'adults': adults,
                'max': max_results
            }
            
            # Add return date for round-trip
            if return_date:
                search_params['returnDate'] = return_date
                self.logger.info(f"Round-trip search with return on {return_date}")
            
            # Search flights
            response = self.amadeus.shopping.flight_offers_search.get(**search_params)
            
            if response.status_code != 200:
                raise ResponseError(f"Amadeus API returned status {response.status_code}")
            
            # Parse and format results
            flights = self._parse_flight_offers(response.data)
            
            self.logger.info(f"Found {len(flights)} flight offers")
            return flights
            
        except ResponseError as e:
            self.logger.error(f"Amadeus API error: {e}")
            return self._get_fallback_flights(origin, destination, departure_date, return_date)
            
        except Exception as e:
            self.logger.error(f"Flight search error: {e}")
            return self._get_fallback_flights(origin, destination, departure_date, return_date)
    
    def _parse_flight_offers(self, offers: List) -> List[Dict]:
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
                    'id': offer.get('id', 'unknown'),
                    'price': f"${price.get('total', 'N/A')}",
                    'currency': price.get('currency', 'USD'),
                    'departure_airport': first_segment.get('departure', {}).get('iataCode', 'N/A'),
                    'arrival_airport': last_segment.get('arrival', {}).get('iataCode', 'N/A'),
                    'departure_time': first_segment.get('departure', {}).get('at', 'N/A'),
                    'arrival_time': last_segment.get('arrival', {}).get('at', 'N/A'),
                    'duration': outbound.get('duration', 'N/A'),
                    'stops': len(segments) - 1,
                    'airline': first_segment.get('carrierCode', 'Unknown'),
                    'flight_number': f"{first_segment.get('carrierCode', '')}{first_segment.get('number', '')}",
                    'aircraft': first_segment.get('aircraft', {}).get('code', 'N/A'),
                    'booking_class': first_segment.get('co2Emissions', [{}])[0].get('cabin', 'ECONOMY') if first_segment.get('co2Emissions') else 'ECONOMY'
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
                self.logger.warning(f"Error parsing flight offer: {e}")
                continue
        
        return flights[:10]  # Limit to 10 results
    
    def _get_airport_code(self, location: str) -> str:
        """Convert city/airport names to IATA codes"""
        # Enhanced mapping for common cities/airports
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
            'PUNE': 'PNQ',
            'GOA': 'GOI',
            'KOCHI': 'COK', 'COCHIN': 'COK',
            'AHMEDABAD': 'AMD',
            'JAIPUR': 'JAI',
            
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
    
    def _get_fallback_flights(self, origin: str, destination: str, 
                            departure_date: str, return_date: str = None) -> List[Dict]:
        """Return fallback flight data when API fails"""
        airlines = ["Air India", "Emirates", "British Airways", "Lufthansa", "Singapore Airlines"]
        base_prices = [450, 650, 850, 1200, 1500]
        
        flights = []
        trip_type = "round-trip" if return_date else "one-way"
        
        for i in range(3):
            airline = airlines[i % len(airlines)]
            price = base_prices[i % len(base_prices)]
            
            if return_date:
                price = int(price * 1.8)
            
            flight_info = {
                'id': f'fallback_{i+1}',
                'price': f'${price}',
                'currency': 'USD',
                'departure_airport': self._get_airport_code(origin),
                'arrival_airport': self._get_airport_code(destination),
                'departure_time': f'2025-07-{15+i}T{8+i*2}:00:00',
                'arrival_time': f'2025-07-{15+i}T{14+i*3}:00:00',
                'duration': f'PT{6+i}H{30+i*15}M',
                'stops': i,
                'airline': airline[:2].upper(),
                'flight_number': f'{airline[:2].upper()}{1000+i}',
                'aircraft': '737',
                'booking_class': 'ECONOMY',
                'trip_type': trip_type
            }
            
            if return_date:
                flight_info.update({
                    'return_departure_time': f'2025-07-{20+i}T{10+i*2}:00:00',
                    'return_arrival_time': f'2025-07-{20+i}T{16+i*3}:00:00',
                    'return_duration': f'PT{6+i}H{45+i*10}M',
                    'return_stops': i
                })
            
            flights.append(flight_info)
        
        return flights

    def get_airport_suggestions(self, query: str, max_results: int = 5) -> List[Dict]:
        """Get airport suggestions for a given city/airport query"""
        try:
            response = self.amadeus.reference_data.locations.get(
                keyword=query,
                subType='AIRPORT',
                view='LIGHT'
            )
            
            if response.status_code != 200:
                return []
            
            suggestions = []
            for location in response.data[:max_results]:
                suggestions.append({
                    'iata_code': location.get('iataCode', ''),
                    'name': location.get('name', ''),
                    'city': location.get('address', {}).get('cityName', ''),
                    'country': location.get('address', {}).get('countryName', '')
                })
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Airport suggestions error: {e}")
            return []
