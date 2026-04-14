from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status


class RegisterViewTest(APITestCase):
    url = '/api/auth/register/'

    def _payload(self, **kwargs):
        base = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'senha1234',
            'password2': 'senha1234',
        }
        base.update(kwargs)
        return base

    def test_register_success(self):
        res = self.client.post(self.url, self._payload(), format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='testuser').exists())

    def test_register_creates_user_profile(self):
        self.client.post(self.url, self._payload(), format='json')
        user = User.objects.get(username='testuser')
        self.assertTrue(hasattr(user, 'profile'))

    def test_register_password_mismatch(self):
        res = self.client.post(self.url, self._payload(password2='outrasenha'), format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password2', res.data)

    def test_register_short_password(self):
        res = self.client.post(self.url, self._payload(password='123', password2='123'), format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email(self):
        self.client.post(self.url, self._payload(), format='json')
        res = self.client.post(
            self.url,
            self._payload(username='outro', email='test@example.com'),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', res.data)

    def test_register_duplicate_username(self):
        self.client.post(self.url, self._payload(), format='json')
        res = self.client.post(
            self.url,
            self._payload(email='outro@example.com'),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_required_fields(self):
        res = self.client.post(self.url, {'username': 'x'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_not_returned(self):
        res = self.client.post(self.url, self._payload(), format='json')
        self.assertNotIn('password', res.data)
        self.assertNotIn('password2', res.data)


class TokenViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='authuser', password='senha1234', email='auth@example.com'
        )

    def test_login_success(self):
        res = self.client.post(
            '/api/token/', {'username': 'authuser', 'password': 'senha1234'}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)

    def test_login_wrong_password(self):
        res = self.client.post(
            '/api/token/', {'username': 'authuser', 'password': 'errada'}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        res = self.client.post(
            '/api/token/', {'username': 'naoexiste', 'password': 'qualquer'}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        login = self.client.post(
            '/api/token/', {'username': 'authuser', 'password': 'senha1234'}, format='json'
        )
        res = self.client.post(
            '/api/token/refresh/', {'refresh': login.data['refresh']}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)


class UserProfileViewTest(APITestCase):
    url = '/api/auth/profile/'

    def setUp(self):
        self.user = User.objects.create_user(
            username='profileuser',
            password='senha1234',
            email='profile@example.com',
            first_name='João',
            last_name='Silva',
        )
        from usuarios.models import UserProfile
        UserProfile.objects.get_or_create(user=self.user)

    def _auth(self, username='profileuser', password='senha1234'):
        res = self.client.post(
            '/api/token/', {'username': username, 'password': password}, format='json'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_profile_requires_auth(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_returns_user_data(self):
        self._auth()
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['username'], 'profileuser')
        self.assertEqual(res.data['email'], 'profile@example.com')
        self.assertIn('profile', res.data)

    def test_profile_update(self):
        self._auth()
        payload = {
            'first_name': 'Maria',
            'last_name': 'Costa',
            'email': 'maria@example.com',
            'profile': {'phone': '11999999999', 'city': 'São Paulo', 'state': 'SP', 'cep': '', 'address': ''},
        }
        res = self.client.put(self.url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Maria')
        self.assertEqual(self.user.profile.phone, '11999999999')

    def test_profile_username_readonly(self):
        self._auth()
        payload = {
            'username': 'hackedname',
            'first_name': 'Test',
            'last_name': 'Test',
            'email': 'profile@example.com',
            'profile': {'phone': '', 'city': '', 'state': '', 'cep': '', 'address': ''},
        }
        self.client.put(self.url, payload, format='json')
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'profileuser')

    def test_each_user_sees_own_profile(self):
        other = User.objects.create_user(username='outro', password='senha1234')
        from usuarios.models import UserProfile
        UserProfile.objects.get_or_create(user=other)
        self._auth(username='outro')
        res = self.client.get(self.url)
        self.assertEqual(res.data['username'], 'outro')
