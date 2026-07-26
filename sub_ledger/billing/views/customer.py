from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from ..serializers import CustomerCreateSerializer, CustomerSerializer
from ..services import CustomerService
from ._base import BillingAPIView


class CustomerListCreateView(BillingAPIView):
    @extend_schema(summary="List customers", responses=CustomerSerializer(many=True), tags=["Customers"])
    def get(self, request):
        customers = CustomerService().list_customers()
        return Response(CustomerSerializer(customers, many=True).data)

    @extend_schema(
        summary="Create a customer",
        request=CustomerCreateSerializer,
        responses={201: CustomerSerializer},
        tags=["Customers"],
    )
    def post(self, request):
        serializer = CustomerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = CustomerService().create_customer(**serializer.validated_data)
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)


class CustomerDetailView(BillingAPIView):
    @extend_schema(summary="Fetch customer details", responses=CustomerSerializer, tags=["Customers"])
    def get(self, request, customer_id):
        customer = CustomerService().get_customer(customer_id)
        return Response(CustomerSerializer(customer).data)
