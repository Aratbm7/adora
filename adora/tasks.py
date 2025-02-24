from typing import List
from account.models import User
from celery import shared_task
from adora.models import Order, OrderReceipt
import requests
from requests.exceptions import ConnectionError
import json
import os
 


HEADERS = {
    'accept': 'application/json',
    'content-type': 'application/json'
}

@shared_task
def send_payment_information(order_id):
    try:
        order = Order.objects.get(id=order_id)
        merchant_id = os.environ.get('ZARIN_MERCHANT_ID')
        zarin_request_url = os.environ.get('ZARIN_REQUEST_URL')
        zarin_callback_url = os.environ.get('ZARINT_CALLBACK_URL')
        payment_data = {
            'merchant_id':merchant_id,
            'amount':int(order.total_price),
            'currency': 'IRT',
            'description':'خرید از آدورا یدک',
            'callback_url': zarin_callback_url,
            'metadata': {'mobile':str(order.receiver_phone_number).replace('+98', '0'),}
        }
        
        res = requests.post(url=zarin_request_url,
                            headers=HEADERS,
                            data=json.dumps(payment_data))
        
        res_dict = res.json()
        data = res_dict.get('data', {})
        errors = res_dict.get('errors', {})
        
        if data:
            OrderReceipt.objects.create(
                authority=data.get('authority', 'Not Found'),
                request_code=data.get('code', 0),
                request_msg=data.get('message', 'Not Found'),
                fee=data.get('fee', 0),
                order=order
                )
        if errors:
            OrderReceipt.objects.create(
                request_code=errors.get('code', 0),
                error_msg=errors.get('message', 'Not Found'),
                order=order
                )
            
    except ConnectionError:
            OrderReceipt.objects.create(
                connection_error=True,
                order=order
                )
            
    except Exception:
        print(f'There is no Order with this id = {order_id}')
        return None


MELLIPAYAMK_PATTER_URL=os.environ.get("MELLIPAYAMK_PATTER_URL")
@shared_task
def send_order_status_message(phone_number, msg_args:List, text_code:int):
    try:
        data ={ 
            "bodyId": int(text_code), 
            "to": phone_number,
            "args":msg_args 
            }
        res = requests.post(MELLIPAYAMK_PATTER_URL, data=json.dumps(data), headers=HEADERS) 
        
        print(res.json())
    except ConnectionError:
        print('Connectino error')
    except Exception:
        print('Exception error')