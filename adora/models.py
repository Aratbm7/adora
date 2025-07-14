import random
import string
from importlib.util import module_from_spec

from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _

# from django.contrib.auth import get_user_model
from phonenumber_field.modelfields import PhoneNumberField

# Create your models here.
class Date(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_date = models.DateTimeField(auto_now=True, verbose_name="تاریخ آپدیت")

    class Meta:
        verbose_name = _("دسته بندی")
        verbose_name_plural = _("دسته بندی کل")

    class Meta:
        abstract = True


class Category(Date):
    name = models.CharField(max_length=500, verbose_name="نام")
    image = models.URLField(max_length=500, verbose_name=_("لینک عکس دسته بندی"))
    alt = models.CharField(
        null=True, blank=True, max_length=500, verbose_name="نام عکس"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="دسته بندی مادر",
    )

    def get_hierarchy(self) -> list:
        """Returns the full category hierarchy from top-level to this category."""
        hierarchy = []
        category = self
        while category:
            hierarchy.insert(0, {
                'id': category.id,
                'name': category.name,
            })
            category = category.parent
            
        for index, item in enumerate(hierarchy):
            item['category_level'] = index + 1
 
 
        return hierarchy
    class Meta:
        verbose_name = _("دسته بندی")
        verbose_name_plural = _("دسته بندی کل")

    def __str__(self) -> str:
        return self.name

    def get_level(self):
        """Returns the level of the category based on the parent hierarchy."""
        if self.parent is None:
            return 1
        elif self.parent.parent is None:
            return 2
        else:
            return 3

    def get_descendants(self):
        descendants = []
        children = self.children.all()
        for child in children:
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants


class Car(Date):
    fa_name = models.CharField(max_length=100, verbose_name=_("نام فارسی"))
    image = models.URLField(
        max_length=500, null=True, blank=True, verbose_name=_("عکس ماشین")
    )
    alt = models.CharField(
        null=True, blank=True, max_length=500, verbose_name="نام عکس"
    )

    class Meta:
        verbose_name = _("خودرو")
        verbose_name_plural = _(" خودرو ها")

    def __str__(self) -> str:
        return self.fa_name


class Brand(Date):
    name = models.CharField(max_length=100, verbose_name=_("نام"))
    image = models.URLField(
        null=True, blank=True, max_length=500, verbose_name=_("لینک عکس برند")
    )
    alt = models.CharField(
        null=True, blank=True, max_length=500, verbose_name="نام عکس"
    )
    abbreviation = models.CharField(
        null=True, blank=True, max_length=100, verbose_name="مخفف"
    )

    class Meta:
        verbose_name = _("برند")
        verbose_name_plural = _(" برند ها")

    def __str__(self) -> str:
        return self.name


class Matrial(Date):
    material_name = models.CharField(max_length=500, verbose_name=_("دسته بندی جز"))

    class Meta:
        verbose_name = _("دسته بندی جز")
        verbose_name_plural = _("دسته بندی های جز")

    def __str__(self) -> str:
        return self.material_name


class ProductImage(Date):
    alt = models.CharField(
        null=True, blank=True, max_length=500, verbose_name="نام عکس"
    )
    image_url = models.URLField(max_length=500, verbose_name=_("لینک محصول"))
    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("محصول"),
    )

    class Meta:
        verbose_name = _(" عکس محصول")
        verbose_name_plural = _("عکس های محصول")

    def __str__(self) -> str:
        if self.alt:
            return self.alt

        return str(self.id)


class FAQ(models.Model):
    question = models.CharField(max_length=1000, verbose_name="سوال")
    answer = models.TextField(verbose_name="پاسخ")
    is_global = models.BooleanField(default=False, verbose_name="مشترک بین همه محصولات")

    def __str__(self):
        return f"{self.question[:20]} ..."
    
    class Meta:
        verbose_name = _("پرسش محصولات")
        verbose_name_plural = _("پرسش های محصولات")


