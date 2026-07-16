class AppError(Exception):
    status_code = 500
    detail = "An unexpected application error occurred."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found."


class AuthenticationError(AppError):
    status_code = 401
    detail = "Authentication failed."


class AuthorizationError(AppError):
    status_code = 403
    detail = "You are not allowed to perform this action."


class ConflictError(AppError):
    status_code = 409
    detail = "The resource conflicts with existing data."


class RateLimitError(AppError):
    status_code = 429
    detail = "Rate limit exceeded."


class AIProviderError(AppError):
    status_code = 503
    detail = "The AI provider is currently unavailable."


class ExecutionTimeoutError(AppError):
    status_code = 504
    detail = "Code execution timed out."


class ConfigurationError(AppError):
    status_code = 503
    detail = "The requested integration is not configured."
