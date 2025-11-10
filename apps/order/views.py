from rest_framework import status, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiExample
from django.utils.translation import gettext_lazy as _

from apps.order.models import Customer, Order
from apps.order.serializers import (
    CustomerSerializer,
    OrderSerializer,
    OrderCreateSerializer,
    PaymentProcessSerializer,
    OrderCancelSerializer,
    OrderRefundSerializer,
    PaymentSerializer,
    OrderErrorSerializer,
)
from apps.order.services import (
    OrderService,
    OrderProcessingError,
    PaymentProcessingError,
)


class CustomerProfileView(APIView):
    """
    Get or create customer profile for authenticated user
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='get_my_profile',
        summary='Get My Customer Profile',
        description='Get or create customer profile for the authenticated user',
        responses={
            200: CustomerSerializer,
        }
    )
    def get(self, request):
        """Get or create customer profile"""
        customer = OrderService.get_or_create_customer_from_user(request.user)
        serializer = CustomerSerializer(customer)
        return Response(serializer.data)

    @extend_schema(
        operation_id='update_my_profile',
        summary='Update My Customer Profile',
        description='Update customer profile for the authenticated user',
        request=CustomerSerializer,
        responses={
            200: CustomerSerializer,
            400: OrderErrorSerializer,
        }
    )
    def put(self, request):
        """Update customer profile"""
        customer = OrderService.get_or_create_customer_from_user(request.user)
        serializer = CustomerSerializer(customer, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        operation_id='partial_update_my_profile',
        summary='Partially Update My Customer Profile',
        description='Partially update customer profile for the authenticated user',
        request=CustomerSerializer,
        responses={
            200: CustomerSerializer,
            400: OrderErrorSerializer,
        }
    )
    def patch(self, request):
        """Partially update customer profile"""
        customer = OrderService.get_or_create_customer_from_user(request.user)
        serializer = CustomerSerializer(customer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Customer CRUD operations
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter customers - staff can see all, users see only their own"""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated and not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        """Automatically link customer to authenticated user when creating"""
        existing_customer = Customer.objects.filter(user=self.request.user).first()
        if existing_customer:
            raise serializers.ValidationError({
                'user': _('You already have a customer profile. Use PUT/PATCH to update it.')
            })

        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Ensure user link is maintained during update"""
        serializer.save(user=self.request.user)


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Order operations with atomic transaction support
    """
    queryset = Order.objects.all().prefetch_related('items', 'payments', 'customer')
    serializer_class = OrderSerializer

    def get_permissions(self):
        """
        Custom permissions:
        - POST (create): Allow anyone (guest checkout)
        - GET/PUT/PATCH/DELETE: Require authentication
        """
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Filter orders based on user permissions"""
        queryset = super().get_queryset()

        if self.request.user.is_staff:
            return queryset.order_by('-created_at')

        if self.request.user.is_authenticated:
            return queryset.filter(
                customer__user=self.request.user
            ).order_by('-created_at')

        return queryset.none()

    @extend_schema(
        operation_id='create_order',
        summary='Create Order',
        description='Create a new order with items atomically. All operations succeed or rollback.',
        request=OrderCreateSerializer,
        responses={
            201: OrderSerializer,
            400: OrderErrorSerializer,
        },
        examples=[
            OpenApiExample(
                'Create Order Request',
                summary='Example order creation',
                value={
                    'customer_email': 'john@example.com',
                    'customer_name': 'John Doe',
                    'customer_phone': '998901234567',
                    'shipping_address': '123 Main St, Tashkent, Uzbekistan',
                    'shipping_cost': '5.00',
                    'notes': 'Please deliver in the morning',
                    'payment_method': 'CREDIT_CARD',
                    'items': [
                        {
                            'product_name': 'Laptop',
                            'product_sku': 'LAP-001',
                            'quantity': 1,
                            'unit_price': '1000.00'
                        },
                        {
                            'product_name': 'Mouse',
                            'product_sku': 'MOU-001',
                            'quantity': 2,
                            'unit_price': '25.00'
                        }
                    ]
                },
                request_only=True
            )
        ]
    )
    def create(self, request):
        """Create order with atomic transaction"""
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            customer_id = serializer.validated_data.get('customer_id')

            if not customer_id and request.user.is_authenticated:
                existing_customer = OrderService.get_or_create_customer_from_user(request.user)
                if existing_customer:
                    customer_id = existing_customer.id

            customer_data = {
                'customer_email': serializer.validated_data.get('customer_email'),
                'customer_name': serializer.validated_data.get('customer_name'),
                'customer_phone': serializer.validated_data.get('customer_phone'),
            } if not customer_id else None

            order = OrderService.create_order(
                customer_id=customer_id,
                customer_data=customer_data,
                items_data=serializer.validated_data['items'],
                shipping_address=serializer.validated_data['shipping_address'],
                shipping_cost=serializer.validated_data.get('shipping_cost'),
                notes=serializer.validated_data.get('notes', ''),
                payment_method=serializer.validated_data['payment_method'],
                user=request.user,
            )

            response_serializer = OrderSerializer(order)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except OrderProcessingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        operation_id='process_payment',
        summary='Process Payment',
        description='Process payment for an order with race condition prevention using select_for_update',
        request=PaymentProcessSerializer,
        responses={
            200: PaymentSerializer,
            400: OrderErrorSerializer,
        }
    )
    @action(detail=True, methods=['post'], url_path='process-payment')
    def process_payment(self, request, pk=None):
        """Process payment for an order"""
        order = self.get_object()

        serializer = PaymentProcessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = OrderService.process_payment(
                order_id=str(order.id),
                payment_gateway=serializer.validated_data.get('payment_gateway', '')
            )

            response_serializer = PaymentSerializer(payment)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except PaymentProcessingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        operation_id='cancel_order',
        summary='Cancel Order',
        description='Cancel an order with atomic transaction',
        request=OrderCancelSerializer,
        responses={
            200: OrderSerializer,
            400: OrderErrorSerializer,
        }
    )
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel an order"""
        order = self.get_object()

        serializer = OrderCancelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated_order = OrderService.cancel_order(
                order_id=str(order.id),
                reason=serializer.validated_data.get('reason', '')
            )

            response_serializer = OrderSerializer(updated_order)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except OrderProcessingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        operation_id='refund_order',
        summary='Refund Order',
        description='Refund an order (full or partial) with atomic transaction',
        request=OrderRefundSerializer,
        responses={
            200: OrderSerializer,
            400: OrderErrorSerializer,
        }
    )
    @action(detail=True, methods=['post'], url_path='refund')
    def refund(self, request, pk=None):
        """Refund an order"""
        order = self.get_object()

        serializer = OrderRefundSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated_order = OrderService.refund_order(
                order_id=str(order.id),
                reason=serializer.validated_data['reason'],
                amount=serializer.validated_data.get('amount')
            )

            response_serializer = OrderSerializer(updated_order)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except OrderProcessingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        operation_id='complete_order',
        summary='Complete Order',
        description='Mark an order as completed',
        responses={
            200: OrderSerializer,
            400: OrderErrorSerializer,
        }
    )
    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        """Complete an order"""
        order = self.get_object()

        try:
            updated_order = OrderService.complete_order(order_id=str(order.id))

            response_serializer = OrderSerializer(updated_order)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except OrderProcessingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
