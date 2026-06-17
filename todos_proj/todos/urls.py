from django.urls import path
from . import views

urlpatterns = [
    # API routes — return JSON
    path('api/todos/', views.TodoListCreateView.as_view(), name='api-todo-list'),
    path('api/todos/<int:id>/', views.TodoDetailUpdateDeleteView.as_view(), name='api-todo-detail'),

    # HTML routes — return rendered templates
    path('todos/', views.TodoListTemplateView.as_view(), name='todo-list'),
    path('todos/<int:id>/', views.TodoDetailTemplateView.as_view(), name='todo-detail'),
]