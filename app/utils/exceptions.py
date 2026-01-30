"""
Custom Exceptions
"""
from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    """Resource not found (404)"""
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class ValidationException(HTTPException):
    """Validation error (400)"""
    def __init__(self, detail: str = "Validation error"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class UnauthorizedException(HTTPException):
    """Unauthorized access (401)"""
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class OpenAIException(Exception):
    """OpenRouter API error"""
    pass


"""
Giải thích:
- HTTPException: FastAPI tự động convert thành HTTP response
- Custom exceptions giúp code rõ ràng hơn

Usage:
    from app.utils.exceptions import NotFoundException
    
    if not user:
        raise NotFoundException("User not found")
"""