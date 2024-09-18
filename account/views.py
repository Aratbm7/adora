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
from rest_framework.exceptions import PermissionDenied
from datetime import timedelta, datetime
from celery.result import AsyncResult
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import HttpRequest
# from rest_framework.generics import Re
from rest_framework.viewsets import ModelViewSet
from core.permissions import personal_permissions, object_level_permissions, address_object_level_permissions, object_level_permissions_restricted_actions
from rest_framework.decorators import action

class SendOtpCode(APIView):
    permission_classes = [permissions.AllowAny]
    http_method_names = ['post']
    
    def post(self, request: HttpRequest, *args, **kwargs):
        serializer = SendOtpSerilizer(data=request.data)
        serializer.is_valid(raise_exception=True)        
        allowed_reqeust_type = ['login_register', 'set_change_pass']
        request_type = serializer.validated_data.get('request_type', '')
        
        if request_type not in allowed_reqeust_type:
            return Response({'error': "Please send correct request type"}, status=status.HTTP_400_BAD_REQUEST)
        
        
        phone_number = str(serializer.validated_data['phone_number'])
        print(phone_number)
        phone_hash = hashlib.sha256((phone_number).encode()).hexdigest()
        print(phone_hash)

        # print("validate_data", serializer.validated_data)
        # otp = random.randint(100000, 999999)
        # print(otp)
        
        cache_key = f"otp_sent_{phone_hash}"
        cached_data = cache.get(cache_key)
        if cached_data:
            # result = AsyncResult(cached_data.get('task_id'), None)
            reminded_time = cache.ttl(cache_key)
            if reminded_time:
                return Response({'error': f'OTP request limit reached. Try again after {reminded_time} {"second" if reminded_time == 1 else "seconds"}.'},
                                    status=status.HTTP_429_TOO_MANY_REQUESTS)
    
        result = send_otp_to_phone.delay(str(phone_number), request_type)
        print('result', result)
        return Response({'token':phone_hash, "message": "Otp send request recieved successfully!", }, status=status.HTTP_200_OK)


class VerifyOtp(APIView):
    permission_classes = [permissions.AllowAny]
    http_method_names = ["post"]
    
    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone_hash = serializer.validated_data['phone_hash']
        otp = serializer.validated_data['otp']
        
        
        cache_key = f"otp_sent_{phone_hash}"
        cached_data = cache.get(cache_key)
                
        if not cached_data:
            return Response({'message': "Your code is expired please try to get new OTP code."}, status=status.HTTP_408_REQUEST_TIMEOUT)
        
        
        phone_number = cached_data.get('phone_number', '')
        # phone_number = '+98' + phone_number
        cached_otp = cached_data.get('otp', '')
        if  cached_otp != str(otp):
            return Response({'error':"Sended otp is not correct!"}, status=status.HTTP_400_BAD_REQUEST)
            
        cached_request_type = cached_data.get('request_type', '')
        
        # Reinitial the serializer with request_type
        serializer = VerifyOtpSerializer(data=request.data, context={'request_type': cached_request_type})
        serializer.is_valid(raise_exception=True)
        if cached_request_type == 'login_register':
            
            user =  User.objects.filter(phone_number=phone_number).first()
            
            if not user:    
                try:
                    new_user = User.objects.create_user(phone_number=phone_number)
                    new_refresh : RefreshToken= RefreshToken.for_user(new_user)
                    cache.delete(cache_key)
                    
                    return Response({'access': str(new_refresh.access_token),
                                    'refresh': str(new_refresh),
                                    'user_registered': True},
                            status=status.HTTP_201_CREATED)
            
                except Exception as e:
                    return Response({'error': "Error when create new user!"}, status=status.HTTP_400_BAD_REQUEST)
                

        
            refresh: RefreshToken = RefreshToken.for_user(user)
            # refresh.blacklist()
            cache.delete(cache_key)
            
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
    http_method_names = ['get', 'put']
    permission_classes = [personal_permissions({'u':31, 'o': 0, 'a': 63}),
                          object_level_permissions({'u':63, 'o': 0, 'a': 63})]
    serializer_class = ProfileSerializer
            
    
    def perform_update(self, serializer):
        serializer.save(user=self.request.user)
        
    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            # Admins can see all profiles
            return Profile.objects.select_related('user').all()
        else:
            # Regular users can only see their own profile
            return Profile.objects.filter(user=self.request.user)
        
        
    def get_permissions(self):
        # Apply custom permissions only for the 'me' action
        if self.action == 'me':
            return [permissions.IsAuthenticated()]  # Allow only authenticated users
        return super().get_permissions()

    @action(detail=False, methods=['get'])
    def me(self, request, pk=None):
        try:
            # Fetch the profile of the logged-in user
            profile = Profile.objects.get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except Profile.DoesNotExist:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
    
class AddressViewSet(ModelViewSet):
    http_method_names = ['get', 'put', 'post']

    # def perform_update(self, serializer):
    #     serializer.save(user=self.request.user)

    
    [personal_permissions({'u':31 , 'o': 0, 'a': 63}),
    address_object_level_permissions({'u':63, 'o': 0, 'a': 63})]
    permission_classes = [permissions.IsAuthenticated]
    queryset = Address.objects.all()
    serializer_class = AddressSerilizer
    
    def get_queryset(self):
        profile_pk = self.kwargs['profile_pk']
        profile = Profile.objects.filter(id=profile_pk).first()
        if profile:
            if profile.user == self.request.user:
                return Address.objects.filter(profile_id=self.kwargs['profile_pk'])

            else:
                raise PermissionDenied("You do not have permission to access addresses for this profile.")
        else:
            raise PermissionDenied("Profile does not exist.")
        
        

    # def get_queryset(self):
    #     # Ensure users only see addresses related to their profile
    #     user = self.request.user
    #     if user.is_authenticated:
    #         return Address.objects.filter(profile__user=user)
    #     return Address.objects.none()  # Return an empty queryset for unauthenticated users

    # def get_queryset(self):
    #     user = self.request.user
    #     if user.is_superuser or user.is_staff:
    #         return Address.objects.all()
    #     return Address.objects.filter(profile__user=user)
    
    def perform_create(self, serializer):
        profile = Profile.objects.get(pk=self.kwargs['profile_pk'])
        serializer.save(profile=profile)
        
    def perform_update(self, serializer):
        profile = Profile.objects.get(pk=self.kwargs['profile_pk'])
        serializer.save(profile=profile)
        
        

        
    
       
            
