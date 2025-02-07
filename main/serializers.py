from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, Staff
from django.contrib.auth.password_validation import validate_password
from djoser.serializers import UserCreateSerializer

class CustomUserCreateSerializer(UserCreateSerializer):
    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'username', 'password')
        
    def validate(self, attrs):
        print("Received data:", attrs)  # For debugging
        return super().validate(attrs)
        
    def create(self, validated_data):
        user = super().create(validated_data)
        
        # Create or update the user profile with staff_uuid
        staff_uuid = self.context['request'].data.get('staff_uuid')
        if staff_uuid:
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'staff_uuid': staff_uuid}
            )
        
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('id', 'staff_uuid', 'phone', 'title')
        read_only_fields = ('user',)

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'profile')
        read_only_fields = ('email', 'username') 