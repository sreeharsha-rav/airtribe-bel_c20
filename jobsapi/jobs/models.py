from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    website = models.URLField()

    class Meta:
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


class Job(models.Model):
    class JobType(models.TextChoices):
        FULL_TIME = "full_time", "Full Time"
        PART_TIME = "part_time", "Part Time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    title = models.CharField(max_length=255)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2)
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.FULL_TIME)
    location = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")

    def __str__(self):
        return f"{self.title} at {self.company.name}"


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        INTERVIEWING = "interviewing", "Interviewing"
        OFFERED = "offered", "Offered"
        REJECTED = "rejected", "Rejected"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    applicant_name = models.CharField(max_length=255)
    applicant_email = models.EmailField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPLIED)

    def __str__(self):
        return f"{self.applicant_name} -> {self.job.title}"