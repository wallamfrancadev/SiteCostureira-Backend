from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from produtos.models import Category, Product
from pedidos.models import Order, OrderItem
from usuarios.models import UserProfile


def make_user(username='user1', password='senha1234'):
    user = User.objects.create_user(username=username, password=password)
    UserProfile.objects.get_or_create(user=user)
    return user


def get_token(client, username='user1', password='senha1234'):
    res = client.post('/api/token/', {'username': username, 'password': password}, format='json')
    return res.data['access']


def make_product(name='Produto Teste', price='50.00', stock=10):
    cat = Category.objects.get_or_create(name='Categoria Teste')[0]
    return Product.objects.create(
        name=name, description='Desc', price=price, stock=stock, category=cat, is_active=True
    )


class OrderCreateTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        token = get_token(self.client)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _order_payload(self, quantity=1, product_id=None):
        return {
            'items': [{'product_id': product_id or self.product.id, 'quantity': quantity}],
            'shipping_address': 'Rua Teste, 123',
            'shipping_city': 'São Paulo',
            'shipping_state': 'SP',
            'shipping_cep': '01310-100',
        }

    def test_create_order_success(self):
        res = self.client.post('/api/orders/', self._order_payload(), format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 1)

    def test_create_order_requires_auth(self):
        self.client.credentials()
        res = self.client.post('/api/orders/', self._order_payload(), format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_order_calculates_total(self):
        res = self.client.post('/api/orders/', self._order_payload(quantity=3), format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        expected_total = float(self.product.price) * 3
        self.assertAlmostEqual(float(res.data['total']), expected_total, places=2)

    def test_create_order_decrements_stock(self):
        initial_stock = self.product.stock
        self.client.post('/api/orders/', self._order_payload(quantity=4), format='json')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock - 4)

    def test_create_order_insufficient_stock(self):
        res = self.client.post('/api/orders/', self._order_payload(quantity=999), format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_order_invalid_product(self):
        res = self.client.post('/api/orders/', self._order_payload(product_id=99999), format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_order_inactive_product(self):
        self.product.is_active = False
        self.product.save()
        res = self.client.post('/api/orders/', self._order_payload(), format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_order_empty_items(self):
        payload = {'items': []}
        res = self.client.post('/api/orders/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_order_creates_order_items(self):
        self.client.post('/api/orders/', self._order_payload(quantity=2), format='json')
        order = Order.objects.first()
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.quantity, 2)
        self.assertAlmostEqual(float(item.subtotal), float(self.product.price) * 2, places=2)

    def test_create_order_default_status_pending(self):
        res = self.client.post('/api/orders/', self._order_payload(), format='json')
        self.assertEqual(res.data['status'], 'pending')


class OrderListTest(APITestCase):
    def setUp(self):
        self.user1 = make_user('user1')
        self.user2 = make_user('user2')
        self.product = make_product()

        token1 = get_token(self.client, 'user1')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token1}')
        self.client.post('/api/orders/', {
            'items': [{'product_id': self.product.id, 'quantity': 1}]
        }, format='json')

    def test_list_orders_requires_auth(self):
        self.client.credentials()
        res = self.client.get('/api/orders/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_orders_only_own(self):
        token2 = get_token(self.client, 'user2')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token2}')
        res = self.client.get('/api/orders/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_list_orders_returns_own(self):
        res = self.client.get('/api/orders/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

    def test_order_detail_only_own(self):
        token1 = get_token(self.client, 'user1')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token1}')
        order = Order.objects.filter(user=self.user1).first()

        token2 = get_token(self.client, 'user2')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token2}')
        res = self.client.get(f'/api/orders/{order.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class OrderCancelTest(APITestCase):
    def setUp(self):
        self.user = make_user('canceluser')
        self.product = make_product(stock=10)
        token = get_token(self.client, 'canceluser')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = self.client.post('/api/orders/', {
            'items': [{'product_id': self.product.id, 'quantity': 3}]
        }, format='json')
        self.order_id = res.data['id']

    def test_cancel_pending_order(self):
        res = self.client.patch(f'/api/orders/{self.order_id}/cancel/', {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'cancelled')

    def test_cancel_restores_stock(self):
        self.client.patch(f'/api/orders/{self.order_id}/cancel/', {}, format='json')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_cancel_requires_auth(self):
        self.client.credentials()
        res = self.client.patch(f'/api/orders/{self.order_id}/cancel/', {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_cancel_other_users_order(self):
        other = make_user('otheruser')
        token2 = get_token(self.client, 'otheruser')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token2}')
        res = self.client.patch(f'/api/orders/{self.order_id}/cancel/', {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_cancel_already_cancelled(self):
        self.client.patch(f'/api/orders/{self.order_id}/cancel/', {}, format='json')
        res = self.client.patch(f'/api/orders/{self.order_id}/cancel/', {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_cancel_delivered_order(self):
        Order.objects.filter(pk=self.order_id).update(status='delivered')
        res = self.client.patch(f'/api/orders/{self.order_id}/cancel/', {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
