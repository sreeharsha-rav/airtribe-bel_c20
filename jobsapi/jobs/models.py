from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    website = models.URLField()

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


class Job(models.Model):
    class JobType(models.TextChoices):
        FULL_TIME = "full_time", "Full Time"
        PART_TIME = "part_time", "Part Time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    title = models.CharField(max_length=255)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2)
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.FULL_TIME)
    location = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.title} at {self.company.name}"


class Application(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REVIEWED = "reviewed", "Reviewed"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    ALLOWED_TRANSITIONS = {
        "pending": ["reviewed", "withdrawn"],
        "reviewed": ["accepted", "rejected"],
        "accepted": [],
        "rejected": [],
        "withdrawn": [],
    }

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    applicant_name = models.CharField(max_length=255)
    applicant_email = models.EmailField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    applied_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.applicant_name} -> {self.job.title}"
    