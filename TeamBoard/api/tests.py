from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from .models import Company, KBEntry, QueryLog


class RegisterTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('auth-register')

    def test_successful_registration(self):
        data = {
            "username": "acmecorp",
            "password": "securepass123",
            "company_name": "Acme Corp",
            "email": "dev@acmecorp.com"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify response structure
        self.assertEqual(response.data['username'], "acmecorp")
        self.assertEqual(response.data['company_name'], "Acme Corp")
        self.assertTrue('api_key' in response.data)
        self.assertTrue('access' in response.data)
        
        # Verify db entries
        user = User.objects.get(username="acmecorp")
        self.assertEqual(user.email, "dev@acmecorp.com")
        
        company = Company.objects.get(user=user)
        self.assertEqual(company.company_name, "Acme Corp")
        self.assertEqual(company.api_key, response.data['api_key'])
        self.assertEqual(company.role, Company.Role.CLIENT)

    def test_duplicate_username_registration(self):
        # Create initial user
        User.objects.create_user(username="acmecorp", password="password123")
        
        data = {
            "username": "acmecorp",
            "password": "securepass123",
            "company_name": "Acme Corp",
            "email": "dev@acmecorp.com"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_missing_email_registration(self):
        # email is required
        data = {
            "username": "acmecorp",
            "password": "securepass123",
            "company_name": "Acme Corp"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_missing_company_name_registration(self):
        data = {
            "username": "acmecorp",
            "password": "securepass123",
            "email": "dev@acmecorp.com"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company_name", response.data)

    def test_password_too_short(self):
        data = {
            "username": "acmecorp",
            "password": "short",
            "company_name": "Acme Corp",
            "email": "dev@acmecorp.com"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_role_cannot_be_set_from_request_body(self):
        data = {
            "username": "admincorp",
            "password": "securepass123",
            "company_name": "Admin Corp",
            "email": "admin@admincorp.com",
            "role": "admin"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(username="admincorp")
        company = Company.objects.get(user=user)
        # role must default to CLIENT even if "admin" is passed in request body
        self.assertEqual(company.role, Company.Role.CLIENT)

    def test_signal_only_runs_on_creation(self):
        data = {
            "username": "testcorp",
            "password": "securepass123",
            "company_name": "Test Corp",
            "email": "test@testcorp.com"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(username="testcorp")
        company = Company.objects.get(user=user)
        original_api_key = company.api_key
        original_company_id = company.id
        
        # Save user again (update)
        user.email = "newemail@testcorp.com"
        user.save()
        
        # Verify no duplicate company has been created and api_key remains unchanged
        self.assertEqual(Company.objects.filter(user=user).count(), 1)
        company.refresh_from_db()
        self.assertEqual(company.id, original_company_id)
        self.assertEqual(company.api_key, original_api_key)


class LoginTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse('auth-login')
        
        # Setup a test user and company
        self.user = User.objects.create_user(username="acmecorp", password="securepass123", email="dev@acmecorp.com")
        self.company = self.user.company
        self.company.company_name = "Acme Corp"
        self.company.api_key = "test-api-key"
        self.company.save()

    def test_login_success(self):
        data = {
            "username": "acmecorp",
            "password": "securepass123"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify returned data structure
        self.assertTrue('access' in response.data)
        self.assertEqual(response.data['company_name'], "Acme Corp")
        self.assertEqual(response.data['api_key'], "test-api-key")

    def test_login_invalid_credentials(self):
        data = {
            "username": "acmecorp",
            "password": "wrongpassword"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], "Invalid credentials.")

    def test_login_missing_username(self):
        data = {
            "password": "securepass123"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "username and password are required.")

    def test_login_missing_password(self):
        data = {
            "username": "acmecorp"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "username and password are required.")

    def test_login_user_without_company_graceful(self):
        # Create a user (which triggers the signal to create the company)
        user = User.objects.create_user(username="nocompanyuser", password="securepass123")
        # Delete the company profile to test the graceful fallback path
        Company.objects.filter(user=user).delete()
        
        data = {
            "username": "nocompanyuser",
            "password": "securepass123"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('access' in response.data)
        self.assertEqual(response.data['company_name'], "")
        self.assertEqual(response.data['api_key'], "")


class KBQueryTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.query_url = reverse('kb-query')
        
        self.user = User.objects.create_user(username="acmecorp", password="securepass123")
        self.company = self.user.company
        
        # Authenticate client
        response = self.client.post(reverse('auth-login'), {"username": "acmecorp", "password": "securepass123"}, format='json')
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        
        # Create some KB entries
        KBEntry.objects.create(question="What is Django ORM?", answer="It is an Object Relational Mapper.", category="framework")
        KBEntry.objects.create(question="How to use select_related?", answer="select_related performs a SQL JOIN.", category="database")
        KBEntry.objects.create(question="Explain prefetch_related", answer="It does a separate lookup for many-to-many.", category="database")

    def test_query_success_match(self):
        data = {"search": "select_related"}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['search'], "select_related")
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['question'], "How to use select_related?")
        
        # Check QueryLog was created
        log = QueryLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.company, self.company)
        self.assertEqual(log.search_term, "select_related")
        self.assertEqual(log.results_count, 1)

    def test_query_empty_results(self):
        data = {"search": "nonexistentterm"}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(len(response.data['results']), 0)
        
        # Check QueryLog was still created
        log = QueryLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.results_count, 0)

    def test_query_missing_search(self):
        data = {}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check QueryLog was NOT created
        self.assertEqual(QueryLog.objects.count(), 0)

    def test_query_blank_search(self):
        data = {"search": "   "}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check QueryLog was NOT created
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_missing_company_name_registration(self):
        data = {
            "username": "acmecorp",
            "password": "securepass123",
            "email": "dev@acmecorp.com"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company_name", response.data)

    def test_password_too_short(self):
        data = {
            "username": "acmecorp",
            "password": "short",
            "company_name": "Acme Corp",
            "email": "dev@acmecorp.com"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_role_cannot_be_set_from_request_body(self):
        data = {
            "username": "admincorp",
            "password": "securepass123",
            "company_name": "Admin Corp",
            "email": "admin@admincorp.com",
            "role": "admin"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(username="admincorp")
        company = Company.objects.get(user=user)
        # role must default to CLIENT even if "admin" is passed in request body
        self.assertEqual(company.role, Company.Role.CLIENT)

    def test_signal_only_runs_on_creation(self):
        data = {
            "username": "testcorp",
            "password": "securepass123",
            "company_name": "Test Corp",
            "email": "test@testcorp.com"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(username="testcorp")
        company = Company.objects.get(user=user)
        original_api_key = company.api_key
        original_company_id = company.id
        
        # Save user again (update)
        user.email = "newemail@testcorp.com"
        user.save()
        
        # Verify no duplicate company has been created and api_key remains unchanged
        self.assertEqual(Company.objects.filter(user=user).count(), 1)
        company.refresh_from_db()
        self.assertEqual(company.id, original_company_id)
        self.assertEqual(company.api_key, original_api_key)


class LoginTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse('auth-login')
        
        # Setup a test user and company
        self.user = User.objects.create_user(username="acmecorp", password="securepass123", email="dev@acmecorp.com")
        self.company = self.user.company
        self.company.company_name = "Acme Corp"
        self.company.api_key = "test-api-key"
        self.company.save()

    def test_login_success(self):
        data = {
            "username": "acmecorp",
            "password": "securepass123"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify returned data structure
        self.assertTrue('access' in response.data)
        self.assertEqual(response.data['company_name'], "Acme Corp")
        self.assertEqual(response.data['api_key'], "test-api-key")

    def test_login_invalid_credentials(self):
        data = {
            "username": "acmecorp",
            "password": "wrongpassword"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], "Invalid credentials.")

    def test_login_missing_username(self):
        data = {
            "password": "securepass123"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "username and password are required.")

    def test_login_missing_password(self):
        data = {
            "username": "acmecorp"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "username and password are required.")

    def test_login_user_without_company_graceful(self):
        # Create a user (which triggers the signal to create the company)
        user = User.objects.create_user(username="nocompanyuser", password="securepass123")
        # Delete the company profile to test the graceful fallback path
        Company.objects.filter(user=user).delete()
        
        data = {
            "username": "nocompanyuser",
            "password": "securepass123"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('access' in response.data)
        self.assertEqual(response.data['company_name'], "")
        self.assertEqual(response.data['api_key'], "")


class KBQueryTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.query_url = reverse('kb-query')
        
        self.user = User.objects.create_user(username="acmecorp", password="securepass123")
        self.company = self.user.company
        
        # Authenticate client
        response = self.client.post(reverse('auth-login'), {"username": "acmecorp", "password": "securepass123"}, format='json')
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        
        # Create some KB entries
        KBEntry.objects.create(question="What is Django ORM?", answer="It is an Object Relational Mapper.", category="framework")
        KBEntry.objects.create(question="How to use select_related?", answer="select_related performs a SQL JOIN.", category="database")
        KBEntry.objects.create(question="Explain prefetch_related", answer="It does a separate lookup for many-to-many.", category="database")

    def test_query_success_match(self):
        data = {"search": "select_related"}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['search'], "select_related")
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['question'], "How to use select_related?")
        
        # Check QueryLog was created
        log = QueryLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.company, self.company)
        self.assertEqual(log.search_term, "select_related")
        self.assertEqual(log.results_count, 1)

    def test_query_empty_results(self):
        data = {"search": "nonexistentterm"}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(len(response.data['results']), 0)
        
        # Check QueryLog was still created
        log = QueryLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.results_count, 0)

    def test_query_missing_search(self):
        data = {}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check QueryLog was NOT created
        self.assertEqual(QueryLog.objects.count(), 0)

    def test_query_blank_search(self):
        data = {"search": "   "}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check QueryLog was NOT created
        self.assertEqual(QueryLog.objects.count(), 0)

    def test_query_unauthenticated(self):
        self.client.credentials()  # Remove token
        data = {"search": "select_related"}
        response = self.client.post(self.query_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(QueryLog.objects.count(), 0)


class UsageSummaryTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.usage_url = reverse('usage-summary')
        
        self.admin_user = User.objects.create_user(username="adminuser", password="password")
        self.admin_company = self.admin_user.company
        self.admin_company.role = Company.Role.ADMIN
        self.admin_company.save()
        
        self.client_user = User.objects.create_user(username="clientuser", password="password")
        self.client_company = self.client_user.company
        # role is CLIENT by default
        
        # Populate QueryLogs
        QueryLog.objects.create(company=self.client_company, search_term="select_related", results_count=1)
        QueryLog.objects.create(company=self.client_company, search_term="select_related", results_count=2)
        QueryLog.objects.create(company=self.admin_company, search_term="select_related", results_count=1)
        
        QueryLog.objects.create(company=self.client_company, search_term="Q objects", results_count=5)
        QueryLog.objects.create(company=self.client_company, search_term="Q objects", results_count=5)
        
        QueryLog.objects.create(company=self.admin_company, search_term="JWT authentication", results_count=0)

    def test_usage_summary_success_admin(self):
        response = self.client.post(reverse('auth-login'), {"username": "adminuser", "password": "password"}, format='json')
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        
        response = self.client.get(self.usage_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertEqual(response.data['total_queries'], 6)
        self.assertEqual(response.data['active_companies'], 2)
        
        top_terms = response.data['top_search_terms']
        self.assertEqual(len(top_terms), 3)
        self.assertEqual(top_terms[0]['search_term'], "select_related")
        self.assertEqual(top_terms[0]['count'], 3)
        
        self.assertEqual(top_terms[1]['search_term'], "Q objects")
        self.assertEqual(top_terms[1]['count'], 2)

    def test_usage_summary_forbidden_client(self):
        response = self.client.post(reverse('auth-login'), {"username": "clientuser", "password": "password"}, format='json')
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        
        response = self.client.get(self.usage_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_usage_summary_unauthenticated(self):
        response = self.client.get(self.usage_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
