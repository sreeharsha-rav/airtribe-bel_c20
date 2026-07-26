from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from ..serializers import PlanCreateSerializer, PlanSerializer, PlanUpdateSerializer
from ..services import PlanService
from ._base import BillingAPIView


class PlanListCreateView(BillingAPIView):
    @extend_schema(summary="List plans", responses=PlanSerializer(many=True), tags=["Plans"])
    def get(self, request):
        plans = PlanService().list_plans()
        return Response(PlanSerializer(plans, many=True).data)

    @extend_schema(
        summary="Create a plan",
        request=PlanCreateSerializer,
        responses={201: PlanSerializer},
        tags=["Plans"],
    )
    def post(self, request):
        serializer = PlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = PlanService().create_plan(**serializer.validated_data)
        return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(BillingAPIView):
    @extend_schema(
        summary="Update or deactivate a plan",
        request=PlanUpdateSerializer,
        responses=PlanSerializer,
        tags=["Plans"],
    )
    def patch(self, request, plan_id):
        serializer = PlanUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = PlanService().update_plan(plan_id, **serializer.validated_data)
        return Response(PlanSerializer(plan).data)
