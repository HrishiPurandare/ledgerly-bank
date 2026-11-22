from django.urls import path

from banking.views import AccountDetail, AccountList, AccountTransactions

urlpatterns = [
    path("", AccountList.as_view(), name="account-list"),
    path("<int:pk>/", AccountDetail.as_view(), name="account-detail"),
    path("<int:pk>/transactions/", AccountTransactions.as_view(), name="account-transactions"),
]
