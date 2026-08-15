from fastapi import HTTPException, status


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str, identifier: str | int) -> None:
        super().__init__(f"{resource} with id={identifier} not found", status_code=404)


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class AuthorizationError(AppException):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, status_code=403)


class ValidationError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class RateLimitError(AppException):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, status_code=429)


class LLMError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(f"LLM error: {message}", status_code=503)


class EmbeddingError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(f"Embedding error: {message}", status_code=503)


class VectorDBError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(f"Vector DB error: {message}", status_code=503)


class InsufficientContextError(AppException):
    def __init__(self) -> None:
        super().__init__(
            "The uploaded legal corpus does not contain sufficient "
            "evidence to answer this question.",
            status_code=422,
        )


# HTTP shortcuts
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
