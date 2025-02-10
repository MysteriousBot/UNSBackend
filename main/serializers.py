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
        # Check if email exists in Staff table first
        email = attrs.get('email')
        try:
            staff = Staff.objects.get(email=email)
        except Staff.DoesNotExist:
            raise serializers.ValidationError({
                'email': 'Email not found in staff records. Please contact your administrator.'
            })
            
        # If we found the staff record, continue with normal validation
        return super().validate(attrs)
        
    def create(self, validated_data):
        user = super().create(validated_data)
        
        # Associate staff UUID with user profile
        try:
            staff = Staff.objects.get(email=user.email)
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'staff_uuid': staff.uuid}
            )
        except Staff.DoesNotExist:
            # This shouldn't happen due to validation, but just in case
            raise serializers.ValidationError({
                'email': 'Failed to associate staff record. Please contact your administrator.'
            })
        
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('id', 'staff_uuid', 'phone', 'title', 'role')
        read_only_fields = ('user',)

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()
    is_admin = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'profile', 'is_admin')
        read_only_fields = ('email', 'username')

    def get_is_admin(self, obj):
        return obj.profile.is_admin 