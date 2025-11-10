from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """
    Advanced custom user manager for phone number authentication
    """
    
    def create_user(self, phone_number, password=None, **extra_fields):
        """
        Create and return a regular user with the given phone number and password.
        """
        if not phone_number:
            raise ValueError('The phone number must be set')
        
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        """
        Create and return a superuser with the given phone number and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)

    def active_users(self):
        """
        Return queryset of all active users
        """
        return self.filter(is_active=True)

    def verified_users(self):
        """
        Return queryset of all verified users
        """
        return self.filter(is_verified=True)
