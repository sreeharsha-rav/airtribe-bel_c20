from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from jobs.models import Application

from .factories import make_application, make_company, make_job


class ApplicationListTests(APITestCase):
    def setUp(self):
        self.url = reverse("application-list")
        self.job = make_job()

    def test_list_returns_all_applications(self):
        make_application(job=self.job, applicant_email="a@example.com")
        make_application(job=self.job, applicant_email="b@example.com")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_nests_job_and_company(self):
        make_application(job=self.job)
        response = self.client.get(self.url)
        app = response.data["results"][0]
        self.assertIn("job", app)
        self.assertIn("company", app["job"])
        self.assertCountEqual(app["job"]["company"].keys(), ["id", "name", "location", "website"])

    def test_list_includes_applied_at(self):
        make_application(job=self.job)
        response = self.client.get(self.url)
        self.assertIn("applied_at", response.data["results"][0])
        self.assertIsNotNone(response.data["results"][0]["applied_at"])

    def test_list_includes_status(self):
        make_application(job=self.job)
        response = self.client.get(self.url)
        self.assertIn("status", response.data["results"][0])
        self.assertEqual(response.data["results"][0]["status"], "pending")

    def test_list_response_has_pagination_envelope(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_list_paginates_beyond_page_size(self):
        for i in range(12):
            make_application(job=self.job, applicant_email=f"user{i}@example.com")
        response = self.client.get(self.url)
        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])

    def test_list_page_two_returns_remaining_items(self):
        for i in range(12):
            make_application(job=self.job, applicant_email=f"user{i}@example.com")
        response = self.client.get(self.url + "?page=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])


class ApplicationCreateTests(APITestCase):
    def setUp(self):
        self.job = make_job()
        self.list_url = reverse("application-list")
        self.apply_url = reverse("job-apply", args=[self.job.pk])

    def test_create_via_applications_endpoint(self):
        payload = {"job_id": self.job.pk, "applicant_name": "Alice", "applicant_email": "alice@example.com"}
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["job"]["id"], self.job.pk)

    def test_create_via_apply_action(self):
        payload = {"applicant_name": "Bob", "applicant_email": "bob@example.com"}
        response = self.client.post(self.apply_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["job"]["id"], self.job.pk)

    def test_status_is_read_only_on_create_and_defaults_to_pending(self):
        # status is read-only on create; any value sent is silently ignored by DRF
        payload = {
            "job_id": self.job.pk,
            "applicant_name": "Charlie",
            "applicant_email": "charlie@example.com",
            "status": "accepted",
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")

    def test_status_is_read_only_on_create_via_apply_action(self):
        payload = {
            "applicant_name": "Charlie",
            "applicant_email": "charlie@example.com",
            "status": "accepted",
        }
        response = self.client.post(self.apply_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")

    def test_job_id_not_in_response(self):
        payload = {"job_id": self.job.pk, "applicant_name": "Alice", "applicant_email": "alice@example.com"}
        response = self.client.post(self.list_url, payload, format="json")
        self.assertNotIn("job_id", response.data)

    def test_applied_at_is_read_only_and_set_automatically(self):
        payload = {
            "job_id": self.job.pk,
            "applicant_name": "Dave",
            "applicant_email": "dave@example.com",
            "applied_at": "2000-01-01T00:00:00Z",
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response.data["applied_at"], "2000-01-01T00:00:00Z")

    def test_create_missing_applicant_name(self):
        response = self.client.post(self.list_url, {"job_id": self.job.pk, "applicant_email": "x@x.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("applicant_name", response.data)

    def test_create_missing_applicant_email(self):
        response = self.client.post(self.list_url, {"job_id": self.job.pk, "applicant_name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("applicant_email", response.data)

    def test_create_missing_job_id(self):
        response = self.client.post(self.list_url, {"applicant_name": "X", "applicant_email": "x@x.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job_id", response.data)


class ApplicationValidationTests(APITestCase):
    def setUp(self):
        self.job = make_job()
        self.url = reverse("application-list")

    def test_invalid_email_format(self):
        payload = {"job_id": self.job.pk, "applicant_name": "X", "applicant_email": "notanemail"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("applicant_email", response.data)

    def test_nonexistent_job_id(self):
        payload = {"job_id": 9999, "applicant_name": "X", "applicant_email": "x@x.com"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job_id", response.data)

    def test_duplicate_application_via_applications_endpoint(self):
        make_application(job=self.job, applicant_email="dup@example.com")
        payload = {"job_id": self.job.pk, "applicant_name": "Dup", "applicant_email": "dup@example.com"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("applicant_email", response.data)

    def test_duplicate_application_via_apply_action(self):
        make_application(job=self.job, applicant_email="dup@example.com")
        apply_url = reverse("job-apply", args=[self.job.pk])
        payload = {"applicant_name": "Dup", "applicant_email": "dup@example.com"}
        response = self.client.post(apply_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("applicant_email", response.data)

    def test_same_email_can_apply_to_different_jobs(self):
        job2 = make_job(title="Other Job")
        make_application(job=self.job, applicant_email="multi@example.com")
        payload = {"job_id": job2.pk, "applicant_name": "Multi", "applicant_email": "multi@example.com"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_put_update_does_not_false_positive_duplicate(self):
        app = make_application(job=self.job, applicant_email="put@example.com")
        url = reverse("application-detail", args=[app.pk])
        payload = {
            "job_id": self.job.pk,
            "applicant_name": "Put User",
            "applicant_email": "put@example.com",
            "status": "pending",
        }
        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_put_still_blocks_genuinely_duplicate_email(self):
        make_application(job=self.job, applicant_email="existing@example.com")
        app2 = make_application(job=self.job, applicant_email="other@example.com")
        url = reverse("application-detail", args=[app2.pk])
        payload = {
            "job_id": self.job.pk,
            "applicant_name": "Other",
            "applicant_email": "existing@example.com",
            "status": "pending",
        }
        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("applicant_email", response.data)


class ApplicationDetailTests(APITestCase):
    def setUp(self):
        self.job = make_job()
        self.application = make_application(job=self.job, applicant_email="jane@example.com")
        self.url = reverse("application-detail", args=[self.application.pk])

    def test_retrieve_application(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["applicant_email"], "jane@example.com")

    def test_retrieve_nonexistent_application(self):
        response = self.client.get(reverse("application-detail", args=[9999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_application(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Application.objects.filter(pk=self.application.pk).exists())


class ApplicationStateMachineTests(APITestCase):
    def setUp(self):
        self.job = make_job()

    def _make_app(self, status=Application.Status.PENDING, email="test@example.com"):
        return make_application(job=self.job, applicant_email=email, status=status)

    def _url(self, app):
        return reverse("application-detail", args=[app.pk])

    # --- same-status no-op (should always pass) ---

    def test_put_with_same_status_is_allowed(self):
        app = self._make_app(Application.Status.PENDING, email="noop@example.com")
        url = self._url(app)
        payload = {
            "job_id": self.job.pk,
            "applicant_name": app.applicant_name,
            "applicant_email": app.applicant_email,
            "status": "pending",
        }
        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "pending")

    def test_patch_with_same_status_is_allowed(self):
        app = self._make_app(Application.Status.REVIEWED, email="noop2@example.com")
        response = self.client.patch(self._url(app), {"status": "reviewed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "reviewed")

    # --- valid transitions ---

    def test_pending_to_reviewed(self):
        app = self._make_app(Application.Status.PENDING)
        response = self.client.patch(self._url(app), {"status": "reviewed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "reviewed")

    def test_reviewed_to_accepted(self):
        app = self._make_app(Application.Status.REVIEWED, email="r2a@example.com")
        response = self.client.patch(self._url(app), {"status": "accepted"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "accepted")

    def test_reviewed_to_rejected(self):
        app = self._make_app(Application.Status.REVIEWED, email="r2r@example.com")
        response = self.client.patch(self._url(app), {"status": "rejected"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "rejected")

    # --- invalid transitions ---

    def test_pending_cannot_skip_to_accepted(self):
        app = self._make_app(Application.Status.PENDING, email="skip1@example.com")
        response = self.client.patch(self._url(app), {"status": "accepted"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)
        self.assertIn("pending", response.data["status"][0])

    def test_pending_cannot_skip_to_rejected(self):
        app = self._make_app(Application.Status.PENDING, email="skip2@example.com")
        response = self.client.patch(self._url(app), {"status": "rejected"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_reviewed_cannot_go_back_to_pending(self):
        app = self._make_app(Application.Status.REVIEWED, email="back@example.com")
        response = self.client.patch(self._url(app), {"status": "pending"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_accepted_is_terminal_cannot_transition_to_rejected(self):
        app = self._make_app(Application.Status.ACCEPTED, email="term1@example.com")
        response = self.client.patch(self._url(app), {"status": "rejected"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)
        self.assertIn("accepted", response.data["status"][0])

    def test_accepted_is_terminal_cannot_transition_to_reviewed(self):
        app = self._make_app(Application.Status.ACCEPTED, email="term2@example.com")
        response = self.client.patch(self._url(app), {"status": "reviewed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejected_is_terminal_cannot_transition_to_reviewed(self):
        app = self._make_app(Application.Status.REJECTED, email="term3@example.com")
        response = self.client.patch(self._url(app), {"status": "reviewed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_without_status_field_leaves_status_unchanged(self):
        app = self._make_app(Application.Status.PENDING, email="nostatus@example.com")
        response = self.client.patch(self._url(app), {"applicant_name": "Updated Name"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "pending")

    def test_error_message_names_both_states(self):
        app = self._make_app(Application.Status.REVIEWED, email="msg@example.com")
        response = self.client.patch(self._url(app), {"status": "pending"}, format="json")
        error_msg = response.data["status"][0]
        self.assertIn("reviewed", error_msg)
        self.assertIn("pending", error_msg)
