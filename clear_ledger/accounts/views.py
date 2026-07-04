from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

from .models import UserProfile
from .serializers import CustomTokenObtainPairSerializer, ProfileSerializer, RegisterSerializer

User = get_user_model()


@extend_schema(
    tags=['Auth'],
    summary='Register a new user',
    description=(
        'Creates a new user account with the given credentials. '
        'Role defaults to `owner` if not provided. '
        'Returns JWT access and refresh tokens immediately — no separate login step required.'
    ),
    request=RegisterSerializer,
    responses={
        201: inline_serializer(
            name='RegisterResponse',
            fields={
                'user': inline_serializer(
                    name='RegisterUserInfo',
                    fields={
                        'id': serializers.IntegerField(),
                        'username': serializers.CharField(),
                        'email': serializers.EmailField(),
                        'role': serializers.ChoiceField(choices=['owner', 'accountant', 'viewer']),
                    },
                ),
                'access': serializers.CharField(help_text='Short-lived JWT access token (15 min)'),
                'refresh': serializers.CharField(help_text='Long-lived JWT refresh token (7 days)'),
            },
        ),
        400: OpenApiResponse(description='Validation error — username already taken or password too weak'),
    },
)
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = CustomTokenObtainPairSerializer.get_token(user)
        return Response(
            {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                },
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=['Auth'],
    summary='Login',
    description=(
        'Authenticates with username and password. '
        'Returns access and refresh tokens. '
        'Both the JWT payload and the response body carry `role` and `email` for client convenience.'
    ),
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'access': serializers.CharField(help_text='Short-lived JWT access token (15 min)'),
                'refresh': serializers.CharField(help_text='Long-lived JWT refresh token (7 days)'),
                'role': serializers.ChoiceField(
                    choices=['owner', 'accountant', 'viewer'],
                    help_text='User role embedded in response body and JWT payload',
                ),
                'email': serializers.EmailField(help_text='User email embedded in response body and JWT payload'),
            },
        ),
        401: OpenApiResponse(description='Invalid credentials'),
    },
)
class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


@extend_schema(
    tags=['Auth'],
    summary='Logout',
    description=(
        'Blacklists the provided refresh token. '
        'The access token cannot be revoked — it expires naturally after its lifetime (15 min). '
        'Refresh token rotation means each `/token/refresh/` call also invalidates the previous refresh token.'
    ),
    request=inline_serializer(
        name='LogoutRequest',
        fields={'refresh': serializers.CharField(help_text='The refresh token to blacklist')},
    ),
    responses={
        204: OpenApiResponse(description='Logged out — refresh token blacklisted'),
        400: OpenApiResponse(description='Token is invalid, expired, or already blacklisted'),
    },
)
class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            return Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema_view(
    get=extend_schema(
        tags=['Auth'],
        summary='Get profile',
        description=(
            "Returns the authenticated user's profile. "
            'The profile record is created automatically on first request if it does not exist.'
        ),
        responses={200: ProfileSerializer},
    ),
    patch=extend_schema(
        tags=['Auth'],
        summary='Update profile',
        description=(
            'Partially updates the profile. '
            'Only `currency_preference` is writable. '
            'The `user`, `created_at`, and `updated_at` fields are read-only.'
        ),
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
    ),
)
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    http_method_names = ['get', 'patch']

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


@extend_schema(
    tags=['Auth'],
    summary='Refresh access token',
    description=(
        'Issues a new access token using a valid refresh token. '
        'Because `ROTATE_REFRESH_TOKENS` is enabled, a new refresh token is also returned '
        'and the submitted refresh token is blacklisted immediately.'
    ),
    responses={
        200: inline_serializer(
            name='TokenRefreshResponse',
            fields={
                'access': serializers.CharField(help_text='New short-lived access token (15 min)'),
                'refresh': serializers.CharField(help_text='New refresh token — submitted token is now blacklisted'),
            },
        ),
        401: OpenApiResponse(description='Refresh token is invalid, expired, or already blacklisted'),
    },
)
class TokenRefreshView(BaseTokenRefreshView):
    pass
