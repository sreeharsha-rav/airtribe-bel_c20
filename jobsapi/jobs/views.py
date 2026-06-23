from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from .models import Company, Job, Application
from .serializers import CompanySerializer, JobSerializer, ApplicationSerializer


# --- Company Views ---

class CompanyListView(APIView):
    def get(self, _request):
        serializer = CompanySerializer(Company.objects.all(), many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CompanyDetailView(APIView):
    def get_object(self, pk):
        try:
            return Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return None

    def get(self, _request, pk):
        company = self.get_object(pk)
        if company is None:
            return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(CompanySerializer(company).data)

    def put(self, request, pk):
        company = self.get_object(pk)
        if company is None:
            return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CompanySerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, _request, pk):
        company = self.get_object(pk)
        if company is None:
            return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)
        company.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Job Views ---

class JobListView(APIView):
    def get(self, _request):
        jobs = Job.objects.select_related("company").all()
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = JobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class JobDetailView(APIView):
    def get_object(self, pk):
        try:
            return Job.objects.select_related("company").get(pk=pk)
        except Job.DoesNotExist:
            return None

    def get(self, _request, pk):
        job = self.get_object(pk)
        if job is None:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(JobSerializer(job).data)

    def put(self, request, pk):
        job = self.get_object(pk)
        if job is None:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = JobSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, _request, pk):
        job = self.get_object(pk)
        if job is None:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Application Views ---

class ApplicationListView(APIView):
    def get(self, _request):
        applications = Application.objects.all()
        serializer = ApplicationSerializer(applications, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ApplicationDetailView(APIView):
    def get_object(self, pk):
        try:
            return Application.objects.get(pk=pk)
        except Application.DoesNotExist:
            return None

    def get(self, _request, pk):
        application = self.get_object(pk)
        if application is None:
            return Response({"error": "Application not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ApplicationSerializer(application).data)

    def put(self, request, pk):
        application = self.get_object(pk)
        if application is None:
            return Response({"error": "Application not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ApplicationSerializer(application, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, _request, pk):
        application = self.get_object(pk)
        if application is None:
            return Response({"error": "Application not found"}, status=status.HTTP_404_NOT_FOUND)
        application.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Apply for Job ---

@api_view(["POST"])
def apply_for_job(request, pk):
    try:
        job = Job.objects.get(pk=pk)
    except Job.DoesNotExist:
        return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = ApplicationSerializer(data={**request.data, "job": job.pk})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)
