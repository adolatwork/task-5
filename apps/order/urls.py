from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.order.views import CustomerProfileView, CustomerViewSet, OrderViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('profile/', CustomerProfileView.as_view(), name='customer-profile'),
    path('', include(router.urls)),
]
