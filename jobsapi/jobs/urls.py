from django.urls import path
from . import views

urlpatterns = [
    path("companies/", views.CompanyListView.as_view()),
    path("companies/<int:pk>/", views.CompanyDetailView.as_view()),
    path("jobs/", views.JobListView.as_view()),
    path("jobs/<int:pk>/", views.JobDetailView.as_view()),
    path("applications/", views.ApplicationListView.as_view()),
    path("applications/<int:pk>/", views.ApplicationDetailView.as_view()),
    path("jobs/<int:pk>/apply/", views.apply_for_job),
]
