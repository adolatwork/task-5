# Transactional Order Processor

A robust Django REST Framework API for processing orders with atomic transactions, payment handling, and race condition prevention. This system ensures data consistency through database transactions and optimistic locking.

## Features

- **Atomic Order Processing**: All-or-nothing order creation with automatic rollback on failure
- **Transaction Management**: Database-level transaction handling using Django's `@transaction.atomic`
- **Race Condition Prevention**: Row-level locking with `select_for_update()` to prevent concurrent modifications
- **Optimistic Locking**: Version field tracking to handle concurrent updates
- **Payment Processing**: Complete payment lifecycle management (pending, processing, completed, failed, refunded)
- **Order Lifecycle**: Full order status tracking from creation to completion/cancellation/refund
- **Guest Checkout**: Support for both authenticated users and guest customers
- **Comprehensive Testing**: Full test coverage for models, services, and API endpoints

## Architecture

### Models

#### Customer
Stores customer information with support for both registered users and guest customers.

#### Order
Main order model with status tracking:
- `PENDING` - Initial state after creation
- `PROCESSING` - Payment being processed
- `CONFIRMED` - Payment completed successfully
- `COMPLETED` - Order fulfilled
- `CANCELLED` - Order cancelled
- `FAILED` - Payment or processing failed
- `REFUNDED` - Order refunded

#### OrderItem
Line items for each order with product snapshots to maintain historical accuracy.

#### Payment
Payment transaction tracking with multiple payment methods:
- Credit Card
- Debit Card
- PayPal
- Bank Transfer
- Cash
- Cryptocurrency

### Services

The `OrderService` class provides transactional operations:

- **create_order()**: Atomically create order with items and payment record
- **process_payment()**: Process payment with row locking to prevent duplicate processing
- **cancel_order()**: Cancel order and update related payment records
- **refund_order()**: Handle full or partial refunds
- **complete_order()**: Mark order as completed

## Technology Stack

- **Django 5.2.6**: Web framework
- **Django REST Framework 3.16.1**: API framework
- **PostgreSQL**: Primary database (with SQLite fallback for development)
- **Redis 5.0.1**: Caching and session management
- **drf-spectacular 0.26.5**: OpenAPI/Swagger documentation
- **PyJWT 2.8.0**: JWT authentication
- **Uvicorn 0.35.0**: ASGI server
- **pytest**: Testing framework

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL (or SQLite for development)
- Redis (optional)

### Setup

1. Clone the repository:
```bash
cd task_5
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
Create a `.env` file in the project root:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DEV=False  # False for SQLite, True for PostgreSQL

# PostgreSQL Configuration (if DEV=True)
DB_NAME=test_db
DB_USER=user
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
```

5. Run migrations:
```bash
make migrate
```

6. Create superuser (optional):
```bash
make createsuperuser
```

7. Run the development server:
```bash
make run
```

The API will be available at `http://localhost:8000`

## API Documentation

When running in DEBUG mode, interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/docs/swagger/
- **ReDoc**: http://localhost:8000/docs/
- **OpenAPI Schema**: http://localhost:8000/schema/

## API Endpoints

### Authentication
- `POST /api/v1/auth/register/` - Register new user
- `POST /api/v1/auth/login/` - Login and get JWT token
- `POST /api/v1/auth/logout/` - Logout

### Customer Profile
- `GET /api/v1/profile/` - Get customer profile
- `PUT /api/v1/profile/` - Update customer profile
- `PATCH /api/v1/profile/` - Partially update customer profile

### Customers (Admin)
- `GET /api/v1/customers/` - List all customers
- `POST /api/v1/customers/` - Create customer
- `GET /api/v1/customers/{id}/` - Get customer details
- `PUT /api/v1/customers/{id}/` - Update customer
- `DELETE /api/v1/customers/{id}/` - Delete customer

