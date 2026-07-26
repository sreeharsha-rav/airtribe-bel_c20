from django.utils import timezone

from ..models import Subscription, SubscriptionStatus


class SubscriptionRepository:
    def create(self, **fields):
        return Subscription.objects.create(**fields)

    def get_by_id(self, subscription_id):
        return Subscription.objects.filter(pk=subscription_id).first()

    def get_active_by_customer_and_plan(self, customer_id, plan_id):
        return Subscription.objects.filter(
            customer_id=customer_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
        ).first()

    def cancel(self, subscription):
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.save()
        return subscription

    def advance_period(self, subscription, period_start, period_end):
        # Takes the already-computed next period bounds rather than
        # billing_cycle — cycle-length math is a service-layer concern,
        # kept out of this thin repository.
        subscription.current_period_start = period_start
        subscription.current_period_end = period_end
        subscription.save()
        return subscription

    def list(self, **filters):
        queryset = Subscription.objects.all()
        if filters:
            queryset = queryset.filter(**filters)
        return queryset.order_by("id")
