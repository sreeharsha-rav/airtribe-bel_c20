from jobs.models import Application, Company, Job


def make_company(**kwargs):
    defaults = {"name": "Acme", "location": "Remote", "website": "https://acme.com"}
    defaults.update(kwargs)
    return Company.objects.create(**defaults)


def make_job(company=None, **kwargs):
    if company is None:
        company = make_company()
    defaults = {
        "title": "Engineer",
        "job_type": Job.JobType.FULL_TIME,
        "location": "Remote",
        "salary_min": 80000,
        "salary_max": 120000,
        "company": company,
    }
    defaults.update(kwargs)
    return Job.objects.create(**defaults)


def make_application(job=None, **kwargs):
    if job is None:
        job = make_job()
    defaults = {
        "applicant_name": "Jane Doe",
        "applicant_email": "jane@example.com",
        "job": job,
    }
    defaults.update(kwargs)
    return Application.objects.create(**defaults)