### Orders
- `GET /api/v1/orders/` - List orders
- `POST /api/v1/orders/` - Create new order (supports guest checkout)
- `GET /api/v1/orders/{id}/` - Get order details
- `POST /api/v1/orders/{id}/process-payment/` - Process payment for order
- `POST /api/v1/orders/{id}/cancel/` - Cancel order
- `POST /api/v1/orders/{id}/refund/` - Refund order
- `POST /api/v1/orders/{id}/complete/` - Mark order as completed

## Usage Examples

### Creating an Order (Guest Checkout)

```bash
curl -X POST http://localhost:8000/api/v1/orders/ \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "john@example.com",
    "customer_name": "John Doe",
    "customer_phone": "998901234567",
    "shipping_address": "123 Main St, Tashkent, Uzbekistan",
    "shipping_cost": "5.00",
    "payment_method": "CREDIT_CARD",
    "items": [
      {
        "product_name": "Laptop",
        "product_sku": "LAP-001",
        "quantity": 1,
        "unit_price": "1000.00"
      },
      {
        "product_name": "Mouse",
        "product_sku": "MOU-001",
        "quantity": 2,
        "unit_price": "25.00"
      }
    ]
  }'
```

### Processing Payment

```bash
curl -X POST http://localhost:8000/api/v1/orders/{order_id}/process-payment/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "payment_gateway": "stripe"
  }'
```

### Cancelling an Order

```bash
curl -X POST http://localhost:8000/api/v1/orders/{order_id}/cancel/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "reason": "Customer requested cancellation"
  }'
```

### Refunding an Order

```bash
curl -X POST http://localhost:8000/api/v1/orders/{order_id}/refund/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "reason": "Product defective",
    "amount": "525.00"
  }'
```

## Database Schema

### Key Features

- **Indexes**: Optimized queries with strategic indexes on frequently searched fields
- **Constraints**: Data integrity enforced at database level
- **Versioning**: Optimistic locking using version field on Order model
- **Decimal Precision**: Financial calculations use `DecimalField` with 10 digits and 2 decimal places

## Transaction Management

### Atomic Operations

All critical operations are wrapped in `@transaction.atomic` decorator:

```python
@transaction.atomic
def create_order(...):
    # All operations succeed or all rollback
    customer = Customer.objects.create(...)
    order = Order.objects.create(...)
    OrderItem.objects.create(...)
    Payment.objects.create(...)
```

### Race Condition Prevention

Row-level locking prevents concurrent modifications:

```python
@transaction.atomic
def process_payment(order_id):
    # Lock the order row until transaction completes
    order = Order.objects.select_for_update().get(id=order_id)
    payment = Payment.objects.select_for_update().filter(...)
    # Process payment safely
```

### Optimistic Locking

Version field incremented on updates using F expressions:

```python
order.version = F('version') + 1
order.save(update_fields=['status', 'version', 'updated_at'])
```

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=apps --cov-report=html
```

Run specific test file:

```bash
pytest tests/test_order.py
```

### Test Coverage

- **Models**: Validation, constraints, and business logic
- **Services**: Transaction handling, error scenarios, race conditions
- **API Endpoints**: Authentication, permissions, request/response formats
- **Edge Cases**: Concurrent access, invalid data, boundary conditions

## Makefile Commands

The project includes a Makefile for common tasks:

- `make run` - Run development server
- `make migrate` - Apply database migrations
- `make makemigrations` - Create new migrations
- `make createsuperuser` - Create admin user
- `make shell` - Open Django shell
- `make dbshell` - Open database shell

## Security Features

- **JWT Authentication**: Secure token-based authentication
- **Permission Classes**: Role-based access control
- **CSRF Protection**: Enabled for form submissions
- **SQL Injection Prevention**: Django ORM parameterized queries
- **Input Validation**: Comprehensive serializer validation
- **Secure Defaults**: Production-ready security settings

## Performance Optimizations

- **Database Indexes**: Strategic indexes on frequently queried fields
- **Query Optimization**: `select_related()` and `prefetch_related()` to reduce queries
- **Connection Pooling**: Database connection reuse
- **Redis Caching**: Optional Redis support for session and cache backend
- **Pagination**: Default page size of 20 items
