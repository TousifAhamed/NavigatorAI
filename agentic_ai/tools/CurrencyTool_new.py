from typing import Dict
from abc import ABC, abstractmethod
import http.client
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()


class BaseTravelTool(ABC):
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        
    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass

class CurrencyTool(BaseTravelTool):
    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        # Use the provided RapidAPI key or get from environment
        self.rapidapi_key = api_key or os.getenv('RAPID_API_KEY') or "ba636c7e69msh28a056533e79d35p1317d3jsn23a5700f9c9d"
        
        # Fallback exchange rates (approximate) - used when API is unavailable
        self.fallback_rates = {
            ('USD', 'EUR'): 0.85,
            ('EUR', 'USD'): 1.18,
            ('USD', 'GBP'): 0.73,
            ('GBP', 'USD'): 1.37,
            ('USD', 'JPY'): 110.0,
            ('JPY', 'USD'): 0.0091,
            ('USD', 'INR'): 75.0,
            ('INR', 'USD'): 0.013,
            ('EUR', 'GBP'): 0.86,
            ('GBP', 'EUR'): 1.16,
            ('USD', 'CAD'): 1.25,
            ('CAD', 'USD'): 0.80,
            ('USD', 'AUD'): 1.35,
            ('AUD', 'USD'): 0.74,
            ('USD', 'CHF'): 0.92,
            ('CHF', 'USD'): 1.09,
            ('USD', 'CNY'): 6.45,
            ('CNY', 'USD'): 0.155,
        }
        
    def _get_conversion_rate_sync(self, from_currency: str, to_currency: str) -> float:
        """Get conversion rate using RapidAPI Currency Converter (synchronous)"""
        try:
            conn = http.client.HTTPSConnection("currency-converter241.p.rapidapi.com")
            
            headers = {
                'x-rapidapi-key': self.rapidapi_key,
                'x-rapidapi-host': "currency-converter241.p.rapidapi.com"
            }
            
            # Make API request
            endpoint = f"/conversion_rate?from={from_currency.upper()}&to={to_currency.upper()}"
            conn.request("GET", endpoint, headers=headers)
            
            res = conn.getresponse()
            data = res.read()
            
            if res.status == 200:
                response_data = json.loads(data.decode("utf-8"))
                print(f"🌐 API Response: {response_data}")
                
                # Parse the response - the API returns different formats
                if isinstance(response_data, dict):
                    # Try different possible response formats
                    rate = (response_data.get('conversion_rate') or 
                           response_data.get('rate') or 
                           response_data.get('result') or
                           response_data.get('exchange_rate'))
                    
                    if rate is not None:
                        return float(rate)
                elif isinstance(response_data, (int, float)):
                    return float(response_data)
                
                print(f"⚠️ Unexpected API response format: {response_data}")
                raise ValueError("Invalid API response format")
            else:
                print(f"❌ API request failed with status {res.status}")
                raise Exception(f"API request failed: {res.status}")
                
        except Exception as e:
            print(f"❌ Currency API error: {e}")
            raise e
        finally:
            conn.close()
    
    async def _get_conversion_rate(self, from_currency: str, to_currency: str) -> float:
        """Async wrapper for the synchronous API call"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_conversion_rate_sync, from_currency, to_currency)
        
    async def execute(self, amount: float, from_currency: str, to_currency: str) -> Dict:
        """
        Convert currency using RapidAPI Currency Converter with fallback.
        """
        try:
            # If same currency, return as is
            if from_currency.upper() == to_currency.upper():
                return {
                    'original_amount': amount,
                    'converted_amount': amount,
                    'rate': 1.0,
                    'from': from_currency.upper(),
                    'to': to_currency.upper(),
                    'status': 'success',
                    'source': 'same_currency'
                }
            
            print(f"💱 Converting {amount} {from_currency} to {to_currency}")
            
            # Try RapidAPI first
            if self.rapidapi_key:
                try:
                    rate = await self._get_conversion_rate(from_currency, to_currency)
                    converted = amount * rate
                    
                    return {
                        'original_amount': amount,
                        'converted_amount': round(converted, 2),
                        'rate': round(rate, 6),
                        'from': from_currency.upper(),
                        'to': to_currency.upper(),
                        'status': 'success',
                        'source': 'rapidapi_live'
                    }
                except Exception as e:
                    print(f"⚠️ RapidAPI failed: {e}, using fallback rates")
                    # Fall through to fallback rates
            
            # Use fallback rates
            rate_key = (from_currency.upper(), to_currency.upper())
            reverse_key = (to_currency.upper(), from_currency.upper())
            
            if rate_key in self.fallback_rates:
                rate = self.fallback_rates[rate_key]
            elif reverse_key in self.fallback_rates:
                rate = 1.0 / self.fallback_rates[reverse_key]
            else:
                # Default fallback rate for unknown currencies
                rate = 1.0
                print(f"⚠️ No rate found for {from_currency} to {to_currency}, using 1:1")
            
            converted = amount * rate
            
            return {
                'original_amount': amount,
                'converted_amount': round(converted, 2),
                'rate': round(rate, 6),
                'from': from_currency.upper(),
                'to': to_currency.upper(),
                'status': 'success',
                'source': 'fallback_rates',
                'note': 'Using approximate exchange rates'
            }
                
        except Exception as e:
            print(f"❌ Currency conversion error: {str(e)}")
            return {
                'original_amount': amount,
                'converted_amount': 'N/A',
                'rate': 'N/A',
                'from': from_currency,
                'to': to_currency,
                'status': 'error',
                'error': str(e)
            }

if __name__ == "__main__":
    import asyncio
    
    async def test_currency():
        print("🧪 Testing RapidAPI Currency Converter")
        print("=" * 50)
        
        tool = CurrencyTool()
        
        # Test cases
        test_cases = [
            (100, "USD", "EUR"),
            (50, "EUR", "USD"),
            (1000, "USD", "JPY"),
            (100, "USD", "USD"),  # Same currency
            (75, "GBP", "INR"),   # Different currencies
        ]
        
        for amount, from_cur, to_cur in test_cases:
            print(f"\n💱 Testing: {amount} {from_cur} → {to_cur}")
            result = await tool.execute(amount, from_cur, to_cur)
            print(f"   Result: {result}")
            
        print("\n🎉 Currency conversion tests completed!")
    
    asyncio.run(test_currency())
