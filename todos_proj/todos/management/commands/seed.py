from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from todos.models import Todo

TODOS = [
    {
        "title": "Buy groceries",
        "description": "Milk, eggs, bread, and coffee.",
        "completed": False,
    },
    {
        "title": "Read Django documentation",
        "description": "Focus on class-based views and the ORM.",
        "completed": True,
    },
    {
        "title": "Set up the project",
        "description": "Install dependencies, run migrations, start the server.",
        "completed": True,
    },
    {
        "title": "Write unit tests",
        "description": "Cover the API endpoints and model methods.",
        "completed": False,
    },
    {
        "title": "Deploy to production",
        "description": "Configure environment variables and a production database.",
        "completed": False,
    },
]

SUPERUSER = {
    "username": "admin",
    "email": "admin@example.com",
    "password": "admin123",
}


class Command(BaseCommand):
    help = "Seed the database with sample todos and create a superuser."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing todos before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count, _ = Todo.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing todo(s)."))

        created = 0
        for data in TODOS:
            _, is_new = Todo.objects.get_or_create(title=data["title"], defaults=data)
            if is_new:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} todo(s) ({len(TODOS) - created} already existed)."))

        if User.objects.filter(username=SUPERUSER["username"]).exists():
            self.stdout.write(self.style.WARNING(f"Superuser '{SUPERUSER['username']}' already exists — skipping."))
        else:
            User.objects.create_superuser(**SUPERUSER)
            self.stdout.write(self.style.SUCCESS(
                f"Superuser created — username: {SUPERUSER['username']}, password: {SUPERUSER['password']}"
            ))