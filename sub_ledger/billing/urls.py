from django.urls import path

from . import views

urlpatterns = [
    path("plans", views.PlanListCreateView.as_view(), name="plan-list-create"),
    path("plans/<int:plan_id>", views.PlanDetailView.as_view(), name="plan-detail"),
    path("customers", views.CustomerListCreateView.as_view(), name="customer-list-create"),
    path("customers/<int:customer_id>", views.CustomerDetailView.as_view(), name="customer-detail"),
    path("customers/<int:customer_id>/ledger", views.CustomerLedgerView.as_view(), name="customer-ledger"),
    path("subscriptions", views.SubscriptionListCreateView.as_view(), name="subscription-list-create"),
    path(
        "subscriptions/<int:subscription_id>/cancel",
        views.SubscriptionCancelView.as_view(),
        name="subscription-cancel",
    ),
    path("invoices/generate", views.InvoiceGenerateView.as_view(), name="invoice-generate"),
    path("invoices/<int:invoice_id>", views.InvoiceDetailView.as_view(), name="invoice-detail"),
    path("payments/record", views.PaymentRecordView.as_view(), name="payment-record"),
]
