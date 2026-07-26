from django.contrib import admin

from .models import Customer, Invoice, LedgerEntry, PaymentAttempt, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "billing_cycle", "price", "currency", "status")
    list_filter = ("status", "billing_cycle")
    search_fields = ("name",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "company_name", "status")
    list_filter = ("status",)
    search_fields = ("name", "email", "company_name")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "plan", "status", "current_period_start", "current_period_end")
    list_filter = ("status",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "subscription", "amount_due", "amount_paid", "status", "due_date")
    list_filter = ("status",)


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice", "amount", "currency", "status", "created_at")
    list_filter = ("status",)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "invoice", "entry_type", "amount", "currency", "reference_id", "created_at")
    list_filter = ("entry_type",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
