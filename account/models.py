from typing import Any
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext as _ 
from django.utils import timezone

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
        