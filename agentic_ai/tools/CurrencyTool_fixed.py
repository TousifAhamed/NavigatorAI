from typing import Dict
from abc import ABC, abstractmethod
import time

# Try to import currency_converter, fallback to manual rates if not available
try:
    from currency_converter import CurrencyConverter
    CURRENCY_CONVERTER_AVAILABLE = True
except ImportError:
    CURRENCY_CONVERTER_AVAILABLE = False
    print("⚠️ currency_converter not available, using fallback rates")


class BaseTravelTool(ABC):
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        
    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass

class CurrencyTool(BaseTravelTool):
    def __init__(self):
        super().__init__()
        if CURRENCY_CONVERTER_AVAILABLE:
            try:
                self.converter = CurrencyConverter()
            except Exception:
                self.converter = None
                print("⚠️ CurrencyConverter initialization failed, using fallback")
        else:
            self.converter = None
            
        # Fallback exchange rates (approximate)
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
        }
        
    async def execute(self, amount: float, from_currency: str, to_currency: str) -> Dict:
        """
        Convert currency using CurrencyConverter or fallback rates.
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
                    'status': 'success'
                }
            
            if self.converter:
                # Use currency_converter library
                try:
                    converted = self.converter.convert(amount, from_currency, to_currency)
                    rate = self.converter.convert(1, from_currency, to_currency)
                    
                    return {
                        'original_amount': amount,
                        'converted_amount': round(converted, 2),
                        'rate': round(rate, 4),
                        'from': from_currency.upper(),
                        'to': to_currency.upper(),
                        'status': 'success',
                        'source': 'currency_converter'
                    }
                except Exception as e:
                    print(f"CurrencyConverter failed: {e}, using fallback")
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
                'rate': round(rate, 4),
                'from': from_currency.upper(),
                'to': to_currency.upper(),
                'status': 'success',
                'source': 'fallback_rates',
                'note': 'Using approximate exchange rates'
            }
                
        except ValueError as e:
            print(f"Currency conversion error: {str(e)}")
            return {
                'original_amount': amount,
                'converted_amount': 'N/A',
                'rate': 'N/A',
                'from': from_currency,
                'to': to_currency,
                'status': 'error',
                'error': str(e)
            }
        except Exception as e:
            print(f"Unexpected currency conversion error: {str(e)}")
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
        tool = CurrencyTool()
        
        # Test cases
        test_cases = [
            (100, "USD", "EUR"),
            (50, "EUR", "USD"),
            (1000, "USD", "JPY"),
            (100, "USD", "USD"),  # Same currency
            (100, "XYZ", "ABC"),  # Unknown currencies
        ]
        
        for amount, from_cur, to_cur in test_cases:
            result = await tool.execute(amount, from_cur, to_cur)
            print(f"{amount} {from_cur} -> {to_cur}: {result}")
    
    asyncio.run(test_currency())
