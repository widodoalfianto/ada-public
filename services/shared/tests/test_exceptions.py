"""
Tests for shared exception utilities.
"""
import pytest


class TestAdaException:
    """Tests for AdaException base class."""
    
    def test_basic_exception(self):
        """Test basic exception creation."""
        from shared.exceptions import AdaException
        
        exc = AdaException("Something went wrong")
        
        assert exc.message == "Something went wrong"
        assert exc.error_code == "INTERNAL_ERROR"
        assert exc.details == {}
    
    def test_exception_with_code_and_details(self):
        """Test exception with custom code and details."""
        from shared.exceptions import AdaException
        
        exc = AdaException(
            "Custom error",
            error_code="CUSTOM_CODE",
            details={"field": "value"}
        )
        
        assert exc.error_code == "CUSTOM_CODE"
        assert exc.details["field"] == "value"
    
    def test_to_dict(self):
        """Test exception serialization to dict."""
        from shared.exceptions import AdaException
        
        exc = AdaException("Test", error_code="TEST_CODE", details={"key": 123})
        result = exc.to_dict()
        
        assert result["error"] == True
        assert result["error_code"] == "TEST_CODE"
        assert result["message"] == "Test"
        assert result["details"]["key"] == 123


class TestSpecializedException:
    """Tests for specialized exception classes."""
    
    def test_database_error(self):
        """Test DatabaseError creation."""
        from shared.exceptions import DatabaseError
        
        exc = DatabaseError("Connection failed", details={"host": "localhost"})
        
        assert exc.error_code == "DATABASE_ERROR"
        assert "Connection failed" in exc.message
    
    def test_not_found_error(self):
        """Test NotFoundError creation."""
        from shared.exceptions import NotFoundError
        
        exc = NotFoundError("Stock", "AAPL")
        
        assert exc.error_code == "NOT_FOUND"
        assert "Stock" in exc.message
        assert "AAPL" in exc.message
        assert exc.details["resource"] == "Stock"
        assert exc.details["identifier"] == "AAPL"
    
    def test_validation_error(self):
        """Test ValidationError creation."""
        from shared.exceptions import ValidationError
        
        exc = ValidationError("Invalid email format", field="email")
        
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.details["field"] == "email"
    
    def test_external_service_error(self):
        """Test ExternalServiceError creation."""
        from shared.exceptions import ExternalServiceError
        
        exc = ExternalServiceError("Finnhub", "Rate limit exceeded", status_code=429)
        
        assert exc.error_code == "EXTERNAL_SERVICE_ERROR"
        assert "Finnhub" in exc.message
        assert exc.details["status_code"] == 429
    
    def test_rate_limit_error(self):
        """Test RateLimitError creation."""
        from shared.exceptions import RateLimitError
        
        exc = RateLimitError("Discord", retry_after=60)
        
        assert exc.error_code == "RATE_LIMIT_ERROR"
        assert exc.details["retry_after"] == 60


class TestLogException:
    """Tests for log_exception utility."""
    
    def test_log_ada_exception(self):
        """Test logging a AdaException."""
        from shared.exceptions import log_exception, NotFoundError
        
        exc = NotFoundError("Stock", "XYZ")
        result = log_exception(exc, context="test_context")
        
        assert result["error"] == True
        assert "NOT_FOUND" in result.get("error_code", "")
    
    def test_log_generic_exception(self):
        """Test logging a generic exception."""
        from shared.exceptions import log_exception
        
        exc = ValueError("Bad value")
        result = log_exception(exc, context="test_context")
        
        assert result["error"] == True
        assert result["type"] == "ValueError"


class TestCreateApiErrorResponse:
    """Tests for create_api_error_response utility."""
    
    def test_ada_exception_response(self):
        """Test API response for AdaException."""
        from shared.exceptions import create_api_error_response, NotFoundError
        
        exc = NotFoundError("User", 123)
        response = create_api_error_response(exc)
        
        assert response["error"] == True
        assert response["error_code"] == "NOT_FOUND"
    
    def test_generic_exception_response(self):
        """Test API response for generic exception."""
        from shared.exceptions import create_api_error_response
        
        exc = RuntimeError("Something broke")
        response = create_api_error_response(exc)
        
        assert response["error"] == True
        assert response["error_code"] == "INTERNAL_ERROR"
