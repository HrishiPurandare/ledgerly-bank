from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.models import User
from users.serializers import RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """Create a customer account. Open to anyone, rate limited."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]  # throttle_scope alone does nothing
    throttle_scope = "auth"

    @extend_schema(responses={201: UserSerializer})
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # Never echo the password back, even hashed.
        response.data = UserSerializer(User.objects.get(email=response.data["email"])).data
        return response


class LoginView(TokenObtainPairView):
    """Email + password in, an access token (15 min) and a refresh token (1 day) out. Rate limited."""

    throttle_classes = [ScopedRateThrottle]  # throttle_scope alone does nothing
    throttle_scope = "auth"


class RefreshView(TokenRefreshView):
    """Swap a refresh token for a new access token. The refresh token rotates on every use."""

    throttle_classes = [ScopedRateThrottle]  # throttle_scope alone does nothing
    throttle_scope = "auth"


class MeView(generics.RetrieveAPIView):
    """The logged-in customer's profile."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
