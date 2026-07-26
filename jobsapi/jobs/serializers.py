import re
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import Company, Job, Application


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "location", "website"]


class JobSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source="company", write_only=True
    )
    salary_min = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1, max_value=500000)
    salary_max = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1, max_value=500000)
    days_since_posted = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = ["id", "title", "job_type", "location", "salary_min", "salary_max", "company", "company_id", "days_since_posted"]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_days_since_posted(self, obj):
        from django.utils import timezone
        if obj.created_at is None:
            return None
        return (timezone.now() - obj.created_at).days

    def validate(self, data):
        salary_min = data.get("salary_min", getattr(self.instance, "salary_min", None))
        salary_max = data.get("salary_max", getattr(self.instance, "salary_max", None))
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            raise serializers.ValidationError("salary_min cannot be greater than salary_max.")
        return data


class ApplicationSerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)
    job_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Application
        fields = ["id", "job", "job_id", "applicant_name", "applicant_email", "status", "applied_at"]
        read_only_fields = ["id", "applied_at"]

    def get_fields(self):
        fields = super().get_fields()
        if not self.instance:
            fields["status"].read_only = True
        return fields

    def validate_applicant_email(self, value):
        if not re.match(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$", value):
            raise serializers.ValidationError("Enter a valid email address.")
        return value

    def validate_status(self, value):
        current = self.instance.status if self.instance else None

        if current and current != value and value not in Application.ALLOWED_TRANSITIONS.get(current, []):
            raise serializers.ValidationError(
                f"Cannot transition from '{current}' to '{value}'."
            )

        return value

    def validate(self, data):
        job_id = data.get("job_id")
        applicant_email = data.get("applicant_email")

        if job_id is not None:
            job = Job.objects.filter(id=job_id).first()
            if not job:
                raise serializers.ValidationError({"job_id": "Job not found."})

            qs = Application.objects.filter(job_id=job_id, applicant_email=applicant_email)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            already_applied = qs.exists()
            if already_applied:
                raise serializers.ValidationError({
                    "applicant_email": "This applicant has already applied for this job."
                })

        return data

    def create(self, validated_data):
        job_id = validated_data.pop("job_id")
        job = Job.objects.get(id=job_id)
        return Application.objects.create(job=job, **validated_data)
