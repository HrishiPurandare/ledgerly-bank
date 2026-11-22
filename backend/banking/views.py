from django.shortcuts import get_object_or_404
from rest_framework import generics

from banking.filters import TransactionFilter
from banking.models import Account, Transaction
from banking.serializers import AccountSerializer, TransactionSerializer


class AccountList(generics.ListAPIView):
    """The logged-in customer's accounts."""

    serializer_class = AccountSerializer
    queryset = Account.objects.none()  # tells the schema generator the model; real data is get_queryset

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user)


class AccountDetail(generics.RetrieveAPIView):
    """One account. Someone else's account is a 404, not a 403: we don't even confirm it exists."""

    serializer_class = AccountSerializer
    queryset = Account.objects.none()  # tells the schema generator the model; real data is get_queryset

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user)


class AccountTransactions(generics.ListAPIView):
    """The account's statement, newest first, with filters and pagination."""

    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation: no user, no URL kwargs
            return Transaction.objects.none()
        # Ownership is checked on the ACCOUNT, so /accounts/<someone else's id>/transactions/ is a 404 too.
        account = get_object_or_404(Account, pk=self.kwargs["pk"], owner=self.request.user)
        return account.transactions.all()
