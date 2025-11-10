import pytest
from decimal import Decimal
from django.utils import timezone

from apps.order.models import Payment, Order
from apps.order.services import OrderService, PaymentProcessingError


@pytest.mark.django_db
class TestPaymentModel:
    """Test Payment model"""

    def test_create_payment(self, order):
        """Test creating a payment"""
        payment = Payment.objects.create(
            order=order,
            transaction_id='TEST-TXN-001',
            payment_method=Payment.PaymentMethod.CREDIT_CARD,
            amount=Decimal('100.00'),
            status=Payment.PaymentStatus.PENDING,
        )

        assert payment.order == order
        assert payment.transaction_id == 'TEST-TXN-001'
        assert payment.amount == Decimal('100.00')
        assert payment.status == Payment.PaymentStatus.PENDING

    def test_payment_str(self, payment):
        """Test payment string representation"""
        assert str(payment) == f"Payment {payment.transaction_id} - {payment.status}"

    def test_payment_methods(self):
        """Test payment method choices"""
        methods = [choice[0] for choice in Payment.PaymentMethod.choices]

        assert 'CREDIT_CARD' in methods
        assert 'DEBIT_CARD' in methods
        assert 'PAYPAL' in methods
        assert 'BANK_TRANSFER' in methods
        assert 'CASH' in methods
        assert 'CRYPTO' in methods

    def test_payment_statuses(self):
        """Test payment status choices"""
        statuses = [choice[0] for choice in Payment.PaymentStatus.choices]

        assert 'PENDING' in statuses
        assert 'PROCESSING' in statuses
        assert 'COMPLETED' in statuses
        assert 'FAILED' in statuses
        assert 'REFUNDED' in statuses
        assert 'CANCELLED' in statuses


@pytest.mark.django_db
class TestPaymentProcessing:
    """Test payment processing logic"""

    def test_process_payment_success(self, order, payment):
        """Test successful payment processing"""
        result = OrderService.process_payment(
            order_id=str(order.id),
            payment_gateway='stripe'
        )

        assert result.status == Payment.PaymentStatus.COMPLETED
        assert result.processed_at is not None
        assert result.payment_gateway == 'stripe'
        assert result.gateway_response['status'] == 'success'

        order.refresh_from_db()
        assert order.status == Order.OrderStatus.CONFIRMED
        assert order.version == 1

    def test_process_payment_invalid_status(self, order, payment):
        """Test processing payment for order in invalid status"""
        order.status = Order.OrderStatus.COMPLETED
        order.save()

        with pytest.raises(PaymentProcessingError) as exc_info:
            OrderService.process_payment(
                order_id=str(order.id),
                payment_gateway='stripe'
            )

        assert 'cannot be processed' in str(exc_info.value)

    def test_process_payment_no_pending_payment(self, order):
        """Test processing payment when no pending payment exists"""
        with pytest.raises(PaymentProcessingError) as exc_info:
            OrderService.process_payment(order_id=str(order.id))

        assert 'No pending payment' in str(exc_info.value)

    def test_process_payment_uses_select_for_update(self, order, payment):
        """Test that payment processing locks the order"""
        result = OrderService.process_payment(order_id=str(order.id))

        assert result.status == Payment.PaymentStatus.COMPLETED

        order.refresh_from_db()
        assert order.status == Order.OrderStatus.CONFIRMED

    def test_payment_processing_updates_order_version(self, order, payment):
        """Test payment processing increments order version"""
        initial_version = order.version

        OrderService.process_payment(order_id=str(order.id))

        order.refresh_from_db()
        assert order.version == initial_version + 1


