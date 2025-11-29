import json
import os
import time
from typing import Callable, Dict, List, Literal, Optional

import traceback
import requests
from celery import shared_task
from requests.exceptions import ConnectionError, RequestException, Timeout

# from urllib3.exceptions import NameResolutionError

# from account.models import User
from adora.models import Order, OrderReceipt, TroboMerchantToken, SnapPayAccessToken

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
    currency_value = 10 if currency == "IRT" else 1
    if not order.use_wallet_balance:
        return int(order.total_price) * currency_value

    if order.user.profile.wallet_balance >= order.total_price:
        return 0
    else:
        return (
            int(order.total_price - order.user.profile.wallet_balance) * currency_value
        )


@shared_task
def send_zarin_payment_information(order: Order):
    try:
        # order = Order.objects.get(id=order_id)
        merchant_id = os.environ.get("ZARIN_MERCHANT_ID")
        zarin_request_url = os.environ.get("ZARIN_REQUEST_URL", b"")
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
        print("order", order)

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
        print(traceback.format_exc())
        return None


def get_torobpay_access_token() -> Optional[str]:
    # مرحله ۱: بررسی توکن معتبر در دیتابیس
    try:
        print("We started.....")
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
        print(traceback.format_exc())


MELLIPAYAMK_PATTER_URL = os.environ.get("MELLIPAYAMK_PATTER_URL", b"")


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


def _choose_getaway_header(
    getway_name: Literal["snappay", "torobpay"], access_token: str
) -> dict:
    if getway_name == "torobpay":
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

    if getway_name == "snappay":
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }


def get_request(
    url: str,
    get_access_token: Callable[[], Optional[str]],
    getway_name: Literal["torobpay", "snappay"],
    params: dict = {},
    retries: int = 3,
) -> Optional[dict]:
    access_token = get_access_token()
    if not access_token:
        print("Failed to retrieve access token")
        return None

    headers = _choose_getaway_header(getway_name, access_token)

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


def post_request(
    url: str,
    data: dict,
    get_access_token: Callable[[], Optional[str]],
    getway_name: Literal["snappay", "torobpay"],
    retries: int = 3,
) -> Optional[dict]:
    access_token = get_access_token()
    if not access_token:
        print("Failed to retrieve access token")
        return None

    headers = _choose_getaway_header(getway_name, access_token)

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
    response = get_request(
        url,
        get_torobpay_access_token,
        "torobpay",
        params={"paymentToken": order.torob_payment_token},
    )
    print(response)
    return response


def snappay_status(order: Order):
    url = f"{os.getenv('SNAP_PAY_BASE_URL')}{os.getenv('SNAP_PAY_STATUS_ENDPOINT')}"
    response = get_request(
        url,
        get_snap_pay_access_token,
        "snappay",
        params={"paymentToken": order.snap_payment_token},
    )
    print(response)
    return response


def _handle_torobpay_action(order: Order, endpoint_env: str, success_status: str):
    url = f"{os.getenv('TOROBPAY_BASE_URL')}/{os.getenv(endpoint_env)}"
    response = post_request(
        url,
        {"paymentToken": order.torob_payment_token},
        get_torobpay_access_token,
        "torobpay",
    )

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


# Azkivam functions
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import time

AZKIVAM_MERCHANT_ID = os.getenv("AZKIVAM_MERCHANT_ID", "")


def azkivam_encrypted_signature(suburl: str, request_method: str, api_key: str) -> str:
    timestamp = int(time.time())
    plain_signature = f"{suburl}#{timestamp}#{request_method}#{api_key}"
    # decode key from hex
    key_bytes = binascii.unhexlify(api_key)

    # IV: 16 bytes of zeros
    iv = bytes(16)

    # create cipher
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)

    # PKCS7 padding (AES block size = 16)
    padded_data = pad(plain_signature.encode(), AES.block_size)

    # encrypt
    encrypted_bytes = cipher.encrypt(padded_data)

    # return hex string
    return binascii.hexlify(encrypted_bytes).decode()


def azkivam_header(suburl: str, request_method: str, merchant_id: str) -> Dict:
    api_key = os.getenv("AZKIVAM_API_KEY", "")
    print(api_key, "api_key")
    return {
        "content-type": "application/json",
        "MerchantId": merchant_id,
        "Signature": azkivam_encrypted_signature(suburl, request_method, api_key),
    }


