from ..models import Plan


class PlanRepository:
    def create_plan(self, **fields):
        return Plan.objects.create(**fields)

    def get_plan_by_id(self, plan_id):
        return Plan.objects.filter(pk=plan_id).first()

    def list_plans(self, **filters):
        queryset = Plan.objects.all()
        if filters:
            queryset = queryset.filter(**filters)
        return queryset.order_by("id")

    def update_plan(self, plan, **fields):
        for field, value in fields.items():
            setattr(plan, field, value)
        plan.save()
        return plan
