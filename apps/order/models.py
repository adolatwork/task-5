from django.db import models
from django.core.validators import MinValueValidator, EmailValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from decimal import Decimal

from apps.base.models import BaseModel


class Customer(BaseModel):
    """
    Customer model to store customer information
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer',
        null=True,
        blank=True,
        help_text="Linked user account (optional for guest checkout)"
    )
    email = models.EmailField(
        validators=[EmailValidator()],
        help_text="Customer email address"
    )
    full_name = models.CharField(
        max_length=255,
        help_text="Customer full name"
    )
    phone_number = models.CharField(
        max_length=20,
        help_text="Customer phone number"
    )
    address = models.TextField(
        blank=True,
        help_text="Customer address"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City"
    )
    country = models.CharField(
        max_length=100,
        default="Uzbekistan",
        help_text="Country"
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal code"
    )

    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        indexes = [
            models.Index(fields=['email'], name='customer_email_idx'),
            models.Index(fields=['phone_number'], name='customer_phone_idx'),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def clean(self):
        """Validate customer data"""
        super().clean()
        if self.phone_number and not self.phone_number.replace('+', '').replace(' ', '').isdigit():
            raise ValidationError({
                'phone_number': _('Phone number must contain only digits')
            })


class Order(BaseModel):
    """
    Order model with status tracking and transaction support
    """
    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        CONFIRMED = 'CONFIRMED', _('Confirmed')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')
        FAILED = 'FAILED', _('Failed')
        REFUNDED = 'REFUNDED', _('Refunded')

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='orders',
        help_text="Customer who placed the order"
    )
    order_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique order number"
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
        help_text="Current order status"
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Subtotal before tax and shipping"
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Tax amount"
    )
    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Shipping cost"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount (subtotal + tax + shipping)"
    )
    notes = models.TextField(
        blank=True,
        help_text="Order notes"
    )
    shipping_address = models.TextField(
        help_text="Shipping address"
    )

    version = models.IntegerField(
        default=0,
        help_text="Version for optimistic locking"
    )

    class Meta:
        db_table = 'orders'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number'], name='order_number_idx'),
            models.Index(fields=['status'], name='order_status_idx'),
            models.Index(fields=['customer', '-created_at'], name='order_customer_date_idx'),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.status}"

    def clean(self):
        """Validate order data"""
        super().clean()

        calculated_total = self.subtotal + self.tax_amount + self.shipping_cost
        if abs(self.total_amount - calculated_total) > Decimal('0.01'):
            raise ValidationError({
                'total_amount': _('Total amount must equal subtotal + tax + shipping')
            })

    def calculate_totals(self):
        """Calculate order totals from order items"""
        items = self.items.all()
        self.subtotal = sum(item.total_price for item in items)
        self.tax_amount = (self.subtotal * Decimal('0.12')).quantize(Decimal('0.01'))
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost
        return self.total_amount

    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        return self.status in [
            self.OrderStatus.PENDING,
            self.OrderStatus.PROCESSING,
            self.OrderStatus.CONFIRMED
        ]

    def can_be_refunded(self):
        """Check if order can be refunded"""
        return self.status == self.OrderStatus.COMPLETED


class OrderItem(BaseModel):
    """
    Order line items
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Parent order"
    )
    product_name = models.CharField(
        max_length=255,
        help_text="Product name (snapshot)"
    )
    product_sku = models.CharField(
        max_length=100,
        blank=True,
        help_text="Product SKU"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity ordered"
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Unit price at time of order"
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total price (quantity * unit_price)"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional product metadata"
    )

    class Meta:
        db_table = 'order_items'
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        indexes = [
            models.Index(fields=['order'], name='order_item_order_idx'),
            models.Index(fields=['product_sku'], name='order_item_sku_idx'),
        ]

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    def clean(self):
        """Validate order item data"""
        super().clean()

        calculated_total = self.unit_price * self.quantity
        if abs(self.total_price - calculated_total) > Decimal('0.01'):
            raise ValidationError({
                'total_price': _('Total price must equal unit_price * quantity')
            })

    def save(self, *args, **kwargs):
        """Auto-calculate total price before saving"""
        if not self.total_price or self.total_price == Decimal('0.00'):
            self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class Payment(BaseModel):
    """
    Payment model to track payment transactions
    """
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')
        REFUNDED = 'REFUNDED', _('Refunded')
        CANCELLED = 'CANCELLED', _('Cancelled')

    class PaymentMethod(models.TextChoices):
        CREDIT_CARD = 'CREDIT_CARD', _('Credit Card')
        DEBIT_CARD = 'DEBIT_CARD', _('Debit Card')
        PAYPAL = 'PAYPAL', _('PayPal')
        BANK_TRANSFER = 'BANK_TRANSFER', _('Bank Transfer')
        CASH = 'CASH', _('Cash')
        CRYPTO = 'CRYPTO', _('Cryptocurrency')

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='payments',
        help_text="Associated order"
    )
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique transaction identifier"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        help_text="Payment method used"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Payment amount"
    )
    currency = models.CharField(
        max_length=3,
        default='UZS',
        help_text="Currency code (ISO 4217)"
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
        help_text="Payment status"
    )
    payment_gateway = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment gateway used"
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Payment gateway response data"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if payment failed"
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when payment was processed"
    )

    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id'], name='payment_transaction_idx'),
            models.Index(fields=['order'], name='payment_order_idx'),
            models.Index(fields=['status'], name='payment_status_idx'),
        ]

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.status}"

    def clean(self):
        """Validate payment data"""
        super().clean()

        if self.status == self.PaymentStatus.COMPLETED and not self.processed_at:
            raise ValidationError({
                'processed_at': _('Processed timestamp required for completed payments')
            })
