from celery import shared_task 
from django.core.cache import cache
from django.conf import settings
# import requests
import time
import requests
from requests.exceptions import RequestException, ConnectionError
from typing import Optional,Dict
from rest_framework.response import Response
import json
import hashlib
import os
import random

# url = "https://console.melipayamak.com/api/send/otp/9727696ea5804598844099615db40e27"
MELLIPAYAMK_PATTER_URL=os.environ.get("MELLIPAYAMK_PATTER_URL")
REGISTER_LOGIN_CODE = os.environ.get('REGISTER_LOGIN_CODE')

HEADERS = {
    'accept': 'application/json',
    'content-type': 'application/json'
}


@shared_task(max_retries=3)
def send_otp_to_phone(phone_number:str, request_type:str):
    print('Message is sending...')
    
    # Define headers and data for the POST request
    otp = str(random.randint(1000, 9999))
    message = [otp]
    print('otp',otp)
    print(REGISTER_LOGIN_CODE)
    data ={ 
            "bodyId": int(REGISTER_LOGIN_CODE), 
            "to": phone_number, 
            "args": message
            }
    
    try:
    # Use the retry_request function to send the OTP
        response = requests.post(MELLIPAYAMK_PATTER_URL, headers=HEADERS, data=json.dumps(data))
        # response.raise_for_status()
        # print('response.json()',response.json())
        if response and response.status_code == 200:
            phone_hash = hashlib.sha256((phone_number).encode()).hexdigest()
            cache_key =f"otp_sent_{phone_hash}"
            # res = response.json()
            # otp = res.get('code', '')
            cache.set(cache_key, {"otp":otp, "phone_number": phone_number, 'request_type': request_type}, timeout=settings.CACHE_TTL)
            print(f"Message is sent to {phone_number}")
            print("response.json()",response.json())
        else:
            print(f"Failed to send message to {phone_number}")
    except ConnectionError as ce:
        print(f"Connection error: {ce}")
        # send_otp_to_phone.apply_async((phone_number, request_type), countdown=60)
    except RequestException as re:
        print(f"Request failed: {re}")
        # send_otp_to_phone.apply_async((phone_number, request_type), countdown=60) ,
        
