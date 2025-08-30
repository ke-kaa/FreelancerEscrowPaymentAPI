from django.contrib import admin
from .models import (
    Payment,
    PaymentMethod,
    PayoutMethod,
    ChapaPayoutMethod,
    StripePayoutMethod,
    Bank,
    WebhookEvent,
)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'escrow', 'user', 'amount', 'provider', 'transaction_type', 'status', 'timestamp')
    list_filter = ('provider', 'transaction_type', 'status')
    search_fields = ('provider_transactionn_id', 'user__email')


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'provider', 'display_info', 'is_default', 'created_at')
    list_filter = ('provider', 'is_default')
    search_fields = ('user__email', 'display_info')


@admin.register(PayoutMethod)
class PayoutMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'provider', 'is_default', 'is_verified', 'is_active', 'created_at')
    list_filter = ('provider', 'is_default', 'is_verified', 'is_active')
    search_fields = ('user__email',)


@admin.register(ChapaPayoutMethod)
class ChapaPayoutMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'payout_method', 'account_name', 'account_number', 'bank_code', 'bank_name')
    search_fields = ('account_name', 'account_number', 'bank_code')


@admin.register(StripePayoutMethod)
class StripePayoutMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'payout_method', 'stripe_account_id', 'charges_enabled', 'payouts_enabled')
    search_fields = ('stripe_account_id',)


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'country', 'is_active')
    list_filter = ('country', 'is_active')
    search_fields = ('code', 'name')


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('provider', 'event_id', 'received_at')
    list_filter = ('provider',)
    search_fields = ('event_id',)