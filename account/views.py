from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from account.serializers import LoginRegisterSerializer, UserSerializer
from rest_framework.response import Response
from account.models import User
 

class LoginRegister(APIView):
    permission_classes = [permissions.AllowAny ]
    
    def post(self, request, *args, **kwargs):
        print("request.data", request.data)
        serializer = LoginRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)        
                
        phone_number = serializer.validated_data['phone_number']        

        print(phone_number, 'sdfg')
        
        return Response({'token': "df"})

    def get(self, request, *args, **kawrgs):
        users = User.objects.all()
        serializer  = UserSerializer(users, many=True)
        
        
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        

# Create your views here.