class Product(Date):
    custom_id = models.PositiveBigIntegerField(
        default=0, unique=True, verbose_name=_("شناسه محصول")
    )
    fa_name = models.CharField(max_length=500, verbose_name="نام فارسی")
    en_name = models.CharField(max_length=500, verbose_name="نام انگلیسی")
    price = models.PositiveBigIntegerField(verbose_name="قیمت محصول")
    price_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name=" درصد تخفیف قیمت"
    )
    wallet_discount = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="درصد تخفیف پاداش محصول"
    )
    count = models.IntegerField(default=0, verbose_name="تعداد موجودی")
    install_location = models.CharField(
        max_length=500, null=True, blank=True, verbose_name="محل نصب"
    )
    count_in_box = models.IntegerField(default=0, verbose_name="تعداد در جعبه")
    guarantee = models.CharField(
        max_length=500, null=True, blank=True, verbose_name="گارانتی"
    )
    guarantee_duration = models.IntegerField(
        default=0,
        verbose_name="مدت زمان گارانتی",
        help_text=_("مدت زمان به ماه وارد شود"),
    )
    new = models.BooleanField(default=False, verbose_name="محصول جدید")
    
    SIZE_MINI = "1"
    SIZE_SMALL = "2"
    SIZE_MEDIUM = "3"
    SIZE_LARGE = "4"
    
    
    SIZE_CHOICES = [
        (SIZE_MINI, _("مینی")),
        (SIZE_SMALL, _("کوچک")),
        (SIZE_MEDIUM,_("معمولی")),
        (SIZE_LARGE, _("بزرگ")),
    ]

    size = models.CharField(
        max_length=1, 
        choices=SIZE_CHOICES, 
        default=SIZE_MINI, 
        verbose_name="سایز"
    )
    
    buyer = models.PositiveIntegerField(default=0, verbose_name=_("تعداد خریدار"))
    customer_point = models.PositiveIntegerField(
        default=0, verbose_name=_("درصد رضایت خریداران")
    )
    title_description = models.TextField(
        null=True, blank=True, verbose_name=_("توضیحات معرفی محصول")
    )
    packing_description = models.TextField(
        null=True, blank=True, verbose_name=_("توضیحات بسته بندی محصول")
    )
    shopping_description = models.TextField(
        null=True, blank=True, verbose_name=_("توضیحات خرید محصول")
    )
    best_seller = models.BooleanField(default=False, verbose_name=_("پر فروش"))

    faqs = models.JSONField()
    # Relationship fields
    material = models.ForeignKey(
        Matrial,
        related_name="products",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="جنس محصول",
    )
    category = models.ForeignKey(
        Category,
        related_name="products",
        on_delete=models.CASCADE,
        verbose_name="دسته بندی",
    )
    brand = models.ForeignKey(
        Brand,
        null=True,
        related_name="products",
        on_delete=models.SET_NULL,
        verbose_name=_("شرکت سازنده"),
    )
    similar_products = models.ManyToManyField(
        "self", blank=True, symmetrical=False, verbose_name="محصولات مشابه"
    )
    compatible_cars = models.ManyToManyField(
        Car, blank=True, related_name="products", verbose_name=_("مناسب خودرو های")
    )
    
    faqs = models.ManyToManyField(FAQ, blank=True, verbose_name="سوالات متداول اختصاصی")


    def get_all_faqs(self):
        """
        دریافت تمام سوالات (هم سوالات اختصاصی این محصول و هم سوالات عمومی)
        """
        global_faqs = FAQ.objects.filter(is_global=True)
        product_faqs = self.faqs.all()
        return global_faqs | product_faqs  # ترکیب سوالات اختصاصی و عمومی

    class Meta:
        verbose_name = _("محصول")
        verbose_name_plural = _("محصولات")

    def __str__(self):
        return self.fa_name


