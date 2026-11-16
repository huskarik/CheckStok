class BusinessError(Exception):
    status_code = 400

    def __init__(
        self,
        detail: str,
        *,
        code: str,
        context: dict | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.context = context


class InvalidOperationError(BusinessError):
    status_code = 422


class NotFoundError(BusinessError):
    status_code = 404


class ConflictError(BusinessError):
    status_code = 409