AZKIVAM_PROVIDED_ID = os.getenv("AZKIVAM_PROVIDED_ID", "")
AZKIVAM_BASE_URL = os.getenv("AZKIVAM_BASE_URL", "")


def azkivam_send_create_ticket_request(order: Order):
    try:
        order_receipt = OrderReceipt.objects.create(order=order, azkivam_reciept=True)

        suburl = os.getenv("AZKIVAM_CREATE_TICKET", "")

        body_data = {
            "amount": consider_walet_balance(order),
            "redirect_uri": "https://adorayadak.ir/a_redirect_uri",
            "fallback_uri": "https://adorayadak.ir/a_fallback_uri",
            "provider_id": AZKIVAM_PROVIDED_ID,
            "mobile_number": str(order.user.phone_number).replace("+98", "0"),
            "merchant_id": AZKIVAM_MERCHANT_ID,
            "items": [
                {
                    "name": item.product.fa_name,
                    "count": item.quantity,
                    "amount": item.sold_price * 10,
                    "url": f"https://adorayadak.ir/adp-{item.id}/{item.product.fa_name.strip().replace(' ', '-')}",
                }
                for item in order.order_items.all()
            ],
        }

        # افزودن هزینه ارسال (در صورت وجود)
        delivery_cost = getattr(order, "delivery_cost", None)
        if delivery_cost:
            body_data["items"].append(
                {
                    "name": "هزینه ارسال و بسته بندی",
                    "count": 1,
                    "amount": int(delivery_cost) * 10,
                    "url": "https://adorayadak.ir/checkout",
                }
            )

        # ارسال درخواست به آذکی‌وام
        res = requests.post(
            url=f"{AZKIVAM_BASE_URL}/{suburl}",
            headers=azkivam_header(suburl, "POST", AZKIVAM_MERCHANT_ID),
            data=json.dumps(body_data),
            timeout=30,  # ✅ اضافه‌شده برای جلوگیری از هنگ در صورت قطع اتصال
        )

        print(f"Azkivam response status: {res.status_code}")

        # پردازش پاسخ
        if res.status_code == 200:
            res_dict = res.json()
            print("Azkivam Ticket created successfully")

            response = res_dict.get("result", {})
            print("Response:", response)

            order.azkivam_payment_token = response.get("ticket_id")
            order.azkivam_payment_page_url = response.get("payment_uri")
            order.save()

        else:
            # در صورت خطا از سمت آذکی‌وام
            try:
                res_dict = res.json()
            except Exception:
                res_dict = {"error": res.text}

            error_message = str(res_dict)
            print("Azkivam error:", error_message)

            order_receipt.azkivam_error_message = error_message
            order_receipt.save()

    except ConnectionError as e:
        print("ConnectionError:", e)
        order_receipt.azkivam_error_message = str(e)
        order_receipt.save()

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        order_receipt.azkivam_error_message = tb
        order_receipt.save()


AZKI_CODES = {
    0: "Request finished successfully",
    1: "Internal Server Error",
    2: "Resource Not Found",
    4: "Malformed Data",
    5: "Data Not Found",
    15: "Access Denied",
    16: "Transaction already reversed",
    17: "Ticket Expired",
    18: "Signature Invalid",
    19: "Ticket unpayable",
    20: "Ticket customer mismatch",
    21: "Insufficient Credit",
    28: "Unverifiable ticket due to status",
    32: "Invalid Invoice Data",
    33: "Contract is not started",
    34: "Contract is expired",
    44: "Validation exception",
    51: "Request data is not valid",
    59: "Transaction not reversible",
    60: "Transaction must be in verified state",
}


