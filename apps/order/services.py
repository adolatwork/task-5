import uuid
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional

from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.order.models import Customer, Order, OrderItem, Payment


class OrderProcessingError(Exception):
    """Custom exception for order processing errors"""
    pass


class PaymentProcessingError(Exception):
    """Custom exception for payment processing errors"""
    pass


class OrderService:
    """
    Service class for handling order processing with atomic transactions
    """

    @staticmethod
    def get_or_create_customer_from_user(user) -> Optional[Customer]:
        """
        Get or create customer profile for authenticated user

        Args:
            user: Django User instance

        Returns:
            Customer instance
        """
        if not user or not user.is_authenticated:
            return None

        try:
            return Customer.objects.get(user=user)
        except Customer.DoesNotExist:
            return Customer.objects.create(
                user=user,
                email=user.email if user.email else f"{user.phone_number}@placeholder.com",
                full_name=user.full_name if hasattr(user, 'full_name') else f"{user.first_name} {user.last_name}".strip(),
                phone_number=user.phone_number if hasattr(user, 'phone_number') else '',
            )

    @staticmethod
    def generate_order_number() -> str:
        """Generate unique order number"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = str(uuid.uuid4().hex[:6]).upper()
        return f"ORD-{timestamp}-{random_suffix}"

    @staticmethod
    def generate_transaction_id() -> str:
        """Generate unique transaction ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = str(uuid.uuid4().hex[:8]).upper()
        return f"TXN-{timestamp}-{random_suffix}"

    @staticmethod
    @transaction.atomic
    def create_order(
        customer_id: Optional[str],
        customer_data: Optional[Dict],
        items_data: List[Dict],
        shipping_address: str,
        shipping_cost: Decimal = Decimal('0.00'),
        notes: str = '',
        payment_method: str = Payment.PaymentMethod.CREDIT_CARD,
        user=None,
    ) -> Order:
        """
        Create order with items atomically

        This method uses database transactions to ensure all-or-nothing behavior.
        If any step fails, the entire transaction is rolled back.

        Args:
            customer_id: Existing customer ID or None
            customer_data: New customer data if customer_id is None
            items_data: List of order items
            shipping_address: Shipping address
            shipping_cost: Shipping cost
            notes: Order notes
            payment_method: Payment method

        Returns:
            Created Order instance

        Raises:
            OrderProcessingError: If order creation fails
        """
        try:
            if customer_id:
                try:
                    customer = Customer.objects.select_for_update().get(id=customer_id)
                except Customer.DoesNotExist:
                    raise OrderProcessingError(_('Customer not found'))
            else:
                if not customer_data:
                    raise OrderProcessingError(_('Customer data required'))

                customer = Customer.objects.create(
                    user=user if user and user.is_authenticated else None,
                    email=customer_data.get('customer_email'),
                    full_name=customer_data.get('customer_name'),
                    phone_number=customer_data.get('customer_phone'),
                )

            order_number = OrderService.generate_order_number()
            order = Order.objects.create(
                customer=customer,
                order_number=order_number,
                status=Order.OrderStatus.PENDING,
                shipping_address=shipping_address,
                shipping_cost=shipping_cost,
                notes=notes,
            )

            if not items_data:
                raise OrderProcessingError(_('At least one order item is required'))

            for item_data in items_data:
                unit_price = Decimal(str(item_data['unit_price']))
                quantity = int(item_data['quantity'])
                total_price = unit_price * quantity

                OrderItem.objects.create(
                    order=order,
                    product_name=item_data['product_name'],
                    product_sku=item_data.get('product_sku', ''),
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                    metadata=item_data.get('metadata', {}),
                )

            order.calculate_totals()
            order.save()

            transaction_id = OrderService.generate_transaction_id()
            payment = Payment.objects.create(
                order=order,
                transaction_id=transaction_id,
                payment_method=payment_method,
                amount=order.total_amount,
                status=Payment.PaymentStatus.PENDING,
            )

            return order

        except ValidationError as e:
            raise OrderProcessingError(str(e))
        except Exception as e:
            raise OrderProcessingError(f'Order creation failed: {str(e)}')

    @staticmethod
    @transaction.atomic
    def process_payment(order_id: str, payment_gateway: str = '') -> Payment:
        """
        Process payment for an order with race condition prevention

        Uses select_for_update() to lock the order row during payment processing,
        preventing concurrent payment attempts on the same order.

        Args:
            order_id: Order ID
            payment_gateway: Payment gateway identifier

        Returns:
            Updated Payment instance

        Raises:
            PaymentProcessingError: If payment processing fails
        """
        try:
            order = Order.objects.select_for_update().get(id=order_id)

            if order.status not in [Order.OrderStatus.PENDING, Order.OrderStatus.PROCESSING]:
                raise PaymentProcessingError(
                    _('Order cannot be processed in current status: {}').format(order.status)
                )

            payment = Payment.objects.select_for_update().filter(
                order=order,
                status=Payment.PaymentStatus.PENDING
            ).first()

            if not payment:
                raise PaymentProcessingError(_('No pending payment found for this order'))

            order.status = Order.OrderStatus.PROCESSING
            order.save(update_fields=['status', 'updated_at'])

            payment.status = Payment.PaymentStatus.PROCESSING
            payment.payment_gateway = payment_gateway
            payment.save(update_fields=['status', 'payment_gateway', 'updated_at'])

            payment_success = OrderService._simulate_payment_processing(payment)

            if payment_success:
                payment.status = Payment.PaymentStatus.COMPLETED
                payment.processed_at = timezone.now()
                payment.gateway_response = {'status': 'success', 'message': 'Payment processed successfully'}
                payment.save(update_fields=['status', 'processed_at', 'gateway_response', 'updated_at'])

                order.status = Order.OrderStatus.CONFIRMED
                order.version = F('version') + 1
                order.save(update_fields=['status', 'version', 'updated_at'])

            else:
                payment.status = Payment.PaymentStatus.FAILED
                payment.error_message = 'Payment processing failed'
                payment.gateway_response = {'status': 'failed', 'message': 'Payment declined'}
                payment.save(update_fields=['status', 'error_message', 'gateway_response', 'updated_at'])

                order.status = Order.OrderStatus.FAILED
                order.save(update_fields=['status', 'updated_at'])

                raise PaymentProcessingError(_('Payment processing failed'))

            payment.refresh_from_db()
            order.refresh_from_db()

            return payment

        except Order.DoesNotExist:
            raise PaymentProcessingError(_('Order not found'))
        except Exception as e:
            raise PaymentProcessingError(f'Payment processing error: {str(e)}')

    @staticmethod
    def _simulate_payment_processing(payment: Payment) -> bool:
        """
        Simulate payment processing (placeholder for real payment gateway)

        In real implementation, this would integrate with payment gateways like:
        - Stripe
        - PayPal
        - Square
        - etc.
        """
        return True

    @staticmethod
    @transaction.atomic
    def cancel_order(order_id: str, reason: str = '') -> Order:
        """
        Cancel an order with race condition prevention

        Args:
            order_id: Order ID
            reason: Cancellation reason

        Returns:
            Updated Order instance

        Raises:
            OrderProcessingError: If cancellation fails
        """
        try:
            order = Order.objects.select_for_update().get(id=order_id)

            if not order.can_be_cancelled():
                raise OrderProcessingError(
                    _('Order cannot be cancelled in current status: {}').format(order.status)
                )

            order.status = Order.OrderStatus.CANCELLED
            if reason:
                order.notes += f'\nCancellation reason: {reason}'
            order.version = F('version') + 1
            order.save(update_fields=['status', 'notes', 'version', 'updated_at'])

            Payment.objects.filter(
                order=order,
                status__in=[Payment.PaymentStatus.PENDING, Payment.PaymentStatus.PROCESSING]
            ).update(
                status=Payment.PaymentStatus.CANCELLED,
                error_message='Order cancelled'
            )

            order.refresh_from_db()
            return order

        except Order.DoesNotExist:
            raise OrderProcessingError(_('Order not found'))
        except Exception as e:
            raise OrderProcessingError(f'Order cancellation failed: {str(e)}')

    @staticmethod
    @transaction.atomic
    def refund_order(order_id: str, reason: str, amount: Optional[Decimal] = None) -> Order:
        """
        Refund an order (full or partial)

        Args:
            order_id: Order ID
            reason: Refund reason
            amount: Refund amount (None for full refund)

        Returns:
            Updated Order instance

        Raises:
            OrderProcessingError: If refund fails
        """
        try:
            order = Order.objects.select_for_update().get(id=order_id)

            if not order.can_be_refunded():
                raise OrderProcessingError(
                    _('Order cannot be refunded in current status: {}').format(order.status)
                )

            refund_amount = amount if amount else order.total_amount
            if refund_amount > order.total_amount:
                raise OrderProcessingError(_('Refund amount cannot exceed order total'))

            completed_payment = Payment.objects.filter(
                order=order,
                status=Payment.PaymentStatus.COMPLETED
            ).first()

            if not completed_payment:
                raise OrderProcessingError(_('No completed payment found for this order'))

            refund_transaction_id = OrderService.generate_transaction_id()
            Payment.objects.create(
                order=order,
                transaction_id=refund_transaction_id,
                payment_method=completed_payment.payment_method,
                amount=-refund_amount,
                currency=completed_payment.currency,
                status=Payment.PaymentStatus.REFUNDED,
                payment_gateway=completed_payment.payment_gateway,
                gateway_response={'status': 'refunded', 'reason': reason},
                processed_at=timezone.now(),
            )

            order.status = Order.OrderStatus.REFUNDED
            order.notes += f'\nRefund reason: {reason}\nRefund amount: {refund_amount}'
            order.version = F('version') + 1
            order.save(update_fields=['status', 'notes', 'version', 'updated_at'])

            order.refresh_from_db()
            return order

        except Order.DoesNotExist:
            raise OrderProcessingError(_('Order not found'))
        except Exception as e:
            raise OrderProcessingError(f'Order refund failed: {str(e)}')

    @staticmethod
    @transaction.atomic
    def complete_order(order_id: str) -> Order:
        """
        Mark order as completed

        Args:
            order_id: Order ID

        Returns:
            Updated Order instance

        Raises:
            OrderProcessingError: If completion fails
        """
        try:
            order = Order.objects.select_for_update().get(id=order_id)

            if order.status != Order.OrderStatus.CONFIRMED:
                raise OrderProcessingError(
                    _('Only confirmed orders can be completed')
                )

            order.status = Order.OrderStatus.COMPLETED
            order.version = F('version') + 1
            order.save(update_fields=['status', 'version', 'updated_at'])

            order.refresh_from_db()
            return order

        except Order.DoesNotExist:
            raise OrderProcessingError(_('Order not found'))
        except Exception as e:
            raise OrderProcessingError(f'Order completion failed: {str(e)}')
