
import os
from .BaseAmadeusAPITool import BaseAmadeusAPITool

class HotelSearchTool(BaseAmadeusAPITool):
    def hotel_search(self, city_code, radius=10, radius_unit='KM', amenities=None):
        """
        Searches for hotels in a given city using the Amadeus API.

        Args:
            city_code (str): The city code (e.g., "PAR" for Paris).
            radius (int, optional): The radius around the city center to search. Defaults to 10.
            radius_unit (str, optional): The unit of the radius ('KM' or 'MILE'). Defaults to 'KM'.
            amenities (list, optional): A list of amenities to filter by. Defaults to None.

        Returns:
            dict: A dictionary containing the hotel search results.
        """
        url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city"
        params = {
            "cityCode": city_code,
            "radius": radius,
            "radiusUnit": radius_unit,
        }
        if amenities:
            params["amenities"] = ",".join(amenities)

        return self._make_authenticated_request(url, params)

