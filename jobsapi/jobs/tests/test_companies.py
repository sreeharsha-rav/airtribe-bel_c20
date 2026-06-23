from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from jobs.models import Application, Company, Job

from .factories import make_application, make_company, make_job


class CompanyListTests(APITestCase):
    def setUp(self):
        self.url = reverse("company-list")

    def test_list_returns_all_companies(self):
        make_company(name="Alpha")
        make_company(name="Beta")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_returns_expected_fields(self):
        make_company(name="Alpha")
        response = self.client.get(self.url)
        self.assertCountEqual(response.data[0].keys(), ["id", "name", "location", "website"])

    def test_create_company(self):
        payload = {"name": "NewCo", "location": "NYC", "website": "https://newco.com"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "NewCo")
        self.assertTrue(Company.objects.filter(name="NewCo").exists())

    def test_create_company_missing_name(self):
        response = self.client.post(self.url, {"location": "NYC", "website": "https://x.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_create_company_missing_location(self):
        response = self.client.post(self.url, {"name": "X", "website": "https://x.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("location", response.data)

    def test_create_company_missing_website(self):
        response = self.client.post(self.url, {"name": "X", "location": "NYC"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("website", response.data)

    def test_create_company_invalid_website_url(self):
        response = self.client.post(self.url, {"name": "X", "location": "NYC", "website": "not-a-url"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("website", response.data)


class CompanyDetailTests(APITestCase):
    def setUp(self):
        self.company = make_company(name="Stripe", location="SF", website="https://stripe.com")
        self.url = reverse("company-detail", args=[self.company.pk])

    def test_retrieve_company(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Stripe")

    def test_retrieve_nonexistent_company(self):
        response = self.client.get(reverse("company-detail", args=[9999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_replaces_company(self):
        payload = {"name": "Stripe Inc", "location": "San Francisco", "website": "https://stripe.com"}
        response = self.client.put(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Stripe Inc")

    def test_put_requires_all_fields(self):
        response = self.client.put(self.url, {"name": "Stripe Only"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("location", response.data)
        self.assertIn("website", response.data)

    def test_patch_updates_single_field(self):
        response = self.client.patch(self.url, {"location": "New York"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["location"], "New York")
        self.assertEqual(response.data["name"], "Stripe")

    def test_delete_company(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Company.objects.filter(pk=self.company.pk).exists())

    def test_delete_company_cascades_to_jobs_and_applications(self):
        job = make_job(company=self.company)
        app = make_application(job=job)
        self.client.delete(self.url)
        self.assertFalse(Job.objects.filter(pk=job.pk).exists())
        self.assertFalse(Application.objects.filter(pk=app.pk).exists())
