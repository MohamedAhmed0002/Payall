class PayallError(Exception):
    def __init__(self, code: str, field: str, status: int = 422):
        self.code = code
        self.field = field
        self.status = status
        super().__init__(code)


PAYALL_ERROR_MESSAGES = {
    "price_must_be_positive": "Price must be greater than 0.",
    "price_too_high": "Price must not exceed 100000.00.",
    "price_required": "Price is required.",
    "billing_period_required": "Billing period is required.",
    "service_name_required": "Service name is required.",
    "service_name_too_long": "Service name must be 100 characters or fewer.",
    "category_not_found": "The selected category was not found.",
    "catalog_item_not_found": "The selected catalog item was not found.",
    "start_date_out_of_range": "Start date is outside the allowed range.",
    "subscription_not_found": "Subscription not found.",
    "subscription_cancelled": "This subscription is cancelled.",
    "already_cancelled": "This subscription is already cancelled.",
    "already_paid": "This period is already marked as paid.",
    "auto_pay_subscription": "Automatic payments are enabled for this subscription.",
    "nothing_due": "There is no payment due for this subscription.",
    "nothing_to_dismiss": "There is no current notification to dismiss.",
    "user_not_found": "User not found.",
    "invalid_input": "The input is invalid.",
    "exchange_rate_unavailable": "Exchange rate is currently unavailable. Please try again later.",
}
