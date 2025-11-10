import pytest
from django.urls import reverse

from apps.order.models import Customer


@pytest.mark.django_db
class TestCustomerModel:
    """Test Customer model"""

    def test_create_customer_with_user(self, user):
        """Test creating customer with user link"""
        customer = Customer.objects.create(
            user=user,
            email='test@example.com',
            full_name='Test User',
            phone_number='998901234567',
            address='123 Main St',
            city='Tashkent',
        )

        assert customer.user == user
        assert customer.email == 'test@example.com'
        assert customer.full_name == 'Test User'
        assert str(customer) == 'Test User (test@example.com)'

    def test_create_guest_customer(self):
        """Test creating customer without user link"""
        customer = Customer.objects.create(
            email='guest@example.com',
            full_name='Guest User',
            phone_number='998909999999',
        )

        assert customer.user is None
        assert customer.email == 'guest@example.com'

    def test_customer_phone_validation(self):
        """Test customer phone number validation"""
        customer = Customer(
            email='test@example.com',
            full_name='Test User',
            phone_number='invalid-phone',
        )

        with pytest.raises(Exception):
            customer.full_clean()


@pytest.mark.django_db
class TestCustomerAPI:
    """Test Customer API endpoints"""

    def test_create_customer_authenticated(self, authenticated_client, user):
        """Test creating customer when authenticated"""
        url = reverse('customer-list')
        data = {
            'email': 'newcustomer@example.com',
            'full_name': 'New Customer',
            'phone_number': '998905555555',
            'address': '789 New Street',
            'city': 'Tashkent',
            'country': 'Uzbekistan',
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 201
        assert response.data['email'] == 'newcustomer@example.com'
        assert response.data['user_id'] == str(user.id)
        assert response.data['user_phone'] == user.phone_number

        customer = Customer.objects.get(id=response.data['id'])
        assert customer.user == user

    def test_create_customer_duplicate_user(self, authenticated_client, customer):
        """Test creating second customer for same user fails"""
        url = reverse('customer-list')
        data = {
            'email': 'another@example.com',
            'full_name': 'Another Customer',
            'phone_number': '998906666666',
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == 400
        assert 'already have a customer profile' in str(response.data)

    def test_list_customers_authenticated(self, authenticated_client, customer):
        """Test listing customers shows only own customer"""
        url = reverse('customer-list')
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(customer.id)

    def test_get_customer_detail(self, authenticated_client, customer):
        """Test getting customer detail"""
        url = reverse('customer-detail', kwargs={'pk': customer.id})
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert response.data['id'] == str(customer.id)
        assert response.data['full_name'] == customer.full_name

    def test_update_customer(self, authenticated_client, customer):
        """Test updating customer"""
        url = reverse('customer-detail', kwargs={'pk': customer.id})
        data = {
            'email': customer.email,
            'full_name': customer.full_name,
            'phone_number': customer.phone_number,
            'address': 'Updated Address',
            'city': 'Samarkand',
            'country': 'Uzbekistan',
        }

        response = authenticated_client.put(url, data, format='json')

        assert response.status_code == 200
        assert response.data['address'] == 'Updated Address'
        assert response.data['city'] == 'Samarkand'

    def test_partial_update_customer(self, authenticated_client, customer):
        """Test partially updating customer"""
        url = reverse('customer-detail', kwargs={'pk': customer.id})
        data = {'city': 'Bukhara'}

        response = authenticated_client.patch(url, data, format='json')

        assert response.status_code == 200
        assert response.data['city'] == 'Bukhara'
        assert response.data['address'] == customer.address

    def test_unauthenticated_access(self, api_client):
        """Test unauthenticated access is denied"""
        url = reverse('customer-list')
        response = api_client.get(url)

        assert response.status_code == 401


@pytest.mark.django_db
class TestCustomerProfileAPI:
    """Test Customer Profile API endpoints"""

    def test_get_profile_creates_if_not_exists(self, authenticated_client, user):
        """Test getting profile creates customer if doesn't exist"""
        url = reverse('customer-profile')
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert response.data['user_id'] == str(user.id)
        assert response.data['email'] == user.email

        assert Customer.objects.filter(user=user).exists()

    def test_get_profile_returns_existing(self, authenticated_client, customer):
        """Test getting profile returns existing customer"""
        url = reverse('customer-profile')
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert response.data['id'] == str(customer.id)

    def test_update_profile(self, authenticated_client, customer):
        """Test updating profile via PUT"""
        url = reverse('customer-profile')
        data = {
            'email': 'updated@example.com',
            'full_name': 'Updated Name',
            'phone_number': '998907777777',
            'address': 'New Address',
            'city': 'New City',
            'country': 'Uzbekistan',
        }

        response = authenticated_client.put(url, data, format='json')

        assert response.status_code == 200
        assert response.data['email'] == 'updated@example.com'
        assert response.data['full_name'] == 'Updated Name'

    def test_partial_update_profile(self, authenticated_client, customer):
        """Test partially updating profile via PATCH"""
        url = reverse('customer-profile')
        data = {'address': 'Partially Updated Address'}

        response = authenticated_client.patch(url, data, format='json')

        assert response.status_code == 200
        assert response.data['address'] == 'Partially Updated Address'
        assert response.data['full_name'] == customer.full_name

    def test_profile_requires_authentication(self, api_client):
        """Test profile endpoint requires authentication"""
        url = reverse('customer-profile')
        response = api_client.get(url)

        assert response.status_code == 401
