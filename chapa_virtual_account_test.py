import requests
import json
import environ, os
from django.conf import settings

env = environ.Env()
BASE_DIR = settings.BASE_DIR
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

CHAPA_SECRET_KEY = env('CHAPA_SECRET_KEY')

# Chapa virtual account creation endpoint
url = "https://api.chapa.co/v1/virtual-account"


payload = {
    "account_name": "Freelancer Test",
    "initial_deposit": 200,
    "account_alias": "FT_01"
}

headers = {
    'Authorization': f'Bearer {CHAPA_SECRET_KEY}',
    'Content-Type': 'application/json'
}

response = requests.get(url, headers=headers, data=json.dumps(payload))

print("Status Code:", response.status_code)
print("Response:", response.text)
