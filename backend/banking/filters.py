import django_filters

from banking.models import Transaction


class TransactionFilter(django_filters.FilterSet):
    """Statement filters: /transactions/?direction=DEBIT&category=CARD&date_from=2026-11-01&min_amount=100"""

    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    min_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search", label="Text in description or counterparty")

    class Meta:
        model = Transaction
        fields = ["direction", "category"]

    def filter_search(self, queryset, name, value):
        from django.db.models import Q

        return queryset.filter(Q(description__icontains=value) | Q(counterparty__icontains=value))
