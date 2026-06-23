from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from jobs.models import Job

from .factories import make_company, make_job


class JobListTests(APITestCase):
    def setUp(self):
        self.url = reverse("job-list")
        self.company = make_company()

    def test_list_returns_all_jobs(self):
        make_job(company=self.company, title="Job A")
        make_job(company=self.company, title="Job B")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_nests_company_object(self):
        make_job(company=self.company)
        response = self.client.get(self.url)
        company_data = response.data[0]["company"]
        self.assertCountEqual(company_data.keys(), ["id", "name", "location", "website"])
        self.assertEqual(company_data["id"], self.company.pk)

    def test_list_includes_days_since_posted(self):
        make_job(company=self.company)
        response = self.client.get(self.url)
        self.assertIn("days_since_posted", response.data[0])
        self.assertIsNotNone(response.data[0]["days_since_posted"])

    def test_create_job(self):
        payload = {
            "title": "SRE",
            "job_type": "full_time",
            "location": "Remote",
            "salary_min": "90000",
            "salary_max": "130000",
            "company_id": self.company.pk,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "SRE")
        self.assertEqual(response.data["company"]["id"], self.company.pk)
        self.assertNotIn("company_id", response.data)

    def test_create_job_missing_required_fields(self):
        response = self.client.post(self.url, {"title": "Incomplete"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ("location", "salary_min", "salary_max", "company_id"):
            self.assertIn(field, response.data)

    def test_create_job_nonexistent_company(self):
        payload = {
            "title": "Ghost",
            "job_type": "full_time",
            "location": "Remote",
            "salary_min": "50000",
            "salary_max": "80000",
            "company_id": 9999,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company_id", response.data)

    def test_create_job_invalid_job_type(self):
        payload = {
            "title": "X",
            "job_type": "freelance",
            "location": "Remote",
            "salary_min": "50000",
            "salary_max": "80000",
            "company_id": self.company.pk,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job_type", response.data)


class JobValidationTests(APITestCase):
    def setUp(self):
        self.url = reverse("job-list")
        self.company = make_company()

    def _payload(self, **overrides):
        base = {
            "title": "Engineer",
            "job_type": "full_time",
            "location": "Remote",
            "salary_min": "80000",
            "salary_max": "120000",
            "company_id": self.company.pk,
        }
        base.update(overrides)
        return base

    def test_salary_min_greater_than_salary_max(self):
        response = self.client.post(self.url, self._payload(salary_min="200000", salary_max="100000"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)
        self.assertIn("salary_min cannot be greater than salary_max", response.data["non_field_errors"][0])

    def test_salary_max_exceeds_limit(self):
        response = self.client.post(self.url, self._payload(salary_max="999999"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("salary_max", response.data)

    def test_salary_min_below_minimum(self):
        response = self.client.post(self.url, self._payload(salary_min="0"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("salary_min", response.data)

    def test_salary_min_equal_to_salary_max_is_valid(self):
        response = self.client.post(self.url, self._payload(salary_min="100000", salary_max="100000"), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class JobDetailTests(APITestCase):
    def setUp(self):
        self.company = make_company()
        self.job = make_job(company=self.company, title="Backend Engineer", salary_min=80000, salary_max=120000)
        self.url = reverse("job-detail", args=[self.job.pk])

    def test_retrieve_job(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Backend Engineer")

    def test_retrieve_nonexistent_job(self):
        response = self.client.get(reverse("job-detail", args=[9999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_replaces_job(self):
        payload = {
            "title": "Senior Backend Engineer",
            "job_type": "full_time",
            "location": "Remote",
            "salary_min": "100000",
            "salary_max": "150000",
            "company_id": self.company.pk,
        }
        response = self.client.put(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Senior Backend Engineer")

    def test_patch_updates_salary_max_only(self):
        response = self.client.patch(self.url, {"salary_max": "130000"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["salary_max"], "130000.00")
        self.assertEqual(response.data["salary_min"], "80000.00")

    def test_patch_salary_min_above_existing_salary_max(self):
        response = self.client.patch(self.url, {"salary_min": "200000"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_delete_job(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Job.objects.filter(pk=self.job.pk).exists())
