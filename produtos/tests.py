from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from produtos.models import Category, Product


def make_category(name='Costura'):
    return Category.objects.get_or_create(name=name)[0]


def make_product(name='Almofada', price='80.00', stock=5, category=None, is_active=True):
    cat = category or make_category()
    return Product.objects.create(
        name=name, description='Descrição do produto',
        price=price, stock=stock, category=cat, is_active=is_active
    )


class CategoryViewTest(APITestCase):
    def setUp(self):
        make_category('Costura')
        make_category('Artesanato')

    def test_list_categories_public(self):
        res = self.client.get('/api/categories/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_category_fields(self):
        res = self.client.get('/api/categories/')
        cat = res.data[0]
        for field in ('id', 'name', 'description', 'created_at'):
            self.assertIn(field, cat)


class ProductListViewTest(APITestCase):
    def setUp(self):
        self.cat1 = make_category('Costura')
        self.cat2 = make_category('Artesanato')
        make_product('Almofada Rosa', '80.00', category=self.cat1)
        make_product('Toalha Bordada', '45.00', category=self.cat1)
        make_product('Boneca de Pano', '120.00', category=self.cat2)
        make_product('Produto Inativo', '10.00', is_active=False)

    def test_list_products_public(self):
        res = self.client.get('/api/products/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_inactive_products_excluded(self):
        res = self.client.get('/api/products/')
        names = [p['name'] for p in res.data]
        self.assertNotIn('Produto Inativo', names)
        self.assertEqual(len(res.data), 3)

    def test_filter_by_category(self):
        res = self.client.get(f'/api/products/?category={self.cat1.id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        for p in res.data:
            self.assertEqual(p['category'], self.cat1.id)

    def test_search_by_name(self):
        res = self.client.get('/api/products/?search=Almofada')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], 'Almofada Rosa')

    def test_search_by_description(self):
        res = self.client.get('/api/products/?search=Descrição')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreater(len(res.data), 0)

    def test_order_by_price_asc(self):
        res = self.client.get('/api/products/?ordering=price')
        prices = [float(p['price']) for p in res.data]
        self.assertEqual(prices, sorted(prices))

    def test_order_by_price_desc(self):
        res = self.client.get('/api/products/?ordering=-price')
        prices = [float(p['price']) for p in res.data]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_product_fields(self):
        res = self.client.get('/api/products/')
        p = res.data[0]
        for field in ('id', 'name', 'price', 'stock', 'category', 'category_name', 'is_active'):
            self.assertIn(field, p)

    def test_product_category_name_populated(self):
        res = self.client.get('/api/products/')
        for p in res.data:
            self.assertIsNotNone(p['category_name'])

    def test_product_detail_public(self):
        product = Product.objects.filter(is_active=True).first()
        res = self.client.get(f'/api/products/{product.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['id'], product.id)

    def test_product_write_not_allowed_unauthenticated(self):
        payload = {'name': 'Novo', 'price': '10.00', 'stock': 1}
        res = self.client.post('/api/products/', payload, format='json')
        # ReadOnlyModelViewSet retorna 405 Method Not Allowed
        self.assertIn(res.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        ])

    def test_product_write_not_allowed_authenticated(self):
        user = User.objects.create_user(username='normal', password='senha1234')
        login = self.client.post('/api/token/', {'username': 'normal', 'password': 'senha1234'}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        payload = {'name': 'Novo', 'price': '10.00', 'stock': 1}
        res = self.client.post('/api/products/', payload, format='json')
        self.assertIn(res.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        ])
