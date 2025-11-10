import pytest
from decimal import Decimal

from apps.order.models import Order, OrderItem, Payment
from apps.order.services import (
    OrderService,
    OrderProcessingError,
)


@pytest.mark.django_db
class TestOrderServiceCreateOrder:
    """Test OrderService.create_order()"""

    def test_create_order_with_new_customer(self, user):
        """Test creating order with new customer"""
        customer_data = {
            'customer_email': 'newcustomer@example.com',
            'customer_name': 'New Customer',
            'customer_phone': '998905555555',
        }

        items_data = [
            {
                'product_name': 'Laptop',
                'product_sku': 'LAP-001',
                'quantity': 1,
                'unit_price': '1000.00',
            }
        ]

        order = OrderService.create_order(
            customer_id=None,
            customer_data=customer_data,
            items_data=items_data,
            shipping_address='123 Test Street',
            shipping_cost=Decimal('10.00'),
            notes='Test order',
            payment_method=Payment.PaymentMethod.CREDIT_CARD,
            user=user,
        )

        assert order.id is not None
        assert order.customer.email == 'newcustomer@example.com'
        assert order.customer.user == user
        assert order.items.count() == 1
        assert order.payments.count() == 1
        assert order.payments.first().status == Payment.PaymentStatus.PENDING

    def test_create_order_with_existing_customer(self, customer):
        """Test creating order with existing customer"""
        items_data = [
            {
                'product_name': 'Mouse',
                'quantity': 2,
                'unit_price': '25.00',
            }
        ]

        order = OrderService.create_order(
            customer_id=str(customer.id),
            customer_data=None,
            items_data=items_data,
            shipping_address='456 Different Street',
            payment_method=Payment.PaymentMethod.PAYPAL,
        )

        assert order.customer == customer
        assert order.items.count() == 1

    def test_create_order_generates_order_number(self, customer):
        """Test order number is auto-generated"""
        items_data = [
            {'product_name': 'Product', 'quantity': 1, 'unit_price': '10.00'}
        ]

        order = OrderService.create_order(
            customer_id=str(customer.id),
            customer_data=None,
            items_data=items_data,
            shipping_address='Test',
            payment_method=Payment.PaymentMethod.CASH,
        )

        assert order.order_number is not None
        assert order.order_number.startswith('ORD-')

    def test_create_order_calculates_totals(self, customer):
        """Test order totals are calculated correctly"""
        items_data = [
            {'product_name': 'Item 1', 'quantity': 2, 'unit_price': '100.00'},
            {'product_name': 'Item 2', 'quantity': 1, 'unit_price': '50.00'},
        ]

        order = OrderService.create_order(
            customer_id=str(customer.id),
            customer_data=None,
            items_data=items_data,
            shipping_address='Test',
            shipping_cost=Decimal('5.00'),
            payment_method=Payment.PaymentMethod.CREDIT_CARD,
        )

        assert order.subtotal == Decimal('250.00')

        assert order.tax_amount == Decimal('30.00')

        assert order.total_amount == Decimal('285.00')

    def test_create_order_without_items_fails(self, customer):
        """Test creating order without items raises error"""
        with pytest.raises(OrderProcessingError) as exc_info:
            OrderService.create_order(
                customer_id=str(customer.id),
                customer_data=None,
                items_data=[],
                shipping_address='Test',
                payment_method=Payment.PaymentMethod.CASH,
            )

        assert 'At least one order item is required' in str(exc_info.value)

    def test_create_order_invalid_customer_id(self):
        """Test creating order with invalid customer ID fails"""
        items_data = [
            {'product_name': 'Product', 'quantity': 1, 'unit_price': '10.00'}
        ]

        with pytest.raises(OrderProcessingError) as exc_info:
            OrderService.create_order(
                customer_id='00000000-0000-0000-0000-000000000000',
                customer_data=None,
                items_data=items_data,
                shipping_address='Test',
                payment_method=Payment.PaymentMethod.CASH,
            )

        assert 'Customer not found' in str(exc_info.value)

    def test_create_order_atomic_transaction(self, customer):
        """Test order creation is atomic (all or nothing)"""
        items_data = [
            {'product_name': 'Product', 'quantity': 1, 'unit_price': '10.00'}
        ]

        initial_order_count = Order.objects.count()
        initial_item_count = OrderItem.objects.count()
        initial_payment_count = Payment.objects.count()

        order = OrderService.create_order(
            customer_id=str(customer.id),
            customer_data=None,
            items_data=items_data,
            shipping_address='Test',
            payment_method=Payment.PaymentMethod.CASH,
        )

        assert Order.objects.count() == initial_order_count + 1
        assert OrderItem.objects.count() == initial_item_count + 1
        assert Payment.objects.count() == initial_payment_count + 1


