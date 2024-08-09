from django.db import models
from django.utils.translation import gettext as _ 
from django.contrib.auth import get_user_model


# Create your models here.
class Date(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_date = models.DateTimeField(auto_now=True, verbose_name="تاریخ آپدیت" )
    
    class Meta:
        verbose_name = _("دسته بندی")
        verbose_name_plural = _("دسته بندی کل")

    class Meta:
        abstract = True
        

class Category(Date):
    name = models.CharField(max_length=500, verbose_name="نام")
    image = models.URLField(max_length=500, verbose_name=_("لینک محصول"))
    alt = models.CharField(null=True,blank=True, max_length=500, verbose_name="نام عکس")

    class Meta:
       verbose_name = _("دسته بندی")
       verbose_name_plural = _("دسته بندی کل") 
    def __str__(self) -> str:
        return self.name


class Car(Date):
    fa_name = models.CharField(max_length=100, verbose_name=_("نام فارسی"))
    image = models.URLField(max_length=500,null=True, blank=True, verbose_name=_("عکس محصول"))
    alt = models.CharField(null=True,blank=True, max_length=500, verbose_name="نام عکس")

    
    class Meta:
        verbose_name = _("خودرو")
        verbose_name_plural = _(" خودرو ها")

    def __str__(self) -> str:
        return self.fa_name
    
    
class Brand(Date):
    name = models.CharField(max_length=100, verbose_name=_("نام"))
    image = models.URLField(null=True, blank=True, max_length=500, verbose_name=_("لینک محصول"))
    alt = models.CharField(null=True,blank=True, max_length=500, verbose_name="نام عکس")
    abbreviation = models.CharField(null=True,blank=True, max_length=10, verbose_name="مخفف")

    
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
    alt = models.CharField(null=True,blank=True, max_length=500, verbose_name="نام عکس")
    image_url = models.URLField(max_length=500, verbose_name=_("لینک محصول"))
    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name='images', verbose_name=_("محصول"))
    
    class Meta:
        verbose_name = _(" عکس محصول")
        verbose_name_plural = _("عکس های محصول")

    def __str__(self) -> str:
        if self.alt:
            return self.alt
        
        return str(self.id)
       
class Product(Date):
    fa_name = models.CharField(max_length=500, verbose_name="نام فارسی")
    en_name = models.CharField(max_length=500, verbose_name="نام انگلیسی")
    price = models.PositiveBigIntegerField( verbose_name="قیمت محصول")
    price_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=" درصد تخفیف قیمت")
    wallet_discount = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="درصد تخفیف پاداش محصول")
    count = models.IntegerField(default=0, verbose_name="تعداد موجودی")
    install_location = models.CharField(max_length=500, null=True, blank=True, verbose_name="محل نصب")
    count_in_box = models.IntegerField(default=0, verbose_name="تعداد در جعبه")
    guarantee = models.CharField(max_length=500, null=True, blank=True, verbose_name='گارانتی' )
    guarantee_duration = models.IntegerField(default=0, verbose_name="مدت زمان گارانتی", help_text=_("مدت زمان به ماه وارد شود"))
    new = models.BooleanField(default=False, verbose_name="محصول جدید")
    buyer = models.PositiveIntegerField(default=0, verbose_name=_("تعداد خریدار"))
    customer_point = models.PositiveIntegerField(default=0, verbose_name=_("درصد رضایت خریداران"))
    title_description = models.TextField(null=True, blank=True, verbose_name=_("توضیحات معرفی محصول"))
    packing_description = models.TextField(null=True, blank=True, verbose_name=_("توضیحات بسته بندی محصول"))
    shopping_description = models.TextField(null=True, blank=True, verbose_name=_("توضیحات خرید محصول"))
    
    material = models.ForeignKey(Matrial, related_name="products", on_delete=models.SET_NULL,  null=True, blank=True, verbose_name="جنس محصول")
    category = models.ForeignKey(Category, related_name="products", on_delete=models.CASCADE, verbose_name="دسته بندی" )
    brand = models.ForeignKey(Brand, null=True, related_name="products", on_delete=models.SET_NULL, verbose_name=_("شرکت سازنده"))
    similar_products = models.ManyToManyField("self", blank=True, symmetrical=False, verbose_name="محصولات مشابه")
    compatible_cars = models.ManyToManyField(Car, blank=True, related_name='products', verbose_name=_("مناسب خودرو های"))

    class Meta:
        verbose_name = _("محصول")
        verbose_name_plural = _("محصولات")
        
    def __str__(self):
        return self.fa_name

    

class Comment(Date):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments',verbose_name="محصول")
    parent = models.ForeignKey('self', blank=True, null=True, on_delete=models.CASCADE, related_name='replies', verbose_name='پاسخ')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='comments', verbose_name='کاربر')

    text = models.TextField(verbose_name="متن کامنت")
    rating = models.PositiveSmallIntegerField(default=0, verbose_name="امتیاز", help_text="امتیاز باید بین 1 تا 5 باشد")

    class Meta:
        verbose_name = _("کامنت")
        verbose_name_plural = _("کامنت‌ها")

    def __str__(self):
        return self.text[:20]

    def get_replies(self):
        return self.replies.all()
    