class Order(Date):
    NO_ANY_ACTION = "N"
    PENDING_STATUS = "P"
    PAYMENT_STATUS_COMPLETE = "C"
    PAYMENT_STATUS_FAILED = "F"

    PAYMENT_STATUS_CHOICES = [
        (PENDING_STATUS, _("در انتظار")),
        (PAYMENT_STATUS_COMPLETE, "موفق"),
        (PAYMENT_STATUS_FAILED, "نا موفق"),
    ]

    payment_status = models.CharField(
        max_length=1,
        choices=PAYMENT_STATUS_CHOICES,
        default=PENDING_STATUS,
        verbose_name=_("وضعیت پرداخت"),
    )
    DELIVERY_STATUS_SHIPPED = "S"
    DELIVERY_STATUS_DELIVERED = "D"
    _STATUS_RETURNED = "R"
    DELIVERY_STATUS_NOT_ACCEPTED_RETURN = "REJECT_RETURNED"

    DELIVERY_STATUS_CHOICES = [
        (NO_ANY_ACTION, _("انتخاب")),
        (PENDING_STATUS, _("در حال بسته بندی و پردازش")),
        (DELIVERY_STATUS_SHIPPED, _("تحویل پست")),
        (DELIVERY_STATUS_DELIVERED, _("تحویل مشتری")),
    ]

    PAYMENT_METHOD_ONLINE = "O"
    PAYMENT_METHOD_CASH = "C"
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_ONLINE, "آنلاین"),
        (PAYMENT_METHOD_CASH, "درب منزل"),
    ]

    RECEIVER_IS_MYSELF = "M"
    RECEIVER_IS_OTHER = "O"
    RECEIVER_CHOICES = [(RECEIVER_IS_MYSELF, "Myself"), (RECEIVER_IS_OTHER, "Other")]

    tracking_number = models.CharField(
        max_length=20, unique=True, verbose_name=_("شماره پیگیری")
    )
    payment_method = models.CharField(
        max_length=1,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_ONLINE,
        verbose_name=_("روش پرداخت"),
    )
    payment_reference = models.CharField(
        max_length=100,
        help_text=_(
            "سامانه ای که کاربر از آن پرداخت را انجام میدهد در این فیلد ذخیره میشود"
        ),
        verbose_name=_("مرجع پرداخت"),
        blank=True,
        null=True,
    )

    delivery_status = models.CharField(
        max_length=1,
        choices=DELIVERY_STATUS_CHOICES,
        default=NO_ANY_ACTION,
        verbose_name=_("وضعیت تحویل"),
    )
    delivery_date = models.CharField(
        max_length=150, null=True, blank=True, verbose_name=_("تاریخ تحویل")
    )
    deliver_post_name = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("نام پست"),
        help_text=_("این فیلد در پیامک ارسال میشود."),
    )
    delivery_tracking_url = models.CharField(
        max_length=700,
        null=True,
        blank=True,
        verbose_name=_("لینک رهگیری پست "),
        help_text=_("لینک رهگیری پست در این فیلد ذخیره میشود "),
    )
    delivery_address = models.TextField(verbose_name=_("آدرس تحویل"))
    delivery_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_("هزینه پست")
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_("هزینه کل سفارش")
    )
    use_wallet_balance = models.BooleanField(
        default=False,
        help_text=_(
            "اگر این مقدار true باشد تمام موجودی کیف پول در این سفارش استفاده میشود"
        ),
        verbose_name=_("استفاده از کیف پول"),
    )

    amount_used_wallet_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_(
            "این مقدار از کلا مبلغ سفارش کم میشود و مبلغ قابل پرداخت این را محاسبه میکند"
        ),
        verbose_name=_("پاداش استفاده شده"),
    )
    order_reward = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("این مقدار به کیف پول خریدار اضافه میگردد"),
        verbose_name=_("پاداش این سفارش"),
    )
    extra_describtion = models.TextField(
        null=True, blank=True, verbose_name=_("توضیحات کاربر")
    )
    receiver_phone_number = PhoneNumberField(
        region="IR", verbose_name=_("شماره موبایل")
    )
    receiver_full_name = models.CharField(max_length=200, verbose_name=_("نام گیرنده"))
    receiver_choose = models.CharField(
        max_length=1,
        choices=RECEIVER_CHOICES,
        default=RECEIVER_IS_MYSELF,
        verbose_name=_("انتخاب گیرنده"),
    )

    torob_payment_token = models.CharField(null=True,blank=True, max_length=200, verbose_name=_("توکن پرداخت ترب پی"),
                                           help_text=_("توکن پرداخت ترب پی فقط موقعی ساخته میشود که پرداخت با ترب پی انجام شود وگرنه خالی باید باشد."))
    torob_payment_page_url = models.CharField(null=True, blank=True, max_length=200, verbose_name=("صفحه پرداخت ترب پی"))
    RETURNED_ASK = "RA"
    RETURNED_CONFIRMED = "RC"
    RETURNED_REJECTED = "RR"
    RETURNED_STATUS_CHOICE = [
        (NO_ANY_ACTION, _("انتخاب")),
        (RETURNED_ASK, "درخواست مرجوعی"),
        (RETURNED_CONFIRMED, ("تایید درخواست مرجوعی")),
        (RETURNED_REJECTED, ("رد درخواست مرجوعی")),
    ]
    returned_status = models.CharField(
        choices=RETURNED_STATUS_CHOICE,
        default=NO_ANY_ACTION,
        verbose_name=_("وضعیت درخواست مرجوعی"),
        help_text=_(
            "اگر وضعیت رد درخواست مرجوعی را انتخاب میکنید لطفا قبلا از ذخیره کردن دلیل رد کردن را هم در فیلد خودش بنویسید"
        ),
    )
    returned_asked_reason = models.TextField(
        null=True, blank=True, verbose_name=_("دلیل درخواست مرجوعی")
    )
    returned_rejected_reason = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("دلیل رد درخواست"),
        help_text=_(
            "توجه داشته باشید که این متن در پیامک ارسال میشه پس کوتاه و مختصر بنویسید"
        ),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name=_("کاربر")
    )
    products = models.ManyToManyField(
        Product, through="OrderItem", related_name="orders", verbose_name=_("محصولات")
    )

    def _generate_tracking_number(self):
        prefix = "ADO"
        suffix_len = 19 - len(prefix)
        suffix = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=suffix_len)
        )
        return f"{prefix}_{suffix}"

    def generate_unique_tracking_number(self):
        """Generate a unique tracking number."""
        while True:
            tracking_number = self._generate_tracking_number()
            if not Order.objects.filter(tracking_number=tracking_number).exists():
                return tracking_number

    def save(self, *args, **kwargs):
        if not self.tracking_number:
            self.tracking_number = self.generate_unique_tracking_number()
            
        # # super().save(*args, **kwargs)
        # self.calculate_total_price()

        # # Save total reward to user's wallet
        # if self.use_wallet_balance:
        #     sروز دوشنبه ۲۴ دی  از ساعت 9 تا 12elf.use_user_walet_balance_in_order()

        # # Save total reward of this order to user's wallet
        # self.calculate_and_save_total_reward_in_user_wallet()

        # Call the original save method to actually save the data to the database
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("سفارش")
        verbose_name_plural = _("سفارشات")

    def __str__(self):
        return self.tracking_number


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="order_items",
        verbose_name=_("سفارش"),
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, verbose_name=_("محصول")
    )
    quantity = models.PositiveIntegerField(verbose_name=_("تعداد"))

    sold_price = models.PositiveBigIntegerField(default=0,verbose_name=" قیمت فروخته شده")

    def _get_discounted_price(self):
        return self.product.price * (1 - (self.product.price_discount_percent / 100))

    def get_total(self):
        return self._get_discounted_price() * self.quantity

    def get_wallet_reward(self):
        return (
            (self.product.price * self.product.wallet_discount) / 100
        ) * self.quantity
    
    def save(self, *args, **kwargs):
    # اگر sold_price هنوز مقدار نداشته باشد، آن را تنظیم کن
        if not self.sold_price:
            self.sold_price = round(self._get_discounted_price())  # گرد کردن قیمت نهایی

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("آیتم سفارش")
        verbose_name_plural = _("آیتم های سفارش")

    def __str__(self):
        return f"جزيیات سفارش {self.order}"


