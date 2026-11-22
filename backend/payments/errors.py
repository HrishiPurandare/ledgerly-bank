from rest_framework import status
from rest_framework.exceptions import APIException


class TransferRejected(APIException):
    """A business rule said no. The `code` is stable, so clients and tests match on it, not on wording."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code: str, detail: str, status_code: int | None = None):
        super().__init__(detail={"code": code, "detail": detail})
        if status_code:
            self.status_code = status_code
