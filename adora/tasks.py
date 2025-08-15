import json
import os
import time
from typing import Dict, List, Optional, Union

import requests
from celery import shared_task
from requests.exceptions import ConnectionError, RequestException, Timeout
from urllib3.exceptions import NameResolutionError

# from account.models import User
from adora.models import Order, OrderReceipt, TroboMerchantToken

# from adora.models import SMSCampaign, SMSCampaignSendLog
# from account.models import User


HEADERS = {"accept": "application/json", "content-type": "application/json"}


def consider_walet_balance(order: Order, currency: str = "IRT") -> int:
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
def send_zarin_payment_information(order: Order):
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
    # مرحله ۱: بررسی توکن معتبر در دیتابیس
    try:
        latest_token = TroboMerchantToken.objects.last()
        if latest_token and not latest_token.is_expired():
            return latest_token.token
    except Exception as e:
        print("⚠️ خطا در واکشی توکن از دیتابیس:", e)

    # مرحله ۲: تلاش برای دریافت توکن جدید، تا ۳ بار
    header = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("TOROBPAY_BASE64"),
    }

    data = {
        "username": os.getenv("TOROBPAY_USERNAME"),
        "password": os.getenv("TOROBPAY_PASSWORD"),
    }

    oauth_url = (
        f"{os.getenv('TOROBPAY_BASE_URL')}/{os.getenv('TOROBPAY_OAUTH_ENDPOINT')}"
    )

    for attempt in range(1, 4):  # تلاش تا ۳ بار
        try:
            print(f"🔄 تلاش {attempt} برای دریافت توکن...")
            res = requests.post(
                url=oauth_url,
                headers=header,
                data=json.dumps(data),
                timeout=10,
            )
            res.raise_for_status()
            res_dict = res.json()
            token = res_dict.get("access_token", None)

            if token:
                TroboMerchantToken.objects.create(token=token)
                print("✅ توکن جدید با موفقیت ذخیره شد.")
                return token
            else:
                print("❌ توکن در پاسخ موجود نیست:", res_dict)
                break  # اگر پاسخ نامعتبر بود، تکرار فایده ندارد

        except (ConnectionError, Timeout, RequestException) as e:
            print(f"⚠️ خطا در اتصال ({type(e).__name__}):", e)
        except Exception as e:
            print("🔥 خطای ناشناخته:", e)
            break  # برای خطای غیرقابل پیش‌بینی، ادامه نده

    print("❌ دریافت توکن پس از ۳ بار تلاش ناموفق بود.")
    return None


@shared_task
def send_torobpay_payment_information(order: Order):
    try:
        order_receipt: OrderReceipt = OrderReceipt.objects.create(
            order=order, torob_reciept=True
        )
        # print(Order)
        TorobPay_BaseUrl = os.getenv("TOROBPAY_BASE_URL")
        TorobPay_Payment_endpoint = os.getenv("TOROBPAY_PAYMENT_ENDPOINT")

        access_token = get_torobpay_access_token()
        # if type(access_token) != str:
        #     order_receipt.torob_error_message = access_token
        #     order_receipt.save()
        #     return

        print("access_token", access_token)
        header = {
            "content-type": "application/json",
            "Authorization": f"Bearer {access_token}",
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
            print("respone : ", response)
            order.torob_payment_token = response.get("paymentToken")
            order.torob_payment_page_url = response.get("paymentPageUrl")
            order.save()

        else:
            error_data = res_dict.get("errorData", {})
            error_message = (
                f"{error_data.get('errorCode', '')}\n {error_data.get('message', '')}"
            )
            print(error_message)
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

def get_request(url: str, params: dict = None, retries: int = 3) -> Optional[dict]:
    access_token = get_torobpay_access_token()
    if not access_token:
        print("Failed to retrieve access token")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    for attempt in range(retries):
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            print("Status Code:", res.status_code)
            print("Response Content:", res.text)
            print("url : ", url)


            try:
                return res.json()
            except ValueError:
                print(f"Invalid JSON response (attempt {attempt + 1}): {res.text}")
        except requests.ConnectionError as ce:
            print(f"Connection error (attempt {attempt + 1}): {ce}")
        except requests.Timeout as te:
            print(f"Timeout error (attempt {attempt + 1}): {te}")
        except requests.RequestException as e:
            print(f"Request exception (attempt {attempt + 1}): {e}")
        time.sleep(2)

    return None


def post_request(url: str, data: dict, retries: int = 3) -> Optional[dict]:
    access_token = get_torobpay_access_token()
    if not access_token:
        print("Failed to retrieve access token")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    for attempt in range(retries):
        try:
            res = requests.post(url, data=json.dumps(data), headers=headers, timeout=10)

            print("Status Code:", res.status_code)
            print("Raw Response:", res.text)
            print("url : ", url)

            try:
                response_json = res.json()
                print("Parsed JSON:", response_json)
                return response_json
            except ValueError:
                print(f"Invalid JSON response (attempt {attempt + 1}): {res.text}")
        except requests.ConnectionError as ce:
            print(f"Connection error (attempt {attempt + 1}): {ce}")
        except requests.Timeout as te:
            print(f"Timeout error (attempt {attempt + 1}): {te}")
        except requests.RequestException as e:
            print(f"Request exception (attempt {attempt + 1}): {e}")
        time.sleep(2)

    return None


def torobpay_status(order: Order):
    url = f"{os.getenv('TOROBPAY_BASE_URL')}/{os.getenv('TOROBPAY_PAYMENT_STATUS')}"
    response = get_request(url, params={"paymentToken": order.torob_payment_token})
    print(response)
    return response


def _handle_torobpay_action(order: Order, endpoint_env: str, success_status: str):
    url = f"{os.getenv('TOROBPAY_BASE_URL')}/{os.getenv(endpoint_env)}"
    response = post_request(url, {"paymentToken": order.torob_payment_token})

    order_receipt: OrderReceipt = order.receipt
    if not order_receipt:
        return None

    if response.get("successful"):
        print(f"{endpoint_env} successful")
        transaction_id = response.get("response", {}).get("transactionId", "")
        order_receipt.torob_error_message = response
        order_receipt.torob_transaction_id = transaction_id
        order_receipt.save()

        order.payment_status = success_status
        order.save()
    else:
        error_msg = str(response.get("errorData", {}))
        if not order_receipt.torob_error_message:
            order_receipt.torob_error_message = error_msg
        else:
            order_receipt.torob_error_message += error_msg
        order_receipt.save()

    return response

@shared_task
def torobpay_verify(order: Order):
    return _handle_torobpay_action(
        order, "TOROBPAY_PAYMENT_VERIFY", "TV"
    )  # Torob Verificaion

def torobpay_settle(order: Order):
    return _handle_torobpay_action(order, "TOROBPAY_PAYMENT_SETTLE", "C")  # Complete


@shared_task
def torobpay_revert(order: Order):
    return _handle_torobpay_action(
        order, "TOROBPAY_PAYMENT_REVERT", "TR"
    )  # Torob Reverted


@shared_task
def torobpay_cancel(order: Order):
    return _handle_torobpay_action(
        order, "TOROBPAY_PAYMENT_CANCEL", "TC"
    )  # Torob Canceled
