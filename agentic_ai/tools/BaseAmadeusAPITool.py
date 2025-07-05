import os
import requests
from dotenv import load_dotenv
from abc import ABC

class BaseAmadeusAPITool(ABC):
    """Base class for Amadeus API tools to share common functionality."""
    
    def __init__(self):
        # Load environment variables from the correct path
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        load_dotenv(env_path)
        
        self.client_id = os.getenv("AMADEUS_API_KEY")
        self.client_secret = os.getenv("AMADEUS_API_SECRET")
        
        if not self.client_id or not self.client_secret:
            raise Exception("Missing Amadeus API credentials")
            
        self.token = self._get_access_token()

    def _get_access_token(self):
        """Get OAuth2 access token from Amadeus API."""
        url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        payload = f"grant_type=client_credentials&client_id={self.client_id}&client_secret={self.client_secret}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=30)
            if response.status_code == 200:
                token_data = response.json()
                return token_data["access_token"]
            else:
                raise Exception(f"Failed to get access token: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Exception getting token: {e}")

    def _make_authenticated_request(self, url, params):
        """Make an authenticated request with automatic token refresh."""
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Token might have expired, try to get a new one
                self.token = self._get_access_token()
                headers = {"Authorization": f"Bearer {self.token}"}
                response = requests.get(url, headers=headers, params=params, timeout=30)
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"Failed after token refresh: {response.status_code} - {response.text}"}
            else:
                return {"error": f"API request failed: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"error": f"Exception during API request: {str(e)}"}
