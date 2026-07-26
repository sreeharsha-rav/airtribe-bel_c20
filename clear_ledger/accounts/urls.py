from django.urls import path

from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='auth-register'),
    path('login/', views.LoginView.as_view(), name='auth-login'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('profile/', views.ProfileView.as_view(), name='auth-profile'),
]
