from django.core.cache import cache
from rest_framework import generics, permissions, status
from django.contrib.auth.password_validation import validate_password
from rest_framework.views import APIView
from account.serializers import (SendOtpSerilizer,
                                 VerifyOtpSerializer,
                                 ProfileSerializer,
                                 AddressSerilizer)
from rest_framework.response import Response
from account.models import User, Profile, Address
from account.tasks import send_otp_to_phone
from django.conf import settings
import random
import hashlib 
from datetime import timedelta, datetime
from celery.result import AsyncResult
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import HttpRequest
# from rest_framework.generics import Re
from rest_framework.viewsets import ModelViewSet

class SendOtpCode(APIView):
    permission_classes = [permissions.AllowAny ]
    http_method_names = ['post']
    
    def post(self, request: HttpRequest, *args, **kwargs):
        serializer = SendOtpSerilizer(data=request.data)
        serializer.is_valid(raise_exception=True)        
        allowed_reqeust_type = ['login_register', 'set_change_pass']
        reqeust_type = serializer.validated_data.get('request_type', '')
        
        if reqeust_type not in allowed_reqeust_type:
            return Response({'error': "Please send correct request type"}, status=status.HTTP_400_BAD_REQUEST)
        
        
        phone_number = str(serializer.validated_data['phone_number'])
        phone_hash = hashlib.sha256((phone_number).encode()).hexdigest()

        print("validate_data", serializer.validated_data)
        otp = random.randint(100000, 999999)
        print(otp)
        
        cach_key = f"otp_sent_{phone_hash}"
        cached_data = cache.get(cach_key)
        if cached_data:
            # result = AsyncResult(cached_data.get('task_id'), None)
            reminded_time = cache.ttl(cach_key)
            if reminded_time:
                return Response({'error': f'OTP request limit reached. Try again after {reminded_time} {"second" if reminded_time == 1 else "seconds"}.'},
                                    status=status.HTTP_429_TOO_MANY_REQUESTS)
    

        cache.set(cach_key, {"otp":otp, "phone_number": phone_number, 'request_type': reqeust_type}, timeout=settings.CACHE_TTL)
        result = send_otp_to_phone.delay(str(phone_number), otp)
        return Response({'token':phone_hash, "message": "Otp send request recieved successfully!", }, status=status.HTTP_200_OK)


class VerifyOtp(APIView):
    permission_classes = [permissions.AllowAny]
    http_method_names = ["post"]
    
    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone_hash = serializer.validated_data['phone_hash']
        otp = serializer.validated_data['otp']
        
        cach_key = f"otp_sent_{phone_hash}"
        cached_data = cache.get(cach_key)
        
        if not cached_data:
            return Response({'message': "Your code is expired please try to get new OTP code."}, status=status.HTTP_408_REQUEST_TIMEOUT)
        
        
        phone_number = cached_data.get('phone_number', '')
        # phone_number = '+98' + phone_number
        cached_otp = cached_data.get('otp', 0)
        cached_request_type = cached_data.get('request_type', '')
        if not cached_otp == otp:
            return Response({'error':"Sended otp is not correct!"}, status=status.HTTP_400_BAD_REQUEST)
            
        if cached_request_type == 'login_register':
            
            user =  User.objects.filter(phone_number=phone_number).first()
            
            if not user:    
                try:
                    new_user = User.objects.create_user(phone_number=phone_number)
                    new_refresh : RefreshToken= RefreshToken.for_user(new_user)
                    cache.delete(cach_key)
                    return Response({'access': str(new_refresh.access_token),
                                    'refresh': str(new_refresh),
                                    'user_registered': True},
                            status=status.HTTP_201_CREATED)
            
                except Exception as e:
                    return Response({'error': "Error when create new user!"}, status=status.HTTP_400_BAD_REQUEST)
                

        
            refresh: RefreshToken = RefreshToken.for_user(user)
            # refresh.blacklist()
            cache.delete(cach_key)
            
            return Response({'access': str(refresh.access_token),
                                'refresh': str(refresh),
                                'user_registered': False},
                            status=status.HTTP_200_OK)
            
            
        if cached_request_type == 'set_change_pass':
            password = serializer.validated_data['password']
            
            user = User.objects.filter(phone_number=phone_number).first()
            
            if not user:
                return Response({'error': f'There is no user with this {phone_number}'}, status=status.HTTP_401_UNAUTHORIZED)
            
            try:
                validate_password(password)
            except Exception as e:
                return Response({'message': e.messages}, status=status.HTTP_400_BAD_REQUEST)
            

            user.set_password(password)
            user.save()
            
            return Response({'message': 'Password cahnge successfully!'}, status=status.HTTP_201_CREATED)
            

class ProfileViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
            
class AddressViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Address.objects.all()
    serializer_class = AddressSerilizer
            
            
