import re
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
    class Meta:
        model = Application
        fields = ["id", "job", "applicant_name", "applicant_email", "status"]

    def validate_applicant_email(self, value):
        if not re.match(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$", value):
            raise serializers.ValidationError("Enter a valid email address.")
        return value
