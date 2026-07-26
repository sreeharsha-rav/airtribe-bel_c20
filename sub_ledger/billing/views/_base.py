from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.exceptions import (
    CurrencyMismatchError,
    DomainError,
    DuplicateEmailError,
    DuplicateInvoiceError,
    DuplicateSubscriptionError,
    InvalidBillingCycleError,
    InvalidPlanPriceError,
    NotFoundError,
    PaymentExceedsBalanceError,
    PlanInactiveError,
    SubscriptionNotActiveError,
)

_DOMAIN_ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidPlanPriceError: status.HTTP_400_BAD_REQUEST,
    InvalidBillingCycleError: status.HTTP_400_BAD_REQUEST,
    CurrencyMismatchError: status.HTTP_400_BAD_REQUEST,
    PaymentExceedsBalanceError: status.HTTP_400_BAD_REQUEST,
    DuplicateEmailError: status.HTTP_409_CONFLICT,
    PlanInactiveError: status.HTTP_409_CONFLICT,
    DuplicateSubscriptionError: status.HTTP_409_CONFLICT,
    SubscriptionNotActiveError: status.HTTP_409_CONFLICT,
    DuplicateInvoiceError: status.HTTP_409_CONFLICT,
}


class BillingAPIView(APIView):
    """Base for every billing view.

    Translates domain exceptions raised by the service layer into the HTTP
    status they map to, so individual views only need to parse the request,
    call one service method, and serialize the result — they never need
    their own try/except around service calls.
    """

    def handle_exception(self, exc):
        if isinstance(exc, DomainError):
            http_status = _DOMAIN_ERROR_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST)
            return Response({"detail": str(exc)}, status=http_status)
        return super().handle_exception(exc)
