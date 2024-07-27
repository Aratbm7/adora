from rest_framework import serializers
from account.models import User, Profile, Address
from phonenumber_field.serializerfields import PhoneNumberField


def valid_id(id):
    control_num = id[-1]
    body = id[:-1]
    body_sum_with_position = sum(int(body[abs(i - 10)]) * i  for i in range(10, 1, -1))
    remind = body_sum_with_position % 11

    if remind < 2:
        return remind == int(control_num)
    return (11 - remind) == int(control_num)


class SendOtpSerilizer(serializers.Serializer):
    phone_number = PhoneNumberField()
    
    # request_type canb login_register and set_change_pass
    request_type = serializers.CharField(default="login_register", max_length=20)
    
     
class VerifyOtpSerializer(serializers.Serializer):
    phone_hash = serializers.CharField(max_length=64, min_length=64)
    otp = serializers.IntegerField(max_value=999999, min_value=100000)
    
    # This field is iptional for using 
    password = serializers.CharField(min_length=6)
    

class UserSerializer(serializers.ModelSerializer):
    phone_number = PhoneNumberField()
    class Meta:
        model = User
        fields = ['id', 'phone_number']
    
        
class ProfileSerializer(serializers.ModelSerializer):
    
    class Meta:
        model=Profile
        # fields = ['id','id_card', 'first_name', 'last_name','user', 'addresses']
        fields = '__all__'
        
    def validate_id_card(self, value):
        
        if len(value) != 10 or not value.isdigit():
            raise serializers.ValidationError("کد ملی باید 10 رقمی و تنها شامل اعداد باشد.")

        if not valid_id(value):
            raise serializers.ValidationError('لطفا کد ملی معتبر خودتان را وارد کنید')

        return value
            
        
class AddressSerilizer(serializers.ModelSerializer):
    
    class Meta:
        model = Address 
        fields = '__all__'