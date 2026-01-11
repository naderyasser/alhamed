import requests
import os

BOSTA_API_KEY = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6InRHOU9wVE5YRzVXTDdnZkQyUXpRZCIsInJvbGVzIjpbIkJVU0lORVNTX0FETUlOIl0sImJ1c2luZXNzQWRtaW5JbmZvIjp7ImJ1c2luZXNzSWQiOiJEZGcwSHlGYnJBakVvSERsMFltR1kiLCJidXNpbmVzc05hbWUiOiJPcmZlIn0sImNvdW50cnkiOnsiX2lkIjoiNjBlNDQ4MmM3Y2I3ZDRiYzQ4NDljNGQ1IiwibmFtZSI6IkVneXB0IiwibmFtZUFyIjoi2YXYtdixIiwiY29kZSI6IkVHIn0sImVtYWlsIjoicHc5MTk5NDEzMi5vZmZpY2VAZ21haWwuY29tIiwicGhvbmUiOiIrMjAxMDY5MzI0ODk1IiwiZ3JvdXAiOnsiX2lkIjoiWGFxbENGQSIsIm5hbWUiOiJCVVNJTkVTU19GVUxMX0FDQ0VTUyIsImNvZGUiOjExNX0sInRva2VuVHlwZSI6IkFDQ0VTUyIsInNlc3Npb25JZCI6IjAxSkswN0tCODM2M0FWSkNWSjE0QTdLUTVUIiwiaWF0IjoxNzM4Mzk1OTg3LCJleHAiOjE3Mzk2MDU1ODd9.J2YA8D82gkMdTY_2SQ0JuCur7a97YAw33hKx8IPym1Y"
BASE_URL = "https://app.bosta.co/api/v2"

class BostaService:
      def __init__(self):
            if not BOSTA_API_KEY:
                  raise ValueError("BOSTA_API_KEY environment variable not set")
            self.api_key = BOSTA_API_KEY
            self.base_url = BASE_URL

      def get_cities(self):
            url = f"{self.base_url}/cities?countryId=60e4482c7cb7d4bc4849c4d5"
            headers = {"Authorization": self.api_key}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get('data', {}).get('list', [])

      def get_zones(self, city_id):
            url = f"{self.base_url}/cities/{city_id}/zones"
            headers = {"Authorization": self.api_key}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get('data', [])

      def get_districts(self, city_id):
            url = f"{self.base_url}/cities/{city_id}/districts"
            headers = {"Authorization": self.api_key}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get('data', [])
      
      def get_shipping_fees(self, cod: float, dropoff_city: str, pickup_city: str, 
                         package_size: str = 'Normal', delivery_type: str = 'SEND'):
        """
        حساب تكاليف الشحن باستخدام Bosta API
        
        :param cod: قيمة الدفع عند الاستلام
        :param dropoff_city: مدينة التسليم
        :param pickup_city: مدينة الاستلام
        :param package_size: حجم الطرد (Normal, Light Bulky, Heavy Bulky)
        :param delivery_type: نوع التسليم (SEND, CASH_COLLECTION, etc.)
        :return: تكلفة الشحن
        """
        url = f"{self.base_url}/pricing/shipment/calculator"
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
        
        params = {
            "cod": cod,
            "dropOffCity": dropoff_city,
            "pickupCity": "Alexandria",
            "size": "Normal",
            "type": "SEND"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('success', False):
                raise ValueError(f"API Error: {data.get('message', 'Unknown error')}")
                
            return data.get('priceAfterVat', 0)
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {str(e)}")
            raise
        except ValueError as e:
            print(f"API Error: {str(e)}")
            raise

      def create_delivery(self, order_data):
            url = f"{self.base_url}/deliveries"
            headers = {
                  "Authorization": self.api_key,
                  "Content-Type": "application/json"
            }
            
            payload = {
                  "type": 10,
                  "specs": {
                        "size": order_data['package_size'],
                        "packageType": order_data['package_type']
                  },
                  "cod": order_data['cod_amount'],
                  "dropOffAddress": {
                        "city": order_data['city'],
                        "zoneId": order_data['zone_id'],
                        "districtId": order_data['district_id'],
                        "firstLine": order_data['address'],
                        "isWorkAddress": False
                  },
                  "businessReference": order_data['business_reference'],
                  "receiver": {
                        "firstName": order_data['first_name'],
                        "phone": order_data['phone']
                  }
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json().get('data', {}).get('trackingNumber', None)