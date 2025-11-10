from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from apps.user.models import User


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(help_text="Refresh token to get new access token")


class UserProfileSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = [
            'id',
            'phone_number',
            'first_name',
            'last_name',
            'email',
            'is_active',
            'is_verified',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'phone_number', 'role', 'created_at', 'updated_at', 'is_active', 'is_verified']


class RefreshResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField(help_text="New JWT access token")


class LogoutResponseSerializer(serializers.Serializer):
    message = serializers.CharField(help_text="Logout success message")


class AuthErrorSerializer(serializers.Serializer):
    """Error response for authentication endpoints"""
    error = serializers.CharField(help_text="Error message")


class PasswordLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20, help_text="Phone number: 998931159963")
    password = serializers.CharField(help_text="User password")


class PasswordLoginResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField(help_text="JWT access token")
    refresh_token = serializers.CharField(help_text="JWT refresh token")
    user = UserProfileSerializer(help_text="User profile information")


class SignupSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=20,
        help_text="Phone number: 998931159963"
    )
    password = serializers.CharField(
        min_length=6,
        write_only=True,
        help_text="Password (min 6 characters)"
    )
    password_confirm = serializers.CharField(
        write_only=True,
        help_text="Confirm password"
    )
    first_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        help_text="First name (optional)"
    )
    last_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        help_text="Last name (optional)"
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Email (optional)"
    )

    def validate_phone_number(self, value):
        """Validate phone number format and uniqueness"""
        if not value.startswith('998'):
            raise serializers.ValidationError(_('Phone number must start with 998'))

        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(_('A user with this phone number already exists'))

        return value

    def validate_email(self, value):
        """Validate email uniqueness if provided"""
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_('A user with this email already exists'))

        return value

    def validate(self, attrs):
        """Validate passwords match"""
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({
                'password_confirm': _('Passwords do not match')
            })

        return attrs

    def create(self, validated_data):
        """Create new user with validated data"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        return user


class SignupResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField(help_text="JWT access token")
    refresh_token = serializers.CharField(help_text="JWT refresh token")
    user = UserProfileSerializer(help_text="User profile information")
