import json
import os
import re
from typing import List, Dict, Optional, Union

import requests
from celery import shared_task
from requests.exceptions import ConnectionError

from account.models import User
from adora.models import Order, OrderReceipt

HEADERS = {"accept": "application/json", "content-type": "application/json"}


@shared_task
def send_zarin_payment_information(order:Order):
    try:
        # order = Order.objects.get(id=order_id)
        merchant_id = os.environ.get("ZARIN_MERCHANT_ID")
        zarin_request_url = os.environ.get("ZARIN_REQUEST_URL")
        zarin_callback_url = os.environ.get("ZARINT_CALLBACK_URL")
        payment_data = {
            "merchant_id": merchant_id,
            "amount": int(order.total_price),
            "currency": "IRT",
            "description": "خرید از آدورا یدک",
            "callback_url": zarin_callback_url,
            "metadata": {
                "mobile": str(order.receiver_phone_number).replace("+98", "0"),
            },
        }

        res = requests.post(
            url=zarin_request_url, headers=HEADERS, data=json.dumps(payment_data)
        )

        res_dict = res.json()
        data = res_dict.get("data", {})
        errors = res_dict.get("errors", {})

        if data:
            OrderReceipt.objects.create(
                authority=data.get("authority", "Not Found"),
                request_code=data.get("code", 0),
                request_msg=data.get("message", "Not Found"),
                fee=data.get("fee", 0),
                order=order,
            )
        if errors:
            OrderReceipt.objects.create(
                request_code=errors.get("code", 0),
                error_msg=errors.get("message", "Not Found"),
                order=order,
            )

    except ConnectionError as e:
        print(e)
        OrderReceipt.objects.create(connection_error=True, order=order)
        

    except Exception as e:
        print(e)
        return None


# [
# {
# "cart_id": str,
# "total_amount": int,
# "tax_amount": int,
# "shipping_amount": int,
# "is_tax_included": bool,
# "is_shipment_included": bool,
# "cartItems": [
# {
# "item_id": str,
# "name": str,
# "count": int,
# "amount": int,
# "category": str,
# "comission_type": str
# }
# ]
# }
# ]


def get_torobpay_access_token() -> Optional[str]: 
    try:
        header = {
            "Content-Type": "application/json",
            "Authorization": os.getenv("TOROBPAY_BASE64"),
        }

        data = {
            "username": os.getenv("TOROBPAY_USERNAME"),
            "password": os.getenv("TOROBPAY_PASSWORD"),
        }

        aouth_url = f"{os.getenv('TOROBPAY_BASE_URL')}/{os.getenv('TOROBPAY_OAUTH_ENDPOINT')}"

        res = requests.post(
            url=aouth_url,
            headers=header,
            data=json.dumps(data),
        )
        res_dict = res.json()
        print("res_dict", res_dict)

        return res_dict.get("access_token", None)

    except ConnectionError as e:
        print(f"There is a problem to connecct to Torob Pay to get access token \n {aouth_url}")
        print(e)
        # return e
        
        
    except Exception as e:
        print(f"There is some error on get access token function from Torob Pay")
        print(e)
        # return e


@shared_task
def send_torobpay_payment_information(order: Order, torob_access_token:str):
    try:
        order_receipt: OrderReceipt = OrderReceipt.objects.create(order=order, torob_reciept=True)
        # print(Order)
        TorobPay_BaseUrl = os.getenv("TOROBPAY_BASE_URL")
        TorobPay_Payment_endpoint = os.getenv("TOROBPAY_PAYMENT_ENDPOINT")

        access_token = torob_access_token
        # if type(access_token) != str:
        #     order_receipt.torob_error_message = access_token
        #     order_receipt.save()
        #     return

        print("access_token", access_token)
        header = {
            "content-type": "application/json",
            "Authorization": f"Bearer {access_token}"
                }

        payment_data = {
            "amount": int(order.total_price) * 10,
            "paymentMethodTypeDto": "CREDIT_ONLINE",
            "returnURL": os.getenv("TOROBPAY_RETURN_TO_THIS_URL"),
            "transactionId": order.tracking_number,
            "cartList": [
                {
                    "cartId": order.tracking_number,
                    "totalAmount": int(order.total_price) * 10,
                    # "tax_amount": order.receipt.fee if order.receipt else 0,
                    "shippingAmount": int(order.delivery_cost) * 10,
                    "isTaxIncluded": bool(os.getenv("TOROBPAY_IS_TAX_INCLUDE")),
                    "isShipmentInclude": True if order.delivery_cost else False,
                    "cartItems": list(
                        map(
                            lambda item: {
                                "id": str(item.id),
                                "name": item.product.fa_name,
                                "count": item.quantity,
                                "category": "قطعات خودرو",
                                "amount": item.sold_price * 10,
                                # "comission_type"
                            },
                            order.order_items.all(),
                        )
                    ),
                }
            ],
        }

        print(payment_data)

        res = requests.post(
            url=f"{TorobPay_BaseUrl}/{TorobPay_Payment_endpoint}",
            headers=header,
            data=json.dumps(payment_data),
        )
        res_dict = res.json()

        if res_dict.get("successful", False):
            print(f"Payment Token successfully is taked")
            response = res_dict.get("response", {})
            print("respone : ",response)
            order.torob_payment_token = response.get("paymentToken")
            order.torob_payment_page_url = response.get("paymentPageUrl")
            order.save()

        else:
            error_data = res_dict.get("errorData", {})
            error_message =   f"{error_data.get('errorCode', '')}\n {error_data.get('message', '')}"
            print(
             error_message
            )
            order_receipt.torob_error_message = error_message
            order_receipt.save()

        print(res_dict)
    except ConnectionError as e:
        print(f"There is a problem to connecct to Torob Pay to get payment token ")
        print(e)
        order_receipt = str(e)
        order_receipt.save()

    except Exception as e:
        print(f"There is some error on get access token function from Torob Pay")
        print(e)


MELLIPAYAMK_PATTER_URL = os.environ.get("MELLIPAYAMK_PATTER_URL")


@shared_task
def send_order_status_message(phone_number, msg_args: List, text_code: int):
    try:
        data = {"bodyId": int(text_code), "to": phone_number, "args": msg_args}
        res = requests.post(
            MELLIPAYAMK_PATTER_URL, data=json.dumps(data), headers=HEADERS
        )

        print(res.json())
    except ConnectionError:
        print("Connectino error")
    except Exception:
        print("Exception error")
