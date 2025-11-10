import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

from apps.order.models import Customer, Order, OrderItem, Payment

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user"""
    return User.objects.create_user(
        phone_number='998901234567',
        password='testpass123',
        first_name='Test',
        last_name='User',
        email='test@example.com',
        is_verified=True,
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user"""
    return User.objects.create_superuser(
        phone_number='998900000000',
        password='adminpass123',
        first_name='Admin',
        last_name='User',
        email='admin@example.com',
    )


@pytest.fixture
def customer(db, user):
    """Create a test customer linked to user"""
    return Customer.objects.create(
        user=user,
        email='customer@example.com',
        full_name='Test Customer',
        phone_number='998901234567',
        address='123 Test Street',
        city='Tashkent',
        country='Uzbekistan',
        postal_code='100000',
    )


@pytest.fixture
def guest_customer(db):
    """Create a guest customer (no user link)"""
    return Customer.objects.create(
        email='guest@example.com',
        full_name='Guest Customer',
        phone_number='998909999999',
        address='456 Guest Street',
        city='Samarkand',
        country='Uzbekistan',
    )


@pytest.fixture
def order(db, customer):
    """Create a test order"""
    order = Order.objects.create(
        customer=customer,
        order_number='ORD-20250109-TEST01',
        status=Order.OrderStatus.PENDING,
        shipping_address='123 Test Street, Tashkent',
        shipping_cost=Decimal('5.00'),
        notes='Test order',
    )

    OrderItem.objects.create(
        order=order,
        product_name='Test Laptop',
        product_sku='LAP-001',
        quantity=1,
        unit_price=Decimal('1000.00'),
        total_price=Decimal('1000.00'),
    )

    OrderItem.objects.create(
        order=order,
        product_name='Test Mouse',
        product_sku='MOU-001',
        quantity=2,
        unit_price=Decimal('25.00'),
        total_price=Decimal('50.00'),
    )

    order.calculate_totals()
    order.save()

    return order


@pytest.fixture
def payment(db, order):
    """Create a test payment"""
    return Payment.objects.create(
        order=order,
        transaction_id='TXN-20250109-TEST01',
        payment_method=Payment.PaymentMethod.CREDIT_CARD,
        amount=order.total_amount,
        status=Payment.PaymentStatus.PENDING,
    )


@pytest.fixture
def api_client():
    """Create API client"""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Create authenticated API client"""
    from apps.base.auth import JWTTokenGenerator

    token = JWTTokenGenerator.generate_token(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Create admin authenticated API client"""
    from apps.base.auth import JWTTokenGenerator

    token = JWTTokenGenerator.generate_token(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api_client
