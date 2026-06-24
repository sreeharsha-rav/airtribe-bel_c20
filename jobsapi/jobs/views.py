from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from .filters import JobFilter
from .models import Application, Company, Job
from .serializers import ApplicationSerializer, CompanySerializer, JobSerializer


_400 = OpenApiResponse(
    description="Validation error",
    examples=[
        OpenApiExample(
            "Validation error",
            value={"field": ["This field is required."]},
            response_only=True,
        )
    ],
)

_404 = OpenApiResponse(
    description="Not found",
    examples=[
        OpenApiExample(
            "Not found",
            value={"detail": "No resource matches the given query."},
            response_only=True,
        )
    ],
)


@extend_schema_view(
    list=extend_schema(
        tags=["companies"],
        summary="List all companies",
        description="Returns a paginated list of all companies.",
        responses={200: CompanySerializer(many=True)},
    ),
    create=extend_schema(
        tags=["companies"],
        summary="Create a company",
        description="Creates and returns a new company.",
        responses={201: CompanySerializer, 400: _400},
        examples=[
            OpenApiExample(
                "Create company",
                value={
                    "name": "Acme Corp",
                    "location": "San Francisco, CA",
                    "website": "https://acme.example.com",
                },
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["companies"],
        summary="Retrieve a company",
        description="Returns a single company by ID.",
        responses={200: CompanySerializer, 404: _404},
    ),
    update=extend_schema(
        tags=["companies"],
        summary="Update a company",
        description="Fully updates a company by ID.",
        responses={200: CompanySerializer, 400: _400, 404: _404},
        examples=[
            OpenApiExample(
                "Update company",
                value={
                    "name": "Acme Corp",
                    "location": "New York, NY",
                    "website": "https://acme.example.com",
                },
                request_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        tags=["companies"],
        summary="Partially update a company",
        description="Updates one or more fields of a company by ID.",
        responses={200: CompanySerializer, 400: _400, 404: _404},
        examples=[
            OpenApiExample(
                "Partial update company",
                value={"location": "Austin, TX"},
                request_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        tags=["companies"],
        summary="Delete a company",
        description="Permanently deletes a company and all its associated jobs.",
        responses={204: None, 404: _404},
    ),
)
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer


@extend_schema_view(
    list=extend_schema(
        tags=["jobs"],
        summary="List all job postings",
        description=(
            "Returns a paginated list of jobs. "
            "Supports filtering by `job_type` and `location`, "
            "salary range filtering via `salary_min` (≥ value) and `salary_max` (≤ value), "
            "full-text search on `title`, and ordering by `created_at` or `salary_min`."
        ),
        responses={200: JobSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["jobs"],
        summary="Create a job posting",
        description="Creates and returns a new job posting associated with a company.",
        responses={201: JobSerializer, 400: _400},
        examples=[
            OpenApiExample(
                "Create job",
                value={
                    "title": "Backend Engineer",
                    "job_type": "full_time",
                    "location": "Remote",
                    "salary_min": "80000.00",
                    "salary_max": "120000.00",
                    "company_id": 1,
                },
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["jobs"],
        summary="Retrieve a job posting",
        description="Returns a single job posting by ID, including nested company details.",
        responses={200: JobSerializer, 404: _404},
    ),
    update=extend_schema(
        tags=["jobs"],
        summary="Update a job posting",
        description="Fully updates a job posting by ID.",
        responses={200: JobSerializer, 400: _400, 404: _404},
        examples=[
            OpenApiExample(
                "Update job",
                value={
                    "title": "Senior Backend Engineer",
                    "job_type": "full_time",
                    "location": "Remote",
                    "salary_min": "100000.00",
                    "salary_max": "150000.00",
                    "company_id": 1,
                },
                request_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        tags=["jobs"],
        summary="Partially update a job posting",
        description="Updates one or more fields of a job posting by ID.",
        responses={200: JobSerializer, 400: _400, 404: _404},
        examples=[
            OpenApiExample(
                "Partial update job",
                value={"salary_max": "130000.00"},
                request_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        tags=["jobs"],
        summary="Delete a job posting",
        description="Permanently deletes a job posting and all its associated applications.",
        responses={204: None, 404: _404},
    ),
)
class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.select_related("company").all()
    serializer_class = JobSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = JobFilter
    search_fields = ["title"]
    ordering_fields = ["created_at", "salary_min"]

    @extend_schema(
        tags=["jobs"],
        summary="Apply to a job",
        description=(
            "Submits a job application for the specified job. "
            "Each applicant email may only apply once per job. "
            "The `status` field is set to `pending` automatically."
        ),
        request=ApplicationSerializer,
        responses={
            201: ApplicationSerializer,
            400: OpenApiResponse(
                description="Validation error — duplicate application or invalid field",
                examples=[
                    OpenApiExample(
                        "Duplicate application",
                        value={"applicant_email": ["This applicant has already applied for this job."]},
                        response_only=True,
                    ),
                    OpenApiExample(
                        "Invalid email",
                        value={"applicant_email": ["Enter a valid email address."]},
                        response_only=True,
                    ),
                ],
            ),
            404: _404,
        },
        examples=[
            OpenApiExample(
                "Apply to job",
                value={"applicant_name": "Jane Doe", "applicant_email": "jane@example.com"},
                request_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        job = self.get_object()
        serializer = ApplicationSerializer(data={**request.data, "job_id": job.pk})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        tags=["applications"],
        summary="List all applications",
        description="Returns a paginated list of all job applications with nested job and company details.",
        responses={200: ApplicationSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["applications"],
        summary="Submit a job application",
        description=(
            "Creates a new application for a job directly. "
            "Prefer `POST /jobs/{id}/apply/` for a more natural workflow."
        ),
        responses={201: ApplicationSerializer, 400: _400},
        examples=[
            OpenApiExample(
                "Create application",
                value={
                    "job_id": 1,
                    "applicant_name": "John Smith",
                    "applicant_email": "john@example.com",
                },
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["applications"],
        summary="Retrieve an application",
        description="Returns a single job application by ID.",
        responses={200: ApplicationSerializer, 404: _404},
    ),
    update=extend_schema(
        tags=["applications"],
        summary="Update an application",
        description="Fully updates an application by ID. Status transition rules are enforced.",
        responses={200: ApplicationSerializer, 400: _400, 404: _404},
        examples=[
            OpenApiExample(
                "Update application",
                value={
                    "job_id": 1,
                    "applicant_name": "John Smith",
                    "applicant_email": "john@example.com",
                    "status": "reviewed",
                },
                request_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        tags=["applications"],
        summary="Advance application status",
        description=(
            "Updates the status of an application. "
            "Allowed transitions: `pending` → `reviewed` → `accepted` | `rejected`. "
            "Terminal states `accepted` and `rejected` cannot be changed."
        ),
        responses={
            200: ApplicationSerializer,
            400: OpenApiResponse(
                description="Invalid status transition",
                examples=[
                    OpenApiExample(
                        "Invalid transition",
                        value={"status": ["Cannot transition from 'pending' to 'accepted'."]},
                        response_only=True,
                    ),
                ],
            ),
            404: _404,
        },
        examples=[
            OpenApiExample(
                "Advance to reviewed",
                value={"status": "reviewed"},
                request_only=True,
            ),
            OpenApiExample(
                "Accept application",
                value={"status": "accepted"},
                request_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        tags=["applications"],
        summary="Delete an application",
        description="Permanently deletes an application.",
        responses={204: None, 404: _404},
    ),
)
class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.select_related("job__company").all()
    serializer_class = ApplicationSerializer