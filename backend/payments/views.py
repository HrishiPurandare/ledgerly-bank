from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from payments import services
from payments.errors import TransferRejected
from payments.models import Beneficiary, Transfer
from payments.serializers import (
    BeneficiarySerializer,
    ConfirmSerializer,
    TransferRequestSerializer,
    TransferSerializer,
)


class BeneficiaryList(generics.ListCreateAPIView):
    """List beneficiaries, or add one. Adding emails a 6-digit OTP; it stays PENDING until confirmed."""

    serializer_class = BeneficiarySerializer
    queryset = Beneficiary.objects.none()

    def get_queryset(self):
        return Beneficiary.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.add_beneficiary(
            self.request.user,
            name=data["name"],
            iban=data["iban"],
            nickname=data.get("nickname", ""),
            now=timezone.now(),
        )


class BeneficiaryDetail(generics.RetrieveDestroyAPIView):
    serializer_class = BeneficiarySerializer
    queryset = Beneficiary.objects.none()

    def get_queryset(self):
        return Beneficiary.objects.filter(owner=self.request.user)


class BeneficiaryConfirm(APIView):
    """Confirm a new beneficiary with the emailed code. Three wrong codes lock it."""

    @extend_schema(request=ConfirmSerializer, responses=BeneficiarySerializer)
    def post(self, request, pk: int):
        beneficiary = get_object_or_404(Beneficiary, pk=pk, owner=request.user)
        serializer = ConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.confirm_beneficiary(beneficiary, serializer.validated_data["otp"], timezone.now())
        return Response(BeneficiarySerializer(beneficiary).data)


IDEMPOTENCY_HEADER = OpenApiParameter(
    "Idempotency-Key",
    OpenApiTypes.STR,
    OpenApiParameter.HEADER,
    required=True,
    description="A unique value per transfer (e.g. a UUID). A retry with the same key never pays twice.",
)


class TransferList(generics.ListAPIView):
    """Your transfers, newest first. POST sends money."""

    serializer_class = TransferSerializer
    queryset = Transfer.objects.none()

    def get_queryset(self):
        return Transfer.objects.filter(owner=self.request.user)

    @extend_schema(
        request=TransferRequestSerializer,
        responses={201: TransferSerializer},
        parameters=[IDEMPOTENCY_HEADER],
    )
    def post(self, request):
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 64:
            raise TransferRejected(
                "idempotency_key_required", "Send an Idempotency-Key header (1-64 characters)."
            )
        serializer = TransferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer, replayed = services.create_transfer(
            request.user, serializer.validated_data, idempotency_key=key, now=timezone.now()
        )
        response = Response(TransferSerializer(transfer).data, status=status.HTTP_201_CREATED)
        if replayed:
            response["Idempotent-Replayed"] = "true"  # same answer as the first time, and no money moved
        return response


class TransferDetail(generics.RetrieveAPIView):
    serializer_class = TransferSerializer
    queryset = Transfer.objects.none()

    def get_queryset(self):
        return Transfer.objects.filter(owner=self.request.user)
