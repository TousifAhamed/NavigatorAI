
import os
from .BaseAmadeusAPITool import BaseAmadeusAPITool

class AmadeusFlightSearchTool(BaseAmadeusAPITool):
    def flight_search(self, origin, destination, departure_date, return_date=None, adults=1):
        """
        Searches for flights using the Amadeus API.

        Args:
            origin (str): The origin airport code (e.g., "MAD").
            destination (str): The destination airport code (e.g., "CDG").
            departure_date (str): The departure date in YYYY-MM-DD format.
            return_date (str, optional): The return date in YYYY-MM-DD format. Defaults to None.
            adults (int, optional): The number of adult passengers. Defaults to 1.

        Returns:
            dict: A dictionary containing the flight search results.
        """
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
        }
        if return_date:
            params["returnDate"] = return_date

        return self._make_authenticated_request(url, params)