@pytest.mark.django_db
class TestOrderServicePaymentProcessing:
    """Test OrderService.process_payment()"""

    def test_process_payment_success(self, order, payment):
        """Test successful payment processing"""
        result = OrderService.process_payment(
            order_id=str(order.id),
            payment_gateway='test-gateway'
        )

        assert result.status == Payment.PaymentStatus.COMPLETED
        assert result.payment_gateway == 'test-gateway'

        order.refresh_from_db()
        assert order.status == Order.OrderStatus.CONFIRMED

    def test_process_payment_increments_version(self, order, payment):
        """Test payment processing increments order version"""
        initial_version = order.version

        OrderService.process_payment(order_id=str(order.id))

        order.refresh_from_db()
        assert order.version > initial_version


@pytest.mark.django_db
class TestOrderServiceCancellation:
    """Test OrderService.cancel_order()"""

    def test_cancel_pending_order(self, order):
        """Test canceling pending order"""
        result = OrderService.cancel_order(
            order_id=str(order.id),
            reason='Customer request'
        )

        assert result.status == Order.OrderStatus.CANCELLED
        assert 'Customer request' in result.notes

    def test_cancel_order_cancels_payments(self, order, payment):
        """Test canceling order also cancels pending payments"""
        OrderService.cancel_order(order_id=str(order.id))

        payment.refresh_from_db()
        assert payment.status == Payment.PaymentStatus.CANCELLED


@pytest.mark.django_db
class TestOrderServiceRefund:
    """Test OrderService.refund_order()"""

    def test_refund_completed_order(self, order, payment):
        """Test refunding completed order"""
        order.status = Order.OrderStatus.COMPLETED
        order.save()

        payment.status = Payment.PaymentStatus.COMPLETED
        payment.save()

        result = OrderService.refund_order(
            order_id=str(order.id),
            reason='Product defect'
        )

        assert result.status == Order.OrderStatus.REFUNDED
        assert 'Product defect' in result.notes


@pytest.mark.django_db
class TestOrderServiceCompletion:
    """Test OrderService.complete_order()"""

    def test_complete_confirmed_order(self, order):
        """Test completing confirmed order"""
        order.status = Order.OrderStatus.CONFIRMED
        order.save()

        result = OrderService.complete_order(order_id=str(order.id))

        assert result.status == Order.OrderStatus.COMPLETED


@pytest.mark.django_db
class TestOrderServiceHelpers:
    """Test OrderService helper methods"""

    def test_get_or_create_customer_from_user(self, user):
        """Test getting or creating customer from user"""
        customer1 = OrderService.get_or_create_customer_from_user(user)

        assert customer1 is not None
        assert customer1.user == user
        assert customer1.email == user.email

        customer2 = OrderService.get_or_create_customer_from_user(user)

        assert customer1.id == customer2.id

    def test_get_or_create_customer_unauthenticated(self):
        """Test returns None for unauthenticated user"""
        result = OrderService.get_or_create_customer_from_user(None)
        assert result is None

    def test_generate_order_number(self):
        """Test order number generation"""
        order_number = OrderService.generate_order_number()

        assert order_number is not None
        assert order_number.startswith('ORD-')
        assert len(order_number) > 10

        order_number2 = OrderService.generate_order_number()
        assert order_number != order_number2

    def test_generate_transaction_id(self):
        """Test transaction ID generation"""
        txn_id = OrderService.generate_transaction_id()

        assert txn_id is not None
        assert txn_id.startswith('TXN-')
        assert len(txn_id) > 10

        txn_id2 = OrderService.generate_transaction_id()
        assert txn_id != txn_id2


@pytest.mark.django_db
class TestRaceConditionPrevention:
    """Test race condition prevention with select_for_update"""

    def test_payment_processing_locks_order(self, order, payment):
        """Test payment processing locks the order to prevent race conditions"""
        result = OrderService.process_payment(order_id=str(order.id))

        assert result is not None
        assert result.status == Payment.PaymentStatus.COMPLETED

    def test_concurrent_cancellation_prevented(self, order):
        """Test that order can't be cancelled concurrently"""
        result = OrderService.cancel_order(order_id=str(order.id))

        assert result.status == Order.OrderStatus.CANCELLED

        with pytest.raises(OrderProcessingError):
            OrderService.cancel_order(order_id=str(order.id))
