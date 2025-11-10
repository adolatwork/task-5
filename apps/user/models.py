from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from apps.base.models import BaseModel

from .managers import UserManager


class User(AbstractUser, BaseModel):
    """
    Custom User model with additional fields
    """

    username = None
    phone_number = models.CharField(max_length=20, unique=True, help_text="Phone number: 998931159963")
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True, null=True)
    is_verified = models.BooleanField(default=False, help_text="Verified user")
    current_token_id = models.CharField(max_length=255, blank=True, null=True, help_text="Current active token ID for single session")

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'phone_number',
                    'first_name',
                    'last_name',
                ],
                name='unique_user_identity'
            )
        ]
        indexes = [
            models.Index(
                fields=[
                    'phone_number',
                    'first_name',
                    'last_name'
                ],
                name='user_identity_idx'
            )
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}" if self.first_name and self.last_name else self.phone_number

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.phone_number

    def clean(self):
        """
        Model-level validation
        """
        super().clean()

        if self.phone_number and not self.phone_number.startswith('998'):
            raise ValidationError({
                'phone_number': _('Phone number must start with 998')
            })
        
        if self.email and User.objects.filter(email=self.email).exclude(pk=self.pk).exists():
            raise ValidationError({
                'email': _('A user with this email already exists.')
            })

    def save(self, *args, **kwargs):
        """
        Override save to run clean validation
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    def invalidate_all_sessions(self):
        """
        Invalidate all user sessions by clearing token ID
        """
        self.current_token_id = None
        self.save(update_fields=['current_token_id'])
