from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from jobs.models import Application, Company, Job

COMPANIES = [
    {"name": "Stripe", "location": "San Francisco, CA", "website": "https://stripe.com"},
    {"name": "Vercel", "location": "Remote", "website": "https://vercel.com"},
    {"name": "Shopify", "location": "Ottawa, Canada", "website": "https://shopify.com"},
    {"name": "Linear", "location": "Remote", "website": "https://linear.app"},
    {"name": "Figma", "location": "San Francisco, CA", "website": "https://figma.com"},
]

JOBS = [
    {
        "title": "Backend Engineer",
        "salary_min": 120000,
        "salary_max": 160000,
        "job_type": Job.JobType.FULL_TIME,
        "location": "San Francisco, CA",
        "company": "Stripe",
    },
    {
        "title": "Staff Engineer",
        "salary_min": 180000,
        "salary_max": 240000,
        "job_type": Job.JobType.FULL_TIME,
        "location": "San Francisco, CA",
        "company": "Stripe",
    },
    {
        "title": "Frontend Engineer",
        "salary_min": 110000,
        "salary_max": 150000,
        "job_type": Job.JobType.FULL_TIME,
        "location": "Remote",
        "company": "Vercel",
    },
    {
        "title": "Developer Advocate",
        "salary_min": 90000,
        "salary_max": 120000,
        "job_type": Job.JobType.FULL_TIME,
        "location": "Remote",
        "company": "Vercel",
    },
    {
        "title": "Data Engineer",
        "salary_min": 100000,
        "salary_max": 140000,
        "job_type": Job.JobType.FULL_TIME,
        "location": "Ottawa, Canada",
        "company": "Shopify",
    },
    {
        "title": "Mobile Engineer (iOS)",
        "salary_min": 95000,
        "salary_max": 130000,
        "job_type": Job.JobType.CONTRACT,
        "location": "Remote",
        "company": "Shopify",
    },
    {
        "title": "Product Engineer",
        "salary_min": 130000,
        "salary_max": 170000,
        "job_type": Job.JobType.FULL_TIME,
        "location": "Remote",
        "company": "Linear",
    },
    {
        "title": "Design Engineer",
        "salary_min": 115000,
        "salary_max": 155000,
        "job_type": Job.JobType.FULL_TIME,
        "location": "San Francisco, CA",
        "company": "Figma",
    },
    {
        "title": "ML Engineer",
        "salary_min": 140000,
        "salary_max": 190000,
        "job_type": Job.JobType.FULL_TIME,
        "location": "San Francisco, CA",
        "company": "Figma",
    },
    {
        "title": "Engineering Intern",
        "salary_min": 40000,
        "salary_max": 60000,
        "job_type": Job.JobType.INTERNSHIP,
        "location": "Remote",
        "company": "Linear",
    },
]

# (job_title, company_name, applicant_name, applicant_email, status)
APPLICATIONS = [
    ("Backend Engineer", "Stripe", "Alice Johnson", "alice@example.com", Application.Status.REVIEWED),
    ("Backend Engineer", "Stripe", "Bob Smith", "bob@example.com", Application.Status.REJECTED),
    ("Staff Engineer", "Stripe", "Carol White", "carol@example.com", Application.Status.PENDING),
    ("Frontend Engineer", "Vercel", "David Lee", "david@example.com", Application.Status.ACCEPTED),
    ("Frontend Engineer", "Vercel", "Eva Martinez", "eva@example.com", Application.Status.REVIEWED),
    ("Developer Advocate", "Vercel", "Frank Chen", "frank@example.com", Application.Status.PENDING),
    ("Data Engineer", "Shopify", "Grace Kim", "grace@example.com", Application.Status.PENDING),
    ("Mobile Engineer (iOS)", "Shopify", "Henry Park", "henry@example.com", Application.Status.REJECTED),
    ("Product Engineer", "Linear", "Isla Brown", "isla@example.com", Application.Status.REVIEWED),
    ("Engineering Intern", "Linear", "Jack Wilson", "jack@example.com", Application.Status.ACCEPTED),
    ("Design Engineer", "Figma", "Karen Patel", "karen@example.com", Application.Status.PENDING),
    ("ML Engineer", "Figma", "Liam Nguyen", "liam@example.com", Application.Status.REVIEWED),
]


class Command(BaseCommand):
    help = "Seed the database with sample companies, jobs, and applications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing data before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            Application.objects.all().delete()
            Job.objects.all().delete()
            Company.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing data."))

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(username="admin", email="admin@example.com", password="admin123")
            self.stdout.write(self.style.SUCCESS("Created superuser: admin / admin123"))
        else:
            self.stdout.write("Superuser 'admin' already exists, skipping.")

        company_map = {}
        for data in COMPANIES:
            company, created = Company.objects.get_or_create(name=data["name"], defaults=data)
            company_map[company.name] = company
            if created:
                self.stdout.write(f"  Created company: {company}")

        job_map = {}
        for data in JOBS:
            company_name = data.pop("company")
            job, created = Job.objects.get_or_create(
                title=data["title"],
                company=company_map[company_name],
                defaults=data,
            )
            job_map[(job.title, company_name)] = job
            if created:
                self.stdout.write(f"  Created job: {job}")

        for job_title, company_name, name, email, status in APPLICATIONS:
            job = job_map[(job_title, company_name)]
            _, created = Application.objects.get_or_create(
                job=job,
                applicant_email=email,
                defaults={"applicant_name": name, "status": status},
            )
            if created:
                self.stdout.write(f"  Created application: {name} -> {job_title}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {Company.objects.count()} companies, "
            f"{Job.objects.count()} jobs, "
            f"{Application.objects.count()} applications."
        ))
