from decimal import Decimal

from rest_framework import serializers

from .models import (
    ActivationStatus,
    BillingCycle,
    Customer,
    Invoice,
    LedgerEntry,
    PaymentAttempt,
    PaymentAttemptStatus,
    Plan,
    Subscription,
)

# ---------------------------------------------------------------------------
# Output serializers — one per entity, read-only representations of the
# service-layer return values. Never used for input validation or `.save()`;
# persistence always goes through a service, not a serializer.
# ---------------------------------------------------------------------------


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id", "name", "description", "billing_cycle", "price", "currency",
            "status", "created_at", "updated_at",
        ]
        read_only_fields = fields


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "email", "company_name", "status", "created_at"]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    # Declared explicitly (rather than relying on ModelSerializer's default FK
    # handling) to expose the raw `customer_id`/`plan_id` columns matching the
    # ERD field names, instead of a nested object or a field named "customer".
    customer_id = serializers.IntegerField(read_only=True)
    plan_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id", "customer_id", "plan_id", "status", "start_date",
            "current_period_start", "current_period_end", "cancelled_at",
        ]
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    subscription_id = serializers.IntegerField(read_only=True)
    customer_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "subscription_id", "customer_id", "amount_due", "amount_paid",
            "currency", "status", "period_start", "period_end", "due_date", "created_at",
        ]
        read_only_fields = fields


class PaymentAttemptSerializer(serializers.ModelSerializer):
    invoice_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = PaymentAttempt
        fields = [
            "id", "invoice_id", "amount", "currency", "status",
            "provider_reference", "failure_reason", "created_at",
        ]
        read_only_fields = fields


class LedgerEntrySerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(read_only=True)
    invoice_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = LedgerEntry
        fields = [
            "id", "customer_id", "invoice_id", "entry_type", "amount",
            "currency", "reference_id", "description", "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Input serializers — plain (non-Model) serializers for create/patch actions.
# Field names follow each service method's signature, not the model, since
# several (Subscription, Invoice, Payment) take ids/derived values rather than
# the model's own fields. Validation here is schema-owned, defense-in-depth
# duplication of the same rule the owning service also enforces
# (DESIGN.md §4 "Business Rule Ownership") — not a replacement for it.
# ---------------------------------------------------------------------------


class PlanCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    billing_cycle = serializers.ChoiceField(choices=BillingCycle.choices)
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3, required=False, default="USD")

    def validate_price(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Plan price must be greater than 0.")
        return value


class PlanUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    billing_cycle = serializers.ChoiceField(choices=BillingCycle.choices, required=False)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    status = serializers.ChoiceField(choices=ActivationStatus.choices, required=False)

    def validate_price(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Plan price must be greater than 0.")
        return value


class CustomerCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    company_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class SubscriptionCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(min_value=1)
    plan_id = serializers.IntegerField(min_value=1)
    # Only meaningful for CUSTOM billing_cycle; the service derives it for
    # every later renewal, so it's accepted here just for the initial create.
    custom_period_length = serializers.DurationField(required=False, allow_null=True)


class InvoiceGenerateSerializer(serializers.Serializer):
    subscription_id = serializers.IntegerField(min_value=1)


class PaymentRecordSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    status = serializers.ChoiceField(choices=PaymentAttemptStatus.choices)
    provider_reference = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    failure_reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Payment amount must be greater than 0.")
        return value
