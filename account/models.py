
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext as _ 
from django.utils import timezone


class DateFields(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ثبت نام'), unique=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('تاریخ تغییر'))

    class Meta:
        abstract = True


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The Phone Number must be set')
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone_number = PhoneNumberField(unique=True,region='IR', verbose_name=_('شماره موبایل'))
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_admin = models.BooleanField(default=False, verbose_name=_('ادمین'))

    
    objects = UserManager()
    USERNAME_FIELD = 'phone_number'
    
    class Meta:
        verbose_name = _("کاربر")
        verbose_name_plural = _("کاربرها")
        
    
    def __str__(self) -> str:
        return str(self.phone_number).replace('+98', '0')
    
    # def has_perm(self, perm, obj=None):
    #     return True

    # def has_module_perms(self, app_label):
    #     return True

    # @property
    # def is_staff(self):
    #     return self.is_admin
    
    # class Profile(models.Model):
    #     first_name = models.CharField(_("first name"), max_length=150, blank=True, verbose_name=_("نام"))
    #     last_name = models.CharField(_("last name"), max_length=150, blank=True, verbose_name=_("نام خانوادگی"))


class Profile(DateFields):
    first_name = models.CharField(_("نام"), max_length=150, blank=True, null=True)
    last_name = models.CharField(_("نام خانوادگی"), max_length=150, blank=True, null=True)
    id_card =  models.CharField(null=True, blank=True, max_length=10,  verbose_name=_('کد ملی'), 
                            error_messages={"required": 'لطفا کد ملی را وارد کنید'}, unique=True)
    email = models.EmailField(null=True, blank=True, verbose_name=_('ایمیل'))
    # referral_code = models.CharField(max_length=25, verbose_name=_('کد دعوت'), unique=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2,default=0, verbose_name=_('کیف پول'))
    user = models.OneToOneField(User, on_delete=models.SET_NULL,related_name='profile',  verbose_name=_('کاربر'), null=True)
    
    class Meta:
        verbose_name = _('پروفایل')
        verbose_name_plural = ('پروفایل ها')
        
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    
    def __str__(self):
        return self.get_full_name()
 
    
class Address(DateFields):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='addresses', verbose_name=_('پروفایل'))
    street_address = models.TextField(_("آدرس دقیق"))
    city = models.CharField(_("شهر"), max_length=100)
    state = models.CharField(_("استان"), max_length=100)
    postal_code = models.CharField(_("کد پستی"), max_length=20)
    # country = models.CharField(_("کشور"), max_length=100)
    
    class Meta:
        verbose_name = _('آدرس')
        verbose_name_plural = ('آدرس ها')
        
    def __str__(self):
        if len(self.street_address) > 10:
            short_address = self.street_address[:10] + "..."
        else:
            short_address = self.street_address
        return f"{self.city}, {self.state}, {short_address}"
    
    
class DeliveryCost(models.Model):
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('هزینه پست'))
    post_service = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("نام پست"))
    extra_description = models.TextField(null=True, blank=True, verbose_name=_('توضیحات اضافه'))
    
    
    class Meta:
        verbose_name = _('سرویس پست')
        verbose_name_plural =  _("سرویس های پست ")
        
    def __str__(self):
        return f"{self.post_service} {self.cost}"
    





