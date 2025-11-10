from django.contrib import admin
from apps.order.models import Customer, Order, OrderItem, Payment


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone_number', 'city', 'country', 'created_at']
    list_filter = ['country', 'city', 'created_at']
    search_fields = ['full_name', 'email', 'phone_number']
    readonly_fields = ['id', 'created_at', 'updated_at']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['id', 'total_price', 'created_at']


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['id', 'transaction_id', 'status', 'processed_at', 'created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'customer', 'status', 'total_amount',
        'created_at', 'updated_at'
    ]
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['order_number', 'customer__email', 'customer__full_name']
    readonly_fields = [
        'id', 'order_number', 'version', 'subtotal', 'tax_amount',
        'total_amount', 'created_at', 'updated_at'
    ]
    inlines = [OrderItemInline, PaymentInline]

    fieldsets = (
        ('Order Information', {
            'fields': ('id', 'order_number', 'customer', 'status', 'version')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'tax_amount', 'shipping_cost', 'total_amount')
        }),
        ('Shipping', {
            'fields': ('shipping_address',)
        }),
        ('Additional', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'product_name', 'product_sku', 'quantity',
        'unit_price', 'total_price', 'created_at'
    ]
    list_filter = ['created_at']
    search_fields = ['product_name', 'product_sku', 'order__order_number']
    readonly_fields = ['id', 'total_price', 'created_at', 'updated_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'order', 'payment_method', 'amount',
        'status', 'processed_at', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at', 'processed_at']
    search_fields = ['transaction_id', 'order__order_number']
    readonly_fields = [
        'id', 'transaction_id', 'processed_at', 'created_at', 'updated_at'
    ]

    fieldsets = (
        ('Transaction Information', {
            'fields': ('id', 'transaction_id', 'order', 'status')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'amount', 'currency', 'payment_gateway')
        }),
        ('Processing', {
            'fields': ('processed_at', 'gateway_response', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