def _handle_azkivam_action(
    order: Order,
    suburl_env_name: str,
    success_status: str = "",
    provide_id: bool = False,
):
    suburl = os.getenv(suburl_env_name, "")
    url = f"{os.getenv('AZKIVAM_BASE_URL')}{suburl}"
    for attempt in range(3):
        try:
            order_receipt: OrderReceipt = order.receipt
            if not order_receipt:
                print("Error is from Heeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeer")
                return None

            data = (
                {
                    "ticket_id": order.azkivam_payment_token,
                    "provider_id": AZKIVAM_PROVIDED_ID,
                }
                if provide_id
                else {"ticket_id": order.azkivam_payment_token}
            )
            print("dataaaaaaaaaaaaaa", data)
            res = requests.post(
                url,
                data=json.dumps(data),
                headers=azkivam_header(suburl, "POST", AZKIVAM_MERCHANT_ID),
                timeout=10,
            )
            res_dict = {}
            if res.status_code == 200:
                res_dict = res.json()
                order_receipt.azkivam_error_message = res_dict
                order_receipt.save()

                if success_status:
                    order.payment_status = success_status
                    order.save()
            else:
                error_msg = res.json()
                if not order_receipt.azkivam_error_message:
                    order_receipt.azkivam_error_message = str(error_msg)
                else:
                    order_receipt.azkivam_error_message += str(error_msg)
                order_receipt.save()

            print("Status Code:", res.status_code)
            print("Raw Response:", res.text)
            print("url : ", url)

        except ValueError:
            print(f"Invalid JSON response (attempt {attempt + 1}): {res.text}")
        except requests.ConnectionError as ce:
            print(f"Connection error (attempt {attempt + 1}): {ce}")
        except requests.Timeout as te:
            print(f"Timeout error (attempt {attempt + 1}): {te}")
        except requests.RequestException as e:
            print(f"Request exception (attempt {attempt + 1}): {e}")
            time.sleep(2)
    return res


def _format_azki_response(res):
    """اضافه کردن متن کد به خروجی اصلی"""
    data = res.json()
    rs_code = data.get("rsCode")
    data["rsCode_message"] = AZKI_CODES.get(rs_code, "Unknown Code")
    return data


def azkivam_verify(order: Order):
    res = _handle_azkivam_action(order, "AZKIVAM_VERIFY_TICKET", success_status="AV")
    if res is None:
        return None
    return _format_azki_response(res)


def azkivam_cancel(order: Order):
    res = _handle_azkivam_action(order, "AZKIVAM_CANCEL_TICKET", success_status="AC")
    if res is None:
        return None
    return _format_azki_response(res)


def azkivam_reverse(order: Order):
    res = _handle_azkivam_action(
        order, "AZKIVAM_REVERSE_TICKET", success_status="AR", provide_id=True
    )
    if res is None:
        return None
    return _format_azki_response(res)


def azkivam_status(order: Order):
    res = _handle_azkivam_action(order, "AZKIVAM_STATUS_TICKET")
    if res is None:
        return None
    return _format_azki_response(res)


SNAP_PAY_BASE64 = os.getenv("SNAP_PAY_BASE64_TOKEN")
SNAP_PAY_USERNAME = os.getenv("SNAP_PAY_USERNAME")
SNAP_PAY_PASSWORD = os.getenv("SNAP_PAY_PASSWORD")
SNAP_PAY_BASE_URL = os.getenv("SNAP_PAY_BASE_URL")


from urllib.parse import urljoin


def get_snap_pay_access_token() -> Optional[str]:
    try:
        latest_token = SnapPayAccessToken.objects.last()
        if latest_token and not latest_token.is_expired():
            return latest_token.token
    except Exception as e:
        print("⚠️ خطا در واکشی توکن از دیتابیس:", e)

    # دریافت توکن جدید
    print("🌀 دریافت توکن جدید از SnappPay...")

    header = {
        "Authorization": f"Basic {os.getenv('SNAP_PAY_BASE64_TOKEN')}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "password",
        "scope": "online-merchant",
        "username": os.getenv("SNAP_PAY_USER_NAME"),
        "password": os.getenv("SNAP_PAY_PASSWORD"),
    }

    oauth_url = urljoin(
        os.getenv("SNAP_PAY_BASE_URL"), os.getenv("SNAP_PAY_JWT_ENDPOINT")
    )
    print("🔗 درخواست توکن به:", oauth_url)

    for attempt in range(1, 4):
        try:
            print(f"🔄 تلاش {attempt} برای دریافت توکن...")
            res = requests.post(url=oauth_url, headers=header, data=data, timeout=10)
            print("Response status:", res.status_code)
            print("Response text:", res.text)

            if res.status_code == 200:
                res_dict = res.json()
                token = res_dict.get("access_token")
                if token:
                    SnapPayAccessToken.objects.create(token=token)
                    print("✅ توکن جدید ذخیره شد.")
                    return token
                else:
                    print("❌ access_token در پاسخ موجود نیست.")
                    break
            else:
                print("❌ پاسخ نامعتبر:", res.status_code)
        except Exception as e:
            print("🔥 خطای ناشناخته:", e)
            break

    print("❌ دریافت توکن پس از ۳ بار تلاش ناموفق بود.")
    return None


