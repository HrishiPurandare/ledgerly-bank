from django.urls import path

from payments.views import (
    BeneficiaryConfirm,
    BeneficiaryDetail,
    BeneficiaryList,
    TransferDetail,
    TransferList,
    TransferPacs008,
)

beneficiary_urls = [
    path("", BeneficiaryList.as_view(), name="beneficiary-list"),
    path("<int:pk>/", BeneficiaryDetail.as_view(), name="beneficiary-detail"),
    path("<int:pk>/confirm/", BeneficiaryConfirm.as_view(), name="beneficiary-confirm"),
]
transfer_urls = [
    path("", TransferList.as_view(), name="transfer-list"),
    path("<int:pk>/", TransferDetail.as_view(), name="transfer-detail"),
    path("<int:pk>/pacs008/", TransferPacs008.as_view(), name="transfer-pacs008"),
]
