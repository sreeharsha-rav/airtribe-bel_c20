import calendar

from ..models import BillingCycle


def _add_months(moment, months):
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def compute_period_end(period_start, billing_cycle, custom_period_length=None):
    """Compute the end of a billing period given its start.

    `custom_period_length` (a timedelta) is required only for CUSTOM cycles,
    which have no fixed calendar unit — callers derive it from the existing
    period's length (there's no other source of truth for it).
    """
    if billing_cycle == BillingCycle.MONTHLY:
        return _add_months(period_start, 1)
    if billing_cycle == BillingCycle.QUARTERLY:
        return _add_months(period_start, 3)
    if billing_cycle == BillingCycle.YEARLY:
        return _add_months(period_start, 12)
    if billing_cycle == BillingCycle.CUSTOM:
        if custom_period_length is None:
            raise ValueError("custom_period_length is required to compute a custom billing period")
        return period_start + custom_period_length
    raise ValueError(f"Unsupported billing_cycle: {billing_cycle!r}")
