import pytest
from decimal import Decimal
from django.urls import reverse

from apps.order.models import Order, OrderItem, Customer


@pytest.mark.django_db
class TestOrderModel:
    """Test Order model"""

    def test_create_order(self, customer):
        """Test creating an order"""
        order = Order.objects.create(
            customer=customer,
            order_number='TEST-001',
            status=Order.OrderStatus.PENDING,
            shipping_address='Test Address',
            shipping_cost=Decimal('10.00'),
        )

        assert order.customer == customer
        assert order.status == Order.OrderStatus.PENDING
        assert order.shipping_cost == Decimal('10.00')

    def test_order_calculate_totals(self, order):
        """Test order total calculation"""
        assert order.subtotal == Decimal('1050.00')

        expected_tax = Decimal('126.00')
        assert order.tax_amount == expected_tax

        expected_total = Decimal('1050.00') + expected_tax + Decimal('5.00')
        assert order.total_amount == expected_total

    def test_order_can_be_cancelled(self, order):
        """Test order cancellation logic"""
        order.status = Order.OrderStatus.PENDING
        assert order.can_be_cancelled() is True

        order.status = Order.OrderStatus.PROCESSING
        assert order.can_be_cancelled() is True

        order.status = Order.OrderStatus.CONFIRMED
        assert order.can_be_cancelled() is True

        order.status = Order.OrderStatus.COMPLETED
        assert order.can_be_cancelled() is False

        order.status = Order.OrderStatus.CANCELLED
        assert order.can_be_cancelled() is False

    def test_order_can_be_refunded(self, order):
        """Test order refund logic"""
        order.status = Order.OrderStatus.COMPLETED
        assert order.can_be_refunded() is True

        order.status = Order.OrderStatus.PENDING
        assert order.can_be_refunded() is False

    def test_order_str(self, order):
        """Test order string representation"""
        assert str(order) == f"Order {order.order_number} - {order.status}"


