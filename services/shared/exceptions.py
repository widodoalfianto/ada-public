"""
Shared exception classes and error handling utilities.

This module provides consistent error handling patterns across all services.
"""
from typing import Optional, Dict, Any
import logging
import traceback


logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exception Classes
# =============================================================================

class AdaException(Exception):
    """Base exception for all Ada services."""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to API-friendly dict."""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class DatabaseError(AdaException):
    """Database operation failed."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATABASE_ERROR", details)


class NotFoundError(AdaException):
    """Requested resource not found."""
    
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            f"{resource} not found: {identifier}",
            "NOT_FOUND",
            {"resource": resource, "identifier": str(identifier)}
        )


class ValidationError(AdaException):
    """Input validation failed."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(message, "VALIDATION_ERROR", details)


class ExternalServiceError(AdaException):
    """External API/service call failed."""
    
    def __init__(self, service: str, message: str, status_code: Optional[int] = None):
        super().__init__(
            f"{service}: {message}",
            "EXTERNAL_SERVICE_ERROR",
            {"service": service, "status_code": status_code}
        )


class RateLimitError(AdaException):
    """Rate limit exceeded."""
    
    def __init__(self, service: str, retry_after: Optional[int] = None):
        super().__init__(
            f"Rate limit exceeded for {service}",
            "RATE_LIMIT_ERROR",
            {"service": service, "retry_after": retry_after}
        )


# =============================================================================
# Error Handling Utilities
# =============================================================================

def log_exception(
    e: Exception, 
    context: str = "",
    include_traceback: bool = True
) -> Dict[str, Any]:
    """
    Log an exception with consistent formatting.
    
    Args:
        e: The exception to log
        context: Additional context about where the error occurred
        include_traceback: Whether to include full traceback
    
    Returns:
        Dict with error details for API response
    """
    error_info = {
        "error": True,
        "message": str(e),
        "type": type(e).__name__
    }
    
    if context:
        error_info["context"] = context
    
    if isinstance(e, AdaException):
        error_info.update(e.to_dict())
        logger.error(f"[{e.error_code}] {context}: {e.message}", extra=e.details)
    else:
        logger.error(f"[UNHANDLED] {context}: {e}")
        if include_traceback:
            logger.debug(traceback.format_exc())
    
    return error_info


def safe_execute(func, *args, context: str = "", default=None, **kwargs):
    """
    Execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        context: Context string for error logging
        default: Default value to return on error
        **kwargs: Keyword arguments
    
    Returns:
        Function result or default value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log_exception(e, context)
        return default


# =============================================================================
# FastAPI Error Handler (for services using FastAPI)
# =============================================================================

def create_api_error_response(e: Exception, status_code: int = 500) -> Dict[str, Any]:
    """
    Create a standardized API error response.
    
    Args:
        e: The exception
        status_code: HTTP status code
    
    Returns:
        Dict for JSON response
    """
    if isinstance(e, AdaException):
        return e.to_dict()
    
    return {
        "error": True,
        "error_code": "INTERNAL_ERROR",
        "message": str(e),
        "details": {}
    }
