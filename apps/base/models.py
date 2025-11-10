import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Base model with common fields for all models
    """
    id = models.UUIDField(
        unique=True, default=uuid.uuid4, editable=False, db_index=True, primary_key=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
