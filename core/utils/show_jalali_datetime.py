from datetime import datetime
from jalali_date import datetime2jalali
from persian_tools import digits


def show_date_time(date_time: datetime) -> str:
    if date_time:
        persian_months = [
            "فروردین",
            "اردیبهشت",
            "خرداد",
            "تیر",
            "مرداد",
            "شهریور",
            "مهر",
            "آبان",
            "آذر",
            "دی",
            "بهمن",
            "اسفند",
        ]
        jalali_date = datetime2jalali(date_time)
        time = jalali_date.strftime("%H:%M:%S")
        day = jalali_date.day
        month = persian_months[jalali_date.month - 1]  # چون لیست از ایندکس 0 شروع می‌شود
        year = jalali_date.year
        return digits.convert_to_fa(f"{day} {month} {year} ({time})")
    return "-"
