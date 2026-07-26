from django.contrib.auth import authenticate

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer


@extend_schema(
    tags=["Auth"],
    summary="Register a new user",
    description=(
        "Creates a new user account with the default role of `user`. "
        "The `role` field is never accepted from the request body — it is always set to `user`. "
        "Returns a JWT access token on success so the client can authenticate immediately."
    ),
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(
            description="User created successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={"username": "alice", "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "role": "user"},
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
            "Minimal registration",
            value={"username": "alice", "password": "securepass"},
            request_only=True,
        ),
        OpenApiExample(
            "With optional email",
            value={"username": "alice", "password": "securepass", "email": "alice@example.com"},
            request_only=True,
        ),
    ],
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'username': user.username,
                'access': str(refresh.access_token),
                'role': user.role,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Auth"],
    summary="Login and obtain JWT tokens",
    description=(
        "Validates credentials using Django's `authenticate()` backend. "
        "Returns both an `access` token (short-lived) and a `refresh` token (long-lived) on success. "
        "Returns `401` if credentials are invalid or the account is inactive. "
        "Returns `400` if `username` or `password` are missing from the request body."
    ),
    request={
        "application/json": {
            "type": "object",
            "required": ["username", "password"],
            "properties": {
                "username": {"type": "string", "example": "alice"},
                "password": {"type": "string", "example": "securepass"},
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
                        "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
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
            value={"username": "alice", "password": "securepass"},
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

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            status=status.HTTP_200_OK,
        )
