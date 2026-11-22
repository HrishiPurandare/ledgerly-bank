from rest_framework import serializers

from banking.iban import format_iban
from banking.models import Account, Transaction


class AccountSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    iban_display = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id",
            "iban",
            "iban_display",
            "type",
            "type_label",
            "nickname",
            "currency",
            "balance",
            "status",
            "opened_at",
        ]
        read_only_fields = fields

    def get_iban_display(self, account: Account) -> str:
        return format_iban(account.iban)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "reference",
            "direction",
            "category",
            "amount",
            "balance_after",
            "description",
            "counterparty",
            "created_at",
        ]
        read_only_fields = fields