class OrderReceipt(Date):
    
    # ZarinPal status
    authority = models.CharField(max_length=36, null=True, blank=True)
    request_code = models.IntegerField(
        default=0, help_text=_("کد اگر ۱۰۰ باشد یعنی موفقیت امیز بود")
    )
    verify_code = models.IntegerField(
        default=0, help_text=_("کد اگر ۱۰۰ یا ۱۰۱ باشد یعنی موفقیت امیز بود")
    )
    ref_id = models.BigIntegerField(default=0, verbose_name="شماره تراكنش خرید")
    request_msg = models.CharField(max_length=500, null=True, blank=True)
    error_msg = models.CharField(max_length=500, null=True, blank=True)
    fee = models.BigIntegerField(default=0)
    fee_type = models.CharField(max_length=50, null=True, blank=True)
    card_hash = models.CharField(max_length=500, null=True, blank=True)
    card_pan = models.CharField(max_length=16, null=True, blank=True)
    connection_error = models.BooleanField(default=False)
    
    # Torob pay status
    # Successful: 
    torob_reciept = models.BooleanField(default=False)
    torob_transaction_id = models.CharField(null=True,blank=True, max_length=200)
    
    # Failed
    torob_error_message = models.TextField(null=True,blank=True)
    torob_error_code = models.CharField(null=True,blank=True, max_length=10)

    order = models.OneToOneField(
        Order, on_delete=models.PROTECT, related_name="receipt"
    )
    
    class Meta:
        verbose_name = _("رسید")
        verbose_name_plural = _("رسید ها")

    def __str__(self):
        if self and self.authority:
            return f"Zarin Pal:{self.authority[:3]}j ... {self.authority[-10:]}"
        elif self and self.torob_reciept:
            return "Torob Pay"
        return '-'

