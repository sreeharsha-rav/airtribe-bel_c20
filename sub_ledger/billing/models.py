from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class ActivationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class BillingCycle(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    YEARLY = "yearly", "Yearly"
    CUSTOM = "custom", "Custom"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    CANCELLED = "cancelled", "Cancelled"


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    PARTIALLY_PAID = "partially_paid", "Partially Paid"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"
    VOID = "void", "Void"


class PaymentAttemptStatus(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class LedgerEntryType(models.TextChoices):
    INVOICE_CREATED = "invoice_created", "Invoice Created"
    PAYMENT_SUCCESS = "payment_success", "Payment Success"
    PAYMENT_FAILURE = "payment_failure", "Payment Failure"


class Plan(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(
        max_length=10, choices=ActivationStatus.choices, default=ActivationStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.billing_cycle}, {self.price} {self.currency})"


class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    company_name = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=10, choices=ActivationStatus.choices, default=ActivationStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} <{self.email}>"


class Subscription(models.Model):
    customer = models.ForeignKey(Customer, related_name="subscriptions", on_delete=models.PROTECT)
    plan = models.ForeignKey(Plan, related_name="subscriptions", on_delete=models.PROTECT)
    status = models.CharField(
        max_length=10, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE
    )
    start_date = models.DateTimeField()
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Subscription #{self.pk} — {self.customer} on {self.plan}"


class Invoice(models.Model):
    subscription = models.ForeignKey(Subscription, related_name="invoices", on_delete=models.PROTECT)
    customer = models.ForeignKey(Customer, related_name="invoices", on_delete=models.PROTECT)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3)
    status = models.CharField(
        max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.ISSUED
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice #{self.pk} — {self.customer} ({self.status})"


class PaymentAttempt(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="payment_attempts", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=10, choices=PaymentAttemptStatus.choices)
    provider_reference = models.CharField(max_length=255, blank=True, default="")
    failure_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PaymentAttempt #{self.pk} — Invoice #{self.invoice_id} ({self.status})"


class LedgerEntry(models.Model):
    customer = models.ForeignKey(Customer, related_name="ledger_entries", on_delete=models.PROTECT)
    invoice = models.ForeignKey(Invoice, related_name="ledger_entries", on_delete=models.PROTECT)
    entry_type = models.CharField(max_length=20, choices=LedgerEntryType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    reference_id = models.CharField(max_length=64)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"LedgerEntry #{self.pk} — {self.entry_type} ({self.amount} {self.currency})"

    def save(self, *args, **kwargs):
        # Append-only: DESIGN.md §4 — LedgerService/LedgerRepository never
        # expose an update path, this is the hard backstop against a stray
        # `entry.save()` on an already-persisted row.
        if self.pk is not None:
            raise ValueError("LedgerEntry is append-only and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("LedgerEntry is append-only and cannot be deleted.")
