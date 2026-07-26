from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from ..serializers import SubscriptionCreateSerializer, SubscriptionSerializer
from ..services import SubscriptionService
from ._base import BillingAPIView


class SubscriptionListCreateView(BillingAPIView):
    @extend_schema(summary="List subscriptions", responses=SubscriptionSerializer(many=True), tags=["Subscriptions"])
    def get(self, request):
        subscriptions = SubscriptionService().list_subscriptions()
        return Response(SubscriptionSerializer(subscriptions, many=True).data)

    @extend_schema(
        summary="Create a subscription",
        request=SubscriptionCreateSerializer,
        responses={201: SubscriptionSerializer},
        tags=["Subscriptions"],
    )
    def post(self, request):
        serializer = SubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subscription = SubscriptionService().create(
            data["customer_id"],
            data["plan_id"],
            custom_period_length=data.get("custom_period_length"),
        )
        return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED)


class SubscriptionCancelView(BillingAPIView):
    @extend_schema(
        summary="Cancel a subscription",
        request=None,
        responses=SubscriptionSerializer,
        tags=["Subscriptions"],
    )
    def patch(self, request, subscription_id):
        subscription = SubscriptionService().cancel(subscription_id)
        return Response(SubscriptionSerializer(subscription).data)