@pytest.mark.django_db
class TestOrderAPI:
    """Test Order API endpoints"""

    def test_create_order_authenticated(self, authenticated_client, user):
        """Test creating order as authenticated user"""
        url = reverse('order-list')
        data = {
            'shipping_address': '123 Test Street, Tashkent',
            'shipping_cost': '10.00',
            'payment_method': 'CREDIT_CARD',
            'notes': 'Test order',
            'items': [
                {
                    'product_name': 'Test Product',
                    'product_sku': 'TEST-001',
                    'quantity': 2,
                    'unit_price': '100.00',
                }
            ]
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 201
        assert response.data['status'] == 'PENDING'
        assert response.data['shipping_address'] == '123 Test Street, Tashkent'
        assert len(response.data['items']) == 1
        assert len(response.data['payments']) == 1

        order = Order.objects.get(id=response.data['id'])
        assert order.customer.user == user

    def test_create_order_with_existing_customer(self, authenticated_client, customer):
        """Test creating order with existing customer"""
        url = reverse('order-list')
        data = {
            'customer_id': str(customer.id),
            'shipping_address': '456 Another Street',
            'payment_method': 'PAYPAL',
            'items': [
                {
                    'product_name': 'Another Product',
                    'quantity': 1,
                    'unit_price': '50.00',
                }
            ]
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 201
        assert response.data['customer']['id'] == str(customer.id)

    def test_create_order_guest(self, api_client):
        """Test creating order as guest (no authentication)"""
        url = reverse('order-list')
        data = {
            'customer_email': 'guest@example.com',
            'customer_name': 'Guest User',
            'customer_phone': '998909999999',
            'shipping_address': '789 Guest Street',
            'payment_method': 'CASH',
            'items': [
                {
                    'product_name': 'Guest Product',
                    'quantity': 1,
                    'unit_price': '75.00',
                }
            ]
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == 201
        assert response.data['customer']['email'] == 'guest@example.com'

        order = Order.objects.get(id=response.data['id'])
        assert order.customer.user is None

    def test_create_order_missing_items(self, authenticated_client):
        """Test creating order without items fails"""
        url = reverse('order-list')
        data = {
            'shipping_address': 'Test Address',
            'payment_method': 'CREDIT_CARD',
            'items': []
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 400
        assert 'items' in response.data

    def test_create_order_missing_customer_data(self, api_client):
        """Test creating order without customer data fails for guests"""
        url = reverse('order-list')
        data = {
            'shipping_address': 'Test Address',
            'payment_method': 'CREDIT_CARD',
            'items': [
                {'product_name': 'Product', 'quantity': 1, 'unit_price': '10.00'}
            ]
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == 400

    def test_list_orders(self, authenticated_client, order):
        """Test listing orders"""
        url = reverse('order-list')
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert len(response.data['results']) >= 1

    def test_get_order_detail(self, authenticated_client, order):
        """Test getting order detail"""
        url = reverse('order-detail', kwargs={'pk': order.id})
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert response.data['id'] == str(order.id)
        assert response.data['order_number'] == order.order_number
        assert len(response.data['items']) == 2


@pytest.mark.django_db
class TestOrderActions:
    """Test Order action endpoints"""

    def test_process_payment(self, authenticated_client, order, payment):
        """Test processing payment for an order"""
        url = reverse('order-process-payment', kwargs={'pk': order.id})
        data = {
            'payment_method': 'CREDIT_CARD',
            'payment_gateway': 'stripe',
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 200
        assert response.data['status'] == 'COMPLETED'

        order.refresh_from_db()
        assert order.status == Order.OrderStatus.CONFIRMED

    def test_cancel_order(self, authenticated_client, order):
        """Test canceling an order"""
        url = reverse('order-cancel', kwargs={'pk': order.id})
        data = {'reason': 'Customer requested cancellation'}

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 200
        assert response.data['status'] == 'CANCELLED'
        assert 'Customer requested cancellation' in response.data['notes']

    def test_cancel_completed_order_fails(self, authenticated_client, order):
        """Test canceling a completed order fails"""
        order.status = Order.OrderStatus.COMPLETED
        order.save()

        url = reverse('order-cancel', kwargs={'pk': order.id})
        data = {'reason': 'Test'}

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 400
        assert 'cannot be cancelled' in str(response.data)

    def test_refund_order(self, authenticated_client, order, payment):
        """Test refunding an order"""
        order.status = Order.OrderStatus.COMPLETED
        order.save()

        payment.status = payment.PaymentStatus.COMPLETED
        payment.save()

        url = reverse('order-refund', kwargs={'pk': order.id})
        data = {'reason': 'Product defect'}

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 200
        assert response.data['status'] == 'REFUNDED'
        assert 'Product defect' in response.data['notes']

    def test_partial_refund_order(self, authenticated_client, order, payment):
        """Test partial refund"""
        order.status = Order.OrderStatus.COMPLETED
        order.save()

        payment.status = payment.PaymentStatus.COMPLETED
        payment.save()

        url = reverse('order-refund', kwargs={'pk': order.id})
        data = {
            'reason': 'Partial refund',
            'amount': '50.00'
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 200
        assert 'Partial refund' in response.data['notes']
        assert '50.00' in response.data['notes']

    def test_complete_order(self, authenticated_client, order, payment):
        """Test completing an order"""
        order.status = Order.OrderStatus.CONFIRMED
        order.save()

        url = reverse('order-complete', kwargs={'pk': order.id})
        response = authenticated_client.post(url, format='json')

        assert response.status_code == 200
        assert response.data['status'] == 'COMPLETED'


@pytest.mark.django_db
class TestOrderItemModel:
    """Test OrderItem model"""

    def test_create_order_item(self, order):
        """Test creating order item"""
        item = OrderItem.objects.create(
            order=order,
            product_name='Test Item',
            product_sku='ITEM-001',
            quantity=3,
            unit_price=Decimal('50.00'),
        )

        assert item.total_price == Decimal('150.00')

    def test_order_item_str(self, order):
        """Test order item string representation"""
        item = OrderItem.objects.create(
            order=order,
            product_name='Test Product',
            quantity=5,
            unit_price=Decimal('10.00'),
        )

        assert str(item) == 'Test Product x 5'
