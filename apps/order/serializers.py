from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from apps.order.models import Customer, Order, OrderItem, Payment


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer model"""
    user_id = serializers.UUIDField(source='user.id', read_only=True, allow_null=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True, allow_null=True)

    class Meta:
        model = Customer
        fields = [
            'id',
            'user_id',
            'user_phone',
            'email',
            'full_name',
            'phone_number',
            'address',
            'city',
            'country',
            'postal_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'user_phone', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem model"""

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product_name',
            'product_sku',
            'quantity',
            'unit_price',
            'total_price',
            'metadata',
        ]
        read_only_fields = ['id', 'total_price']

    def validate_quantity(self, value):
        """Validate quantity is positive"""
        if value < 1:
            raise serializers.ValidationError(_('Quantity must be at least 1'))
        return value

    def validate_unit_price(self, value):
        """Validate unit price is positive"""
        if value <= Decimal('0.00'):
            raise serializers.ValidationError(_('Unit price must be greater than 0'))
        return value


class OrderItemCreateSerializer(serializers.Serializer):
    """Serializer for creating order items (simplified input)"""
    product_name = serializers.CharField(max_length=255)
    product_sku = serializers.CharField(max_length=100, required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    metadata = serializers.JSONField(required=False, default=dict)


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""

    class Meta:
        model = Payment
        fields = [
            'id',
            'transaction_id',
            'payment_method',
            'amount',
            'currency',
            'status',
            'payment_gateway',
            'error_message',
            'processed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'transaction_id',
            'status',
            'error_message',
            'processed_at',
            'created_at',
            'updated_at',
        ]


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model with nested items and payments"""
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    customer = CustomerSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'customer',
            'order_number',
            'status',
            'subtotal',
            'tax_amount',
            'shipping_cost',
            'total_amount',
            'notes',
            'shipping_address',
            'items',
            'payments',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'order_number',
            'status',
            'subtotal',
            'tax_amount',
            'total_amount',
            'created_at',
            'updated_at',
        ]


class OrderCreateSerializer(serializers.Serializer):
    """Serializer for creating a new order with atomic transaction"""
    customer_id = serializers.UUIDField(required=False, allow_null=True, help_text="Existing customer ID")
    customer_email = serializers.EmailField(required=False, help_text="Email for new customer")
    customer_name = serializers.CharField(max_length=255, required=False, help_text="Name for new customer")
    customer_phone = serializers.CharField(max_length=20, required=False, help_text="Phone for new customer")

    shipping_address = serializers.CharField(help_text="Shipping address")
    shipping_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        min_value=Decimal('0.00')
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    items = OrderItemCreateSerializer(many=True, help_text="List of order items")

    payment_method = serializers.ChoiceField(
        choices=Payment.PaymentMethod.choices,
        help_text="Payment method"
    )

    def validate(self, attrs):
        """Validate that either customer_id or customer details are provided"""
        customer_id = attrs.get('customer_id')
        customer_email = attrs.get('customer_email')
        customer_name = attrs.get('customer_name')
        customer_phone = attrs.get('customer_phone')

        # Note: If authenticated, customer will be auto-created from user
        # So we only require customer data for unauthenticated requests
        # This check will be done in the view layer

        items = attrs.get('items', [])
        if not items:
            raise serializers.ValidationError({
                'items': _('At least one order item is required')
            })

        return attrs


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating order status"""
    status = serializers.ChoiceField(choices=Order.OrderStatus.choices)
    notes = serializers.CharField(required=False, allow_blank=True)


class PaymentProcessSerializer(serializers.Serializer):
    """Serializer for processing payment"""
    payment_method = serializers.ChoiceField(choices=Payment.PaymentMethod.choices)
    payment_gateway = serializers.CharField(required=False, allow_blank=True, default='')


class OrderCancelSerializer(serializers.Serializer):
    """Serializer for cancelling an order"""
    reason = serializers.CharField(required=False, allow_blank=True)


class OrderRefundSerializer(serializers.Serializer):
    """Serializer for refunding an order"""
    reason = serializers.CharField(required=True)
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        help_text="Partial refund amount (optional, full refund if not specified)"
    )


class OrderErrorSerializer(serializers.Serializer):
    """Error response serializer for order endpoints"""
    error = serializers.CharField()
    detail = serializers.CharField(required=False)
