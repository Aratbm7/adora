from typing import Any
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext as _ 
from django.utils import timezone
import base64
import uuid 

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
        return str(self.phone_number)
    
    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

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
    referral_code = models.CharField(max_length=25, verbose_name=_('کد دعوت'), unique=True)
    user = models.OneToOneField(User, on_delete=models.SET_NULL,related_name='profile',  verbose_name=_('کاربر'), null=True)
    
    class Meta:
        verbose_name = _('پروفایل')
        verbose_name_plural = ('پروفایل ها')
        
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            while True:
                new_referall_code = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode("utf-8").rstrip()[:25]
                if not User.objects.filter(referral_code=new_referall_code).exists():
                    self.referral_code = new_referall_code
                    break
                
        super(User, self).save(*args, **kwargs)
        
        
    
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