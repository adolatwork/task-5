from rest_framework import status
from apps.user.models import User
from rest_framework.views import APIView
from apps.base.auth import JWTTokenGenerator
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.user.serializers import (
    RefreshTokenSerializer, UserProfileSerializer,
    RefreshResponseSerializer, LogoutResponseSerializer,
    AuthErrorSerializer, PasswordLoginSerializer, PasswordLoginResponseSerializer,
    SignupSerializer, SignupResponseSerializer,
)
from django.utils.translation import gettext_lazy as _


class SignupView(APIView):
    """
    User signup/registration endpoint
    """
    permission_classes = [AllowAny]
    serializer_class = SignupResponseSerializer

    @extend_schema(
        operation_id='user_signup',
        summary='User Signup',
        description='Register a new user with phone number and password',
        request=SignupSerializer,
        responses={
            201: SignupResponseSerializer,
            400: AuthErrorSerializer,
        },
        examples=[
            OpenApiExample(
                'Signup Request',
                summary='User signup request',
                description='Example signup request with required fields',
                value={
                    'phone_number': '998931159963',
                    'password': 'secure_password',
                    'password_confirm': 'secure_password',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'email': 'john@example.com'
                },
                request_only=True
            ),
            OpenApiExample(
                'Signup Success Response',
                summary='Successful signup response',
                description='Response when signup is successful',
                value={
                    'access_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                    'refresh_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                    'user': {
                        'id': '01HZ8X9K2M3N4P5Q6R7S8T9U0V',
                        'phone_number': '998931159963',
                        'first_name': 'John',
                        'last_name': 'Doe',
                        'email': 'john@example.com',
                        'is_verified': False,
                        'created_at': '2024-01-01T00:00:00Z',
                        'updated_at': '2024-01-01T00:00:00Z'
                    }
                },
                response_only=True
            )
        ]
    )
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        token = JWTTokenGenerator.generate_token(user)
        refresh_token = JWTTokenGenerator.generate_refresh_token(user)

        response_data = {
            'access_token': token,
            'refresh_token': refresh_token,
            'user': {
                'id': str(user.id),
                'phone_number': user.phone_number,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'is_active': user.is_active,
                'is_verified': user.is_verified,
                'created_at': user.created_at,
                'updated_at': user.updated_at,
            }
        }

        response_serializer = SignupResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    Password-based login endpoint (main login method)
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordLoginResponseSerializer
    
    @extend_schema(
        operation_id='user_login',
        summary='User Login (Password)',
        description='Login using phone number and password. This is the main login method.',
        request=PasswordLoginSerializer,
        responses={
            200: PasswordLoginResponseSerializer,
            400: AuthErrorSerializer,
            401: AuthErrorSerializer,
        },
        examples=[
            OpenApiExample(
                'Password Login Request',
                summary='Password login request',
                description='Example password login request with phone number and password',
                value={
                    'phone_number': '998931159963',
                    'password': 'your_password'
                },
                request_only=True
            ),
            OpenApiExample(
                'Password Login Success Response',
                summary='Successful password login response',
                description='Response when password login is successful',
                value={
                    'access_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                    'refresh_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                    'user': {
                        'id': '01HZ8X9K2M3N4P5Q6R7S8T9U0V',
                        'phone_number': '998931159963',
                        'first_name': 'John',
                        'last_name': 'Doe',
                        'email': 'john@example.com',
                        'is_verified': True,
                        'created_at': '2024-01-01T00:00:00Z',
                        'updated_at': '2024-01-01T00:00:00Z'
                    }
                },
                response_only=True
            )
        ]
    )
    def post(self, request):
        serializer = PasswordLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone_number = serializer.validated_data['phone_number']
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(phone_number=phone_number)
            if not user.check_password(password):
                return Response(
                    {'error': _('Invalid phone number or password')}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )

        except User.DoesNotExist:
            return Response(
                {'error': _('Invalid phone number or password')}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        token = JWTTokenGenerator.generate_token(user)
        refresh_token = JWTTokenGenerator.generate_refresh_token(user)
        
        response_data = {
            'access_token': token,
            'refresh_token': refresh_token,
            'user': {
                'id': str(user.id),
                'phone_number': user.phone_number,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'is_active': user.is_active,
                'is_verified': user.is_verified,
                'created_at': user.created_at,
                'updated_at': user.updated_at,
            }
        }
        
        response_serializer = PasswordLoginResponseSerializer(response_data)
        return Response(response_serializer.data)


class RefreshTokenView(APIView):
    """
    Refresh JWT token endpoint
    """
    permission_classes = [AllowAny]
    serializer_class = RefreshTokenSerializer
    
    @extend_schema(
        operation_id='user_refresh_token',
        summary='Refresh JWT Token',
        description='Refresh expired JWT access token using refresh token',
        request=RefreshTokenSerializer,
        responses={
            200: RefreshResponseSerializer,
            400: AuthErrorSerializer,
            401: AuthErrorSerializer,
        },
        examples=[
            OpenApiExample(
                'Refresh Token Request',
                summary='Refresh token request',
                description='Example refresh token request',
                value={
                    'refresh_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                },
                request_only=True
            ),
            OpenApiExample(
                'Refresh Token Success Response',
                summary='Successful token refresh response',
                description='Response when token refresh is successful',
                value={
                    'access_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                },
                response_only=True
            )
        ]
    )
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        refresh_token = serializer.validated_data['refresh_token']
        
        payload = JWTTokenGenerator.verify_token(refresh_token)
        
        if not payload or payload.get('type') != 'refresh':
            return Response(
                {'error': _('Invalid refresh token')}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            user = User.objects.get(id=payload['user_id'])

            token_id = payload.get('token_id')
            if user.current_token_id != token_id:
                return Response(
                    {'error': _('Refresh token has been invalidated by new login')}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            new_token = JWTTokenGenerator.generate_token(user)
            
            response_data = {
                'access_token': new_token,
            }
            
            response_serializer = RefreshResponseSerializer(response_data)
            return Response(response_serializer.data)
        except User.DoesNotExist:
            return Response(
                {'error': _('User not found')}, 
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    """
    Logout endpoint - invalidates current session
    """
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutResponseSerializer

    @extend_schema(
        operation_id='user_logout',
        summary='User Logout',
        description='Logout user and invalidate current session token',
        responses={
            200: LogoutResponseSerializer,
            401: AuthErrorSerializer,
        },
        examples=[
            OpenApiExample(
                'Logout Success Response',
                summary='Successful logout response',
                description='Response when logout is successful',
                value={
                    'message': 'Successfully logged out'
                },
                response_only=True
            )
        ]
    )
    def post(self, request):
        user = request.user
        user.current_token_id = None
        user.save(update_fields=['current_token_id'])
        
        response_data = {
            'message': _('Successfully logged out')
        }
        
        response_serializer = LogoutResponseSerializer(response_data)
        return Response(response_serializer.data)


class ProfileView(APIView):
    """
    Get current user profile
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    
    @extend_schema(
        operation_id='user_profile',
        summary='Get User Profile',
        description='Get current authenticated user profile information',
        responses={
            200: UserProfileSerializer,
            401: AuthErrorSerializer,
        },
        examples=[
            OpenApiExample(
                'Profile Success Response',
                summary='User profile response',
                description='Response with user profile information',
                value={
                    'id': '01HZ8X9K2M3N4P5Q6R7S8T9U0V',
                    'phone_number': '998931159963',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'email': 'john@example.com',
                    'is_verified': True,
                    'created_at': '2024-01-01T00:00:00Z',
                    'updated_at': '2024-01-01T00:00:00Z'
                },
                response_only=True
            )
        ]
    )
    def get(self, request):
        user = request.user
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)
