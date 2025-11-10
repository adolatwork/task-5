import jwt
import uuid
import base64

from typing import Optional
from django.conf import settings
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object
from rest_framework.authentication import BaseAuthentication, BasicAuthentication

User = get_user_model()


class JWTAuthentication(BaseAuthentication):
    """
    JWT Authentication class for Django REST Framework
    """

    def authenticate(self, request):
        """
        Authenticate the request using JWT token with single session validation
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')

        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]

        try:
            payload = jwt.decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=['HS256']
            )

            user_id = payload.get('user_id')
            token_id = payload.get('token_id')

            if not user_id or not token_id:
                raise AuthenticationFailed('Invalid token payload')

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise AuthenticationFailed('User not found')

            if user.current_token_id != token_id:
                raise AuthenticationFailed('Token has been invalidated by new login')
                
            return (user, token)
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')
        except Exception as e:
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        """
        return 'Bearer'


class BasicAuth(BaseAuthentication):
    """
    Custom Basic Authentication class for phone number authentication
    """
    
    def authenticate(self, request):
        """
        Authenticate using phone number and password
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header or not auth_header.startswith('Basic '):
            return None
            
        try:
            encoded_credentials = auth_header.split(' ')[1]
            decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
            phone_number, password = decoded_credentials.split(':', 1)
        except (ValueError, UnicodeDecodeError):
            return None
            
        try:
            user = User.objects.get(phone_number=phone_number)
            if check_password(password, user.password):
                return (user, None)
        except User.DoesNotExist:
            pass
            
        return None
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        """
        return 'Basic'


class JWTTokenGenerator:
    """
    Utility class for generating JWT tokens
    """
    
    @staticmethod
    def generate_token(user) -> str:
        """
        Generate a JWT token for the given user with single session support
        """
        token_id = str(uuid.uuid4())
        
        payload = {
            'user_id': str(user.id),
            'phone_number': user.phone_number,
            'token_id': token_id,
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow(),
        }

        user.current_token_id = token_id
        user.save(update_fields=['current_token_id'])
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def generate_refresh_token(user) -> str:
        """
        Generate a refresh token for the given user with single session support
        """
        token_id = user.current_token_id or str(uuid.uuid4())
        
        payload = {
            'user_id': str(user.id),
            'type': 'refresh',
            'token_id': token_id,
            'exp': datetime.utcnow() + timedelta(days=30),
            'iat': datetime.utcnow(),
        }
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """
        Verify and decode a JWT token
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None


class JWTAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = 'apps.base.auth.JWTAuthentication'
    name = 'JWTAuthentication'
    
    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name='Authorization',
            token_prefix='Bearer',
            bearer_format='JWT'
        )


class BasicAuthExtension(OpenApiAuthenticationExtension):
    target_class = 'apps.base.auth.BasicAuth'
    name = 'BasicAuth'
    
    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'basic',
            'description': 'Basic authentication using phone number and password'
        }


__all__ = [
    'JWTAuthentication',
    'BasicAuthentication',
    'BasicAuth',
    'JWTTokenGenerator',
    'JWTAuthenticationExtension',
    'BasicAuthExtension',
]
