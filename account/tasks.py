from decimal import Decimal
from phonenumbers import PhoneNumber
from datetime import datetime
import hashlib
import json
import os
import random
# import requests
from typing import Dict, Optional

import requests
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from requests.exceptions import ConnectionError, RequestException

from account.models import User, Profile
from adora.models import SMSCampaign, SMSCampaignSendLog

import jdatetime
from core.utils.separate_and_convert_to_fa import separate_digits_and_convert_to_fa
from core.utils.show_jalali_datetime import show_date_time
from persian_tools import digits

# url = "https://console.melipayamak.com/api/send/otp/9727696ea5804598844099615db40e27"
MELLIPAYAMK_PATTER_URL=os.environ.get("MELLIPAYAMK_PATTER_URL")
REGISTER_LOGIN_CODE = os.environ.get('REGISTER_LOGIN_CODE')

HEADERS = {
    'accept': 'application/json',
    'content-type': 'application/json'
}

print("✅ tasks.py loaded")
print("#" * 50)

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


MELLIPAYAMK_PATTER_URL = os.environ.get("MELLIPAYAMK_PATTER_URL")


def serialize_arg(arg):
    if isinstance(arg, Decimal):
        return separate_digits_and_convert_to_fa(arg)
    elif isinstance(arg, datetime):
        return show_date_time(arg)
    elif isinstance(arg, PhoneNumber):
        return digits.convert_to_fa(str(arg))  # یا: return arg.national_number برای فقط شماره داخلی
    return str(arg)


@shared_task()
def send_campaign_pattern_sms_with_mellipayamk(user_id: int, campaign_id: int):
    try:
        user = User.objects.filter(id=user_id).first()
        if not user:
            return

        campaign = SMSCampaign.objects.filter(id=campaign_id).first()
        if not campaign:
            return

        profile = Profile.objects.filter(user=user).first()
        
        # استخراج پارامترها
        args = [serialize_arg(param.resolve_value(user=user, profile=profile, campaign=campaign)) for param in campaign.params.all()]
        # args = [int(arg) if isinstance(arg, Decimal) else arg for arg in args]
        print("args", args)
        data = {
            "bodyId": int(campaign.sms_template_id),
            "to": user.phone_number_with_zero(),
            "args": args,
        }

        res = requests.post(
            MELLIPAYAMK_PATTER_URL, data=json.dumps(data), headers=HEADERS
        )

        res_json = res.json() if res.content else {}
        status_text = res_json.get("status", "")

        SMSCampaignSendLog.objects.create(
            campaign=campaign,
            user=user,
            message_args=f"{str(args)}\n\n {str(res.json())}",
            is_successful=res.status_code == 200 and status_text == "ارسال موفق بود",
            response_message=status_text,
            status_code=res.status_code,
        )

    except Exception as e:
        SMSCampaignSendLog.objects.create(
            campaign_id=campaign_id,
            user_id=user_id,
            message_args=f"{str(args)}\n\n {str(res.json())}",
            is_successful=False,
            response_message=str(e),
            status_code=0,
        )
