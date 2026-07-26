from ..models import Customer


class CustomerRepository:
    def create_customer(self, **fields):
        return Customer.objects.create(**fields)

    def get_by_email(self, email):
        return Customer.objects.filter(email=email).first()

    def get_by_id(self, customer_id):
        return Customer.objects.filter(pk=customer_id).first()

    def list_customers(self, **filters):
        queryset = Customer.objects.all()
        if filters:
            queryset = queryset.filter(**filters)
        return queryset.order_by("id")
