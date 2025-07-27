import json
import os
import re
from typing import List, Dict, Optional, Union

import requests
from celery import shared_task
from requests.exceptions import ConnectionError
from urllib3.exceptions import NameResolutionError
# from adora.models import SMSCampaign, SMSCampaignSendLog
# from account.models import User

# from account.models import User
from adora.models import Order, OrderReceipt


HEADERS = {"accept": "application/json", "content-type": "application/json"}


def consider_walet_balance(order: Order, currency: str = "IRT") ->  int:
    """
    This function checks if the user has a wallet balance and want to use it then returns the amount to be paid after deducting the wallet balance.
    If the wallet balance is greater than or equal to the total price, it returns 0.
    
    This function returnt Rial currency amount.
    If the user does not want to use wallet balance, it returns the total price multiplied by 10 (to convert to Rial).
    If the user has a wallet balance but it is less than the total price, it returns the total price minus the wallet balance.
    
    args:
        - currency [IRI, TOMAN]. default=IRI
    """
    currency = 10 if currency == "IRT" else 1
    if not order.use_wallet_balance:
        return int(order.total_price * currency)
    
    if order.user.profile.wallet_balance >= order.total_price:
        return 0
    else:
        return int(order.total_price - order.user.profile.wallet_balance) * currency


@shared_task
def send_zarin_payment_information(order:Order):
    try:
        # order = Order.objects.get(id=order_id)
        merchant_id = os.environ.get("ZARIN_MERCHANT_ID")
        zarin_request_url = os.environ.get("ZARIN_REQUEST_URL")
        zarin_callback_url = os.environ.get("ZARINT_CALLBACK_URL")
        payment_data = {
            "merchant_id": merchant_id,
            "amount": consider_walet_balance(order, "TOMAN"),
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
            "mobile": str(order.user.phone_number).replace("+98", "0"),
            "amount": consider_walet_balance(order),
            "paymentMethodTypeDto": "CREDIT_ONLINE",
            "returnURL": os.getenv("TOROBPAY_RETURN_TO_THIS_URL"),
            "transactionId": order.tracking_number,
            "cartList": [
                {
                    "cartId": order.tracking_number,
                    "totalAmount": consider_walet_balance(order),
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
        order_receipt.torob_error_message = str(e)
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
