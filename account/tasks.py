from celery import shared_task 
# import requests
import time


@shared_task
def send_otp_to_phone(phone_number, otp):
    print('message is sending')
    time.sleep(2)
    print(f"message is sent to {phone_number}, {otp}")