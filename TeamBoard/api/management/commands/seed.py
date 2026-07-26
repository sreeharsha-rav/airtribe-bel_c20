from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from api.models import Company, KBEntry

KB_ENTRIES = [
    {
        "question": "How do I implement REST API authentication?",
        "answer": "REST API authentication can be implemented using tokens, such as JWT. This is typically done by sending the token in the Authorization header. For secure REST access, always use HTTPS.",
        "category": KBEntry.Category.API,
    },
    {
        "question": "What is the best way to secure a PostgreSQL database in Docker?",
        "answer": "To secure PostgreSQL in Docker, ensure you do not expose the default port (5432) to the public internet. Use a strong POSTGRES_PASSWORD, and consider using Docker networks so only your application containers can access the PostgreSQL container.",
        "category": KBEntry.Category.DATABASE,
    },
    {
        "question": "How do I deploy a REST API on Kubernetes?",
        "answer": "Deploying a REST API on Kubernetes involves creating a Deployment to manage your pods, and a Service to expose the API. You can use Ingress to handle routing and TLS termination for authentication endpoints.",
        "category": KBEntry.Category.CLOUD,
    },
    {
        "question": "Which framework is recommended for building a REST API in Python?",
        "answer": "Django REST Framework (DRF) is highly recommended. It provides built-in serializers, authentication classes, and views. It makes creating a REST API much faster compared to writing everything from scratch.",
        "category": KBEntry.Category.FRAMEWORK,
    },
    {
        "question": "What is Docker and how does it compare to Kubernetes?",
        "answer": "Docker is a containerization platform used to package applications and their dependencies. Kubernetes is a container orchestration platform that manages Docker (or other) containers across a cluster of machines. They are often used together.",
        "category": KBEntry.Category.CLOUD,
    },
    {
        "question": "How can I backup my PostgreSQL database?",
        "answer": "You can use the pg_dump utility to create logical backups of a PostgreSQL database. If your PostgreSQL database is running in a Docker container, you can execute pg_dump using `docker exec`.",
        "category": KBEntry.Category.DATABASE,
    },
    {
        "question": "What are common authentication methods for web applications?",
        "answer": "Common authentication methods include Session-based authentication, Token-based authentication (like JWT), and OAuth. For modern REST APIs, token-based authentication is the standard approach.",
        "category": KBEntry.Category.GENERAL,
    },
    {
        "question": "How do I connect Django to a PostgreSQL database?",
        "answer": "To connect Django to PostgreSQL, you need the psycopg2 library. Then, configure the DATABASES setting in your settings.py with the ENGINE set to 'django.db.backends.postgresql' and provide the database name, user, password, and host.",
        "category": KBEntry.Category.FRAMEWORK,
    },
    {
        "question": "Can I run Kubernetes locally for testing?",
        "answer": "Yes, tools like Minikube, kind (Kubernetes in Docker), or Docker Desktop's built-in Kubernetes allow you to run a local cluster for development and testing of your containerized applications.",
        "category": KBEntry.Category.CLOUD,
    },
    {
        "question": "How to handle rate limiting for a REST API?",
        "answer": "Rate limiting restricts the number of API requests a user can make in a given timeframe. In frameworks like Django REST Framework, you can use built-in throttling classes or tools like Redis to enforce these limits based on IP address or authentication tokens.",
        "category": KBEntry.Category.API,
    },
]

class Command(BaseCommand):
    help = "Seed the database with sample KB entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing data before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            KBEntry.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing KBEntry data."))

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(username="admin", email="admin@example.com", password="admin123")
            self.stdout.write(self.style.SUCCESS("Created superuser: admin / admin123"))
        else:
            self.stdout.write("Superuser 'admin' already exists, skipping.")
            
        for data in KB_ENTRIES:
            kb, created = KBEntry.objects.get_or_create(
                question=data["question"],
                defaults={"answer": data["answer"], "category": data["category"]},
            )
            if created:
                self.stdout.write(f"  Created KBEntry: {kb}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {KBEntry.objects.count()} KB entries."
        ))