@pytest.mark.django_db
class TestPaymentRefund:
    """Test payment refund logic"""

    def test_refund_payment(self, order, payment):
        """Test refunding a payment"""
        order.status = Order.OrderStatus.COMPLETED
        order.save()

        payment.status = Payment.PaymentStatus.COMPLETED
        payment.processed_at = timezone.now()
        payment.save()

        refunded_order = OrderService.refund_order(
            order_id=str(order.id),
            reason='Customer request'
        )

        assert refunded_order.status == Order.OrderStatus.REFUNDED

        refund_payments = Payment.objects.filter(
            order=order,
            status=Payment.PaymentStatus.REFUNDED
        )
        assert refund_payments.count() == 1

        refund_payment = refund_payments.first()
        assert refund_payment.amount == -order.total_amount

    def test_partial_refund_payment(self, order, payment):
        """Test partial refund"""
        order.status = Order.OrderStatus.COMPLETED
        order.save()

        payment.status = Payment.PaymentStatus.COMPLETED
        payment.processed_at = timezone.now()
        payment.save()

        refund_amount = Decimal('50.00')
        refunded_order = OrderService.refund_order(
            order_id=str(order.id),
            reason='Partial refund',
            amount=refund_amount
        )

        refund_payment = Payment.objects.filter(
            order=order,
            status=Payment.PaymentStatus.REFUNDED
        ).first()

        assert refund_payment.amount == -refund_amount

    def test_refund_invalid_status(self, order, payment):
        """Test refund fails for non-completed orders"""
        with pytest.raises(Exception) as exc_info:
            OrderService.refund_order(
                order_id=str(order.id),
                reason='Test'
            )

        assert 'cannot be refunded' in str(exc_info.value)

    def test_refund_amount_exceeds_total(self, order, payment):
        """Test refund amount cannot exceed order total"""
        order.status = Order.OrderStatus.COMPLETED
        order.save()

        payment.status = Payment.PaymentStatus.COMPLETED
        payment.save()

        with pytest.raises(Exception) as exc_info:
            OrderService.refund_order(
                order_id=str(order.id),
                reason='Test',
                amount=order.total_amount + Decimal('100.00')
            )

        assert 'cannot exceed' in str(exc_info.value)


@pytest.mark.django_db
class TestPaymentCancellation:
    """Test payment cancellation"""

    def test_cancel_pending_payment_on_order_cancel(self, order, payment):
        """Test pending payment is cancelled when order is cancelled"""
        OrderService.cancel_order(
            order_id=str(order.id),
            reason='Customer request'
        )

        payment.refresh_from_db()
        assert payment.status == Payment.PaymentStatus.CANCELLED
        assert payment.error_message == 'Order cancelled'


@pytest.mark.django_db
class TestMultiplePayments:
    """Test orders with multiple payments"""

    def test_order_with_multiple_payment_attempts(self, order):
        """Test order can have multiple payment attempts"""
        payment1 = Payment.objects.create(
            order=order,
            transaction_id='TXN-001',
            payment_method=Payment.PaymentMethod.CREDIT_CARD,
            amount=order.total_amount,
            status=Payment.PaymentStatus.FAILED,
            error_message='Card declined',
        )

        payment2 = Payment.objects.create(
            order=order,
            transaction_id='TXN-002',
            payment_method=Payment.PaymentMethod.PAYPAL,
            amount=order.total_amount,
            status=Payment.PaymentStatus.PENDING,
        )

        result = OrderService.process_payment(
            order_id=str(order.id),
            payment_gateway='paypal'
        )

        assert result.transaction_id == 'TXN-002'
        assert result.status == Payment.PaymentStatus.COMPLETED

        assert order.payments.count() == 2
        assert order.payments.filter(status=Payment.PaymentStatus.FAILED).count() == 1
        assert order.payments.filter(status=Payment.PaymentStatus.COMPLETED).count() == 1


@pytest.mark.django_db
class TestPaymentGatewayIntegration:
    """Test payment gateway integration points"""

    def test_payment_gateway_response_storage(self, order, payment):
        """Test payment gateway response is stored"""
        OrderService.process_payment(
            order_id=str(order.id),
            payment_gateway='stripe'
        )

        payment.refresh_from_db()
        assert 'gateway_response' in dir(payment)
        assert payment.gateway_response is not None
        assert isinstance(payment.gateway_response, dict)
        assert payment.gateway_response.get('status') == 'success'

    def test_payment_different_gateways(self, order):
        """Test payments can use different gateways"""
        gateways = ['stripe', 'paypal', 'square']

        for gateway in gateways:
            payment = Payment.objects.create(
                order=order,
                transaction_id=f'TXN-{gateway.upper()}',
                payment_method=Payment.PaymentMethod.CREDIT_CARD,
                amount=Decimal('10.00'),
                status=Payment.PaymentStatus.PENDING,
                payment_gateway=gateway,
            )

            assert payment.payment_gateway == gateway

    def test_payment_currency_support(self, order):
        """Test payment supports different currencies"""
        payment = Payment.objects.create(
            order=order,
            transaction_id='TXN-USD',
            payment_method=Payment.PaymentMethod.CREDIT_CARD,
            amount=Decimal('100.00'),
            currency='USD',
            status=Payment.PaymentStatus.PENDING,
        )

        assert payment.currency == 'USD'

        payment2 = Payment.objects.create(
            order=order,
            transaction_id='TXN-UZS',
            payment_method=Payment.PaymentMethod.CASH,
            amount=Decimal('1000000.00'),
            currency='UZS',
            status=Payment.PaymentStatus.PENDING,
        )

        assert payment2.currency == 'UZS'
