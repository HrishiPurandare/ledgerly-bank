from django.contrib import admin

from banking.models import Account, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["iban", "owner", "type", "balance", "status"]
    list_filter = ["type", "status"]
    search_fields = ["iban", "owner__email"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["reference", "account", "direction", "category", "amount", "created_at"]
    list_filter = ["direction", "category"]
    search_fields = ["reference", "description", "counterparty"]