@shared_task
def send_snap_payment_information(order: Order):
    try:
        order_receipt: OrderReceipt = OrderReceipt.objects.create(
            order=order, snap_reciept=True
        )
        # print(Order)
        snap_base_url = os.getenv("SNAP_PAY_BASE_URL")
        snap_payment_endpoint = os.getenv("SNAP_PAY_PAYMENT_ENDPOINT")

        access_token = get_snap_pay_access_token()
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
            "amount": consider_walet_balance(order),
            "discountAmount": 0,
            "externalSourceAmount": int(order.user.profile.wallet_balance * 10) if order.use_wallet_balance else 0,
            "mobile": str(order.user.phone_number),
            "paymentMethodTypeDto": "INSTALLMENT",
            "returnURL": "https://api.adorayadak.ir/snappay-callback/",
            "transactionId": order.tracking_number,
            "cartList": [
                {
                    "cartId": order.id,
                    "totalAmount": int(order.total_price) * 10,
                    "isShipmentIncluded": True if order.delivery_cost else False,
                    "shippingAmount": int(order.delivery_cost) * 10,
                    "isTaxIncluded": True,
                    "taxAmount": 0,
                    "cartItems": list(
                        map(
                            lambda item: {
                                "id": item.id,
                                "amount": item.sold_price * 10,
                                "category": "ابزار و یدک خودرو",
                                "count": item.quantity,
                                "name": item.product.fa_name,
                                "commissionType": 100,
                            },
                            order.order_items.all(),
                        )
                    ),
                }
            ],
        }

        print(payment_data)

        url = f"{snap_base_url}{snap_payment_endpoint}"
        print("urllllllllllllllllllL", url)
        res = requests.post(
            url=url,
            headers=header,
            data=json.dumps(payment_data),
        )
        res_dict = res.json()

        if res_dict.get("successful", False):
            print(f"Payment Token successfully is taked")
            response = res_dict.get("response", {})
            print("respone : ", response)
            order.snap_payment_token = response.get("paymentToken")
            order.snap_payment_page_url = response.get("paymentPageUrl")
            order.save()

        else:
            error_data = res_dict.get("errorData", {})
            error_message = (
                f"{error_data.get('errorCode', '')}\n {error_data.get('message', '')}"
            )
            print(error_message)
            order_receipt.snap_error_message = error_message
            order_receipt.save()

        print(res_dict)
    except ConnectionError as e:
        print(f"There is a problem to connecct to Torob Pay to get payment token ")
        print(e)
        order_receipt.snap_error_message = str(e)
        order_receipt.save()

    except Exception as e:
        print(f"There is some error on get access token function from Torob Pay")
        print(traceback.format_exc())

def _handle_snap_action(order: Order, endpoint_env: str, success_status: str, data={}):
    url = f"{os.getenv('SNAP_PAY_BASE_URL')}{os.getenv(endpoint_env)}"
    response = post_request(
        url,
        {"paymentToken": order.snap_payment_token},
        get_snap_pay_access_token,
        "snappay",
    )

    order_receipt: OrderReceipt = order.receipt
    if not order_receipt:
        return None

    if response.get("successful"):
        print(f"{endpoint_env} successful")
        transaction_id = response.get("response", {}).get("transactionId", "")
        order_receipt.snap_error_message = response
        order_receipt.snap_transaction_id = transaction_id
        order_receipt.save()

        order.payment_status = success_status
        order.save()
    else:
        error_msg = str(response.get("errorData", {}))
        if not order_receipt.snap_error_message:
            order_receipt.snap_error_message = error_msg
        else:
            order_receipt.snap_error_message += error_msg
        order_receipt.save()

    return response


@shared_task
def snappay_verify(order: Order):
    return _handle_snap_action(
        order, "SNAP_PAY_VERIFY_ENDPOINT", "SV"
    )  # Snap Verificaion


def snappay_settle(order: Order):
    return _handle_snap_action(order, "SNAP_PAY_SETTLE_ENDPOINT", "C")  # Complete


@shared_task
def snappay_revert(order: Order):
    return _handle_snap_action(order, "SNAP_PAY_REVERT_ENDPOINT", "SR")  # Snap Reverted


@shared_task
def snappay_cancel(order: Order):
    return _handle_snap_action(order, "SNAP_PAY_CANCEL_ENDPOINT", "SC")  # Snap Canceled