class OrderProvider(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = _("درگاه پرداخت")
        verbose_name_plural = _("درگاه های پرداخت")

    def __str__(self):
        return self.name

class Banner(models.Model):
    where = models.CharField(max_length=100)
    url = models.URLField()
    call_back_url = models.CharField(max_length=500, null=True, blank=True)
    title = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = _("بنر")
        verbose_name_plural = _("بنر ها")

    def __str__(self):
        return self.title


class Comment(Date):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="comments", verbose_name="محصول"
    )
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="replies",
        verbose_name="پاسخ",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="کاربر",
    )
    text = models.TextField(verbose_name="متن کامنت")
    rating = models.PositiveSmallIntegerField(
        default=0, verbose_name="امتیاز", help_text="امتیاز باید بین 1 تا 5 باشد"
    )
    buy_suggest = models.BooleanField(default=False, verbose_name=_("پیشنهاد خرید"))

    class Meta:
        verbose_name = _("کامنت")
        verbose_name_plural = _("کامنت‌ها")

    def __str__(self):
        return self.text[:20]

    def get_replies(self):
        return self.replies.all()


class Post(Date):
    STATUS = ((0, "Draft"), (1, "Publish"))
    title = models.CharField(max_length=200, verbose_name=_("تایتل"))
    slug = models.SlugField(max_length=200, unique=True)
    content = models.TextField(verbose_name=_("محتوا"))
    status = models.IntegerField(choices=STATUS, default=0, verbose_name=_("وضیعت"))
    authors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="posts", verbose_name=_("نویسندگان")
    )
    related_products = models.ManyToManyField(
        Product, related_name="posts", blank=True, verbose_name=_("محصولات مرتبط")
    )

    class Meta:
        ordering = ["-created_date"]
        verbose_name = _("بلاگ")
        verbose_name_plural = _("بلاگ ها")

    def __str__(self):
        return self.title


class PostImage(Date):
    alt = models.CharField(
        null=True, blank=True, max_length=500, verbose_name="نام عکس"
    )
    image_url = models.URLField(max_length=500, verbose_name=_("لینک عکس"))
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="images", verbose_name=_("پست")
    )

    class Meta:
        verbose_name = _("عکس بلاگ")
        verbose_name_plural = _("عکس ها بلاگ")

    def __str__(self):
        return str(self.image_url)


class Collaborate_Contact(Date):
    COLLABORATE = "collaborate"
    CONTACT_US = "contact"
    CHOICE = [(COLLABORATE, _("همکاری ")), (CONTACT_US, _("تماس با ما"))]

    full_name = models.CharField(max_length=200, verbose_name=_("نام و نام خانوادگی"))
    phone_number = PhoneNumberField(region="IR", verbose_name=_("شماره تلفن"))
    request_type = models.CharField(
        choices=CHOICE, default=COLLABORATE, verbose_name=("نوع درخواست")
    )
    address = models.TextField(null=True, verbose_name=_("آدرس"))
    comment = models.TextField(null=True, verbose_name=_("نظر"))

    class Meta:
        verbose_name = _("همکاری و ارتباط با ما")
        verbose_name_plural = _("درخواست های همکاری و ارتباط با ما")

    def __str__(self):
        return self.full_name
