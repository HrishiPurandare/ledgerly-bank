from decimal import Decimal

from rest_framework import serializers

from banking.iban import format_iban
from payments.models import Beneficiary, Transfer


class BeneficiarySerializer(serializers.ModelSerializer):
    # Longer than 23 on input: people paste IBANs with spaces ("AE07 0331 ..."). Stored without them.
    iban = serializers.CharField(max_length=34)
    iban_display = serializers.SerializerMethodField()

    class Meta:
        model = Beneficiary
        fields = ["id", "name", "iban", "iban_display", "nickname", "status", "created_at", "activated_at"]
        read_only_fields = ["id", "status", "created_at", "activated_at"]

    def get_iban_display(self, beneficiary: Beneficiary) -> str:
        return format_iban(beneficiary.iban)


class ConfirmSerializer(serializers.Serializer):
    otp = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "The code is 6 digits."})


class TransferRequestSerializer(serializers.Serializer):
    from_account = serializers.IntegerField()
    to_account = serializers.IntegerField(required=False, help_text="One of your own accounts")
    beneficiary = serializers.IntegerField(required=False, help_text="A confirmed beneficiary")
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    remarks = serializers.CharField(max_length=140, required=False, allow_blank=True)

    def validate(self, attrs):
        if bool(attrs.get("to_account")) == bool(attrs.get("beneficiary")):
            raise serializers.ValidationError("Send to exactly one of: to_account, beneficiary.")
        return attrs


class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = [
            "id",
            "reference",
            "uetr",
            "kind",
            "status",
            "from_account",
            "to_account",
            "beneficiary",
            "creditor_name",
            "creditor_iban",
            "amount",
            "currency",
            "remarks",
            "created_at",
        ]
        read_only_fields = fields
