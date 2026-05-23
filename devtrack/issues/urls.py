from django.urls import path
from . import views

urlpatterns = [
    path('reporters/', views.reporters_view, name='reporters'),
    path('issues/', views.issues_view, name='issues'),
]
