from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from payments.urls import beneficiary_urls, transfer_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", include("core.urls")),
    path("api/auth/", include("users.urls")),
    path("api/accounts/", include("banking.urls")),
    path("api/beneficiaries/", include(beneficiary_urls)),
    path("api/transfers/", include(transfer_urls)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
