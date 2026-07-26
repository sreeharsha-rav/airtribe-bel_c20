from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from ..serializers import InvoiceSerializer, PaymentAttemptSerializer, PaymentRecordResponseSerializer, PaymentRecordSerializer
from ..services import PaymentService
from ._base import BillingAPIView


class PaymentRecordView(BillingAPIView):
    @extend_schema(
        summary="Record a payment attempt",
        request=PaymentRecordSerializer,
        responses={201: PaymentRecordResponseSerializer},
        tags=["Payments"],
    )
    def post(self, request):
        serializer = PaymentRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        attempt, invoice = PaymentService().record_payment(
            data["invoice_id"],
            data["amount"],
            data["currency"],
            data["status"],
            provider_reference=data["provider_reference"],
            failure_reason=data["failure_reason"],
        )
        response_data = {
            "payment_attempt": PaymentAttemptSerializer(attempt).data,
            "invoice": InvoiceSerializer(invoice).data,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
