from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "date_joined"]
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["email", "full_name", "password"]

    def validate_email(self, value: str) -> str:
        # Case-insensitive uniqueness: Sam@x.com and sam@x.com are the same customer.
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        # Run Django's password rules (length, common passwords, similarity to the email/name).
        validate_password(attrs["password"], user=User(email=attrs["email"], full_name=attrs["full_name"]))
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
