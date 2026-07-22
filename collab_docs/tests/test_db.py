"""
Postgres connectivity and model persistence tests.

Requires the Postgres container to be running:
    docker compose up -d

Run with:
    python manage.py test tests.test_db --verbosity=2
"""

import uuid

from django.db import IntegrityError, OperationalError, connection, transaction
from django.test import TestCase

from core.models import Comment, Document, Tag, User, Workspace, WorkspaceMember


class PostgresConnectivityTests(TestCase):

    def test_backend_is_postgresql(self):
        vendor = connection.vendor
        self.assertEqual(
            vendor,
            "postgresql",
            f"Expected postgresql backend, got: {vendor}. "
            "Check POSTGRES_* vars in .env and that docker compose is running.",
        )

    def test_connection_is_live(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
            self.assertEqual(row[0], 1)
        except OperationalError as e:
            self.fail(
                f"Could not connect to Postgres: {e}\n"
                "Run `docker compose up -d` and wait for the healthcheck to pass."
            )

    def test_postgres_version(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
        self.assertIn("PostgreSQL", version)


class ModelPersistenceTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create(
            first_name="Ada", last_name="Lovelace", email="ada@example.com", phone="1234567890"
        )
        self.workspace = Workspace.objects.create(name="Engineering", owner=self.owner)
        self.document = Document.objects.create(
            title="Design Doc", content="v1", workspace=self.workspace, created_by=self.owner
        )

    def test_primary_keys_are_uuids(self):
        self.assertIsInstance(self.owner.id, uuid.UUID)
        self.assertIsInstance(self.workspace.id, uuid.UUID)
        self.assertIsInstance(self.document.id, uuid.UUID)

    def test_document_status_uses_text_choices(self):
        self.assertEqual(self.document.status, Document.Status.DRAFT)
        self.document.status = Document.Status.PUBLISHED
        self.document.save()
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "published")

    def test_workspace_member_unique_constraint(self):
        WorkspaceMember.objects.create(workspace=self.workspace, user=self.owner, role=WorkspaceMember.Role.ADMIN)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkspaceMember.objects.create(
                    workspace=self.workspace, user=self.owner, role=WorkspaceMember.Role.EDITOR
                )

    def test_tag_document_many_to_many(self):
        tag = Tag.objects.create(name="python")
        tag.documents.add(self.document)
        self.assertIn(tag, self.document.tags.all())
        self.assertIn(self.document, tag.documents.all())

    def test_comment_self_referential_replies(self):
        parent = Comment.objects.create(document=self.document, author=self.owner, content="Looks good")
        reply = Comment.objects.create(
            document=self.document, author=self.owner, content="Agreed", parent=parent
        )
        self.assertIn(reply, parent.replies.all())
        self.assertEqual(reply.parent, parent)
