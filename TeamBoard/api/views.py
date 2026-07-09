from django.contrib.auth import authenticate

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer
from .models import Company



@extend_schema(
    tags=["Auth"],
    summary="Register a new user and company profile",
    description=(
        "Creates a new user account and an associated company profile with the default role of `CLIENT`. "
        "Returns the newly generated API key and a JWT access token on success."
    ),
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(
            description="User and Company created successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "username": "acmecorp",
                        "company_name": "Acme Corp",
                        "api_key": "gT8x...auto-generated...",
                        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    },
                    response_only=True,
                    status_codes=["201"],
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation error — missing fields, password too short, or duplicate username.",
            examples=[
                OpenApiExample(
                    "Duplicate username",
                    value={"username": ["A user with that username already exists."]},
                    response_only=True,
                    status_codes=["400"],
                ),
                OpenApiExample(
                    "Short password",
                    value={"password": ["Ensure this field has at least 8 characters."]},
                    response_only=True,
                    status_codes=["400"],
                ),
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "Company registration",
            value={
                "username": "acmecorp",
                "password": "securepass123",
                "company_name": "Acme Corp",
                "email": "dev@acmecorp.com"
            },
            request_only=True,
        ),
    ],
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        company = user.company
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'username': user.username,
                'company_name': company.company_name,
                'api_key': company.api_key,
                'access': str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Auth"],
    summary="Login and obtain JWT tokens",
    description=(
        "Validates credentials using Django's `authenticate()` backend. "
        "Returns a JWT `access` token, `company_name`, and `api_key` on success."
    ),
    request={
        "application/json": {
            "type": "object",
            "required": ["username", "password"],
            "properties": {
                "username": {"type": "string", "example": "acmecorp"},
                "password": {"type": "string", "example": "securepass123"},
            },
        }
    },
    responses={
        200: OpenApiResponse(
            description="Login successful.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "company_name": "Acme Corp",
                        "api_key": "gT8x...",
                    },
                    response_only=True,
                    status_codes=["200"],
                )
            ],
        ),
        400: OpenApiResponse(
            description="Missing username or password.",
            examples=[
                OpenApiExample(
                    "Missing fields",
                    value={"detail": "username and password are required."},
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
        401: OpenApiResponse(
            description="Invalid credentials or inactive account.",
            examples=[
                OpenApiExample(
                    "Bad credentials",
                    value={"detail": "Invalid credentials."},
                    response_only=True,
                    status_codes=["401"],
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "Valid login",
            value={"username": "acmecorp", "password": "securepass123"},
            request_only=True,
        ),
    ],
)
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'detail': 'username and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {'detail': 'Invalid credentials.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            company = user.company
            company_name = company.company_name
            api_key = company.api_key
        except Company.DoesNotExist:
            company_name = ""
            api_key = ""

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'access': str(refresh.access_token),
                'company_name': company_name,
                'api_key': api_key,
            },
            status=status.HTTP_200_OK,
        )
