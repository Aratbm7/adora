from rest_framework import serializers
from account.models import User
from phonenumber_field.serializerfields import PhoneNumberField


class LoginRegisterSerializer(serializers.Serializer):
     phone_number = PhoneNumberField()
     
     
     
class UserSerializer(serializers.ModelSerializer):
    phone_number = PhoneNumberField()
    class Meta:
        model = User
        fields = ['id', 'phone_number']