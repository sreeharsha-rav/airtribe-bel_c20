class DomainError(Exception):
    """Base class for all billing domain exceptions."""


class NotFoundError(DomainError):
    """Raised when a requested entity does not exist."""


class InvalidPlanPriceError(DomainError):
    """Plan price must be greater than 0."""


class InvalidBillingCycleError(DomainError):
    """billing_cycle is not one of the supported values."""


class DuplicateEmailError(DomainError):
    """Customer email must be unique."""


class PlanInactiveError(DomainError):
    """A subscription cannot be created against an inactive plan."""


class DuplicateSubscriptionError(DomainError):
    """Customer already has an active subscription to this plan."""


class SubscriptionNotActiveError(DomainError):
    """An invoice can only be generated for an active subscription."""


class DuplicateInvoiceError(DomainError):
    """An invoice already exists for this subscription's current billing period."""


class CurrencyMismatchError(DomainError):
    """Payment currency does not match the invoice's currency."""


class PaymentExceedsBalanceError(DomainError):
    """Payment amount exceeds the invoice's remaining unpaid balance."""
