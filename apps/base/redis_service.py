import redis
import json
import random
import string

from django.conf import settings
from typing import Optional, Dict, Any


class RedisService:
    """
    Redis service for OTP storage and management
    """
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    def generate_otp(self, length: int = None) -> str:
        """
        Generate random OTP code
        """
        if length is None:
            length = settings.OTP_LENGTH
        return ''.join(random.choices(string.digits, k=length))
    
    def store_otp(self, phone_number: str, otp: str, ttl: int = None) -> bool:
        """
        Store OTP in Redis with TTL using OTP as key
        """
        if ttl is None:
            ttl = settings.OTP_TTL
        
        key = f"otp:{otp}"
        otp_data = {
            'otp': otp,
            'phone_number': phone_number
        }
        try:
            self.redis_client.setex(key, ttl, json.dumps(otp_data))
            return True
        except Exception as e:
            print(f"Redis error storing OTP: {e}")
            return False
    
    def get_otp_data(self, otp: str) -> Optional[Dict[str, Any]]:
        """
        Get OTP data from Redis using OTP as key
        """
        key = f"otp:{otp}"
        try:
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Redis error getting OTP data: {e}")
            return None
    
    def delete_otp(self, otp: str) -> bool:
        """
        Delete OTP from Redis
        """
        key = f"otp:{otp}"
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Redis error deleting OTP: {e}")
            return False
    
    def verify_otp(self, otp: str) -> Optional[Dict[str, Any]]:
        """
        Verify OTP and return phone number if correct, then delete OTP
        """
        otp_data = self.get_otp_data(otp)
        if otp_data and otp_data.get('otp') == otp:
            self.delete_otp(otp)
            return otp_data
        return None
    
    def store_user_data(self, phone_number: str, user_data: Dict[str, Any], ttl: int = None) -> bool:
        """
        Store user data temporarily in Redis
        """
        if ttl is None:
            ttl = settings.OTP_TTL
        
        key = f"user_data:{phone_number}"
        try:
            self.redis_client.setex(key, ttl, json.dumps(user_data))
            return True
        except Exception as e:
            print(f"Redis error storing user data: {e}")
            return False
    
    def get_user_data(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Get user data from Redis
        """
        key = f"user_data:{phone_number}"
        try:
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Redis error getting user data: {e}")
            return None
    
    def delete_user_data(self, phone_number: str) -> bool:
        """
        Delete user data from Redis
        """
        key = f"user_data:{phone_number}"
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Redis error deleting user data: {e}")
            return False


redis_service = RedisService()
