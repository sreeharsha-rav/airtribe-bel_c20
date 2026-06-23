from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Company, Job, Application
from .serializers import CompanySerializer, JobSerializer, ApplicationSerializer


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.select_related("company").all()
    serializer_class = JobSerializer

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        job = self.get_object()
        serializer = ApplicationSerializer(data={**request.data, "job_id": job.pk})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.select_related("job__company").all()
    serializer_class = ApplicationSerializer
