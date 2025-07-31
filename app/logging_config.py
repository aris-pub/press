"""Centralized logging configuration for Scroll Press application."""

import logging
import os
import sys
from typing import Optional

from fastapi import Request


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure and return the application logger.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("scroll_press")

    if logger.handlers:
        return logger

    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Prevent duplicate logs
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """Get the application logger instance."""
    return logging.getLogger("scroll_press")


def log_request(
    request: Request, user_id: Optional[str] = None, extra_data: Optional[dict] = None
) -> None:
    """Log incoming HTTP request details.

    Args:
        request: FastAPI request object
        user_id: Optional user ID for authenticated requests
        extra_data: Optional additional data to log
    """
    logger = get_logger()

    log_data = {
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "client_ip": getattr(request.client, "host", "unknown") if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
    }

    if user_id:
        log_data["user_id"] = user_id

    if extra_data:
        log_data.update(extra_data)

    logger.info(f"Request: {log_data}")


def log_response(
    request: Request,
    status_code: int,
    user_id: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> None:
    """Log HTTP response details.

    Args:
        request: FastAPI request object
        status_code: HTTP response status code
        user_id: Optional user ID for authenticated requests
        extra_data: Optional additional data to log
    """
    logger = get_logger()

    log_data = {
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "client_ip": getattr(request.client, "host", "unknown") if request.client else "unknown",
    }

    if user_id:
        log_data["user_id"] = user_id

    if extra_data:
        log_data.update(extra_data)

    logger.info(f"Response: {log_data}")


def log_auth_event(
    event_type: str,
    email: str,
    success: bool,
    request: Request,
    user_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Log authentication events.

    Args:
        event_type: Type of auth event (login, register, logout)
        email: User email address
        success: Whether the operation was successful
        request: FastAPI request object
        user_id: Optional user ID (for successful operations)
        error_message: Optional error message (for failed operations)
    """
    logger = get_logger()

    log_data = {
        "event_type": event_type,
        "email": email,
        "success": success,
        "client_ip": getattr(request.client, "host", "unknown") if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
    }

    if user_id:
        log_data["user_id"] = user_id

    if error_message:
        log_data["error"] = error_message

    level = logging.INFO if success else logging.WARNING
    logger.log(level, f"Auth event: {log_data}")


def log_preview_event(
    event_type: str,
    preview_id: str,
    user_id: str,
    request: Request,
    extra_data: Optional[dict] = None,
) -> None:
    """Log scroll-related events.

    Args:
        event_type: Type of scroll event (create, publish, view)
        preview_id: Scroll ID or UUID
        user_id: User ID performing the action
        request: FastAPI request object
        extra_data: Optional additional data to log
    """
    logger = get_logger()

    log_data = {
        "event_type": event_type,
        "preview_id": preview_id,
        "user_id": user_id,
        "client_ip": getattr(request.client, "host", "unknown") if request.client else "unknown",
    }

    if extra_data:
        log_data.update(extra_data)

    logger.info(f"Scroll event: {log_data}")


def log_error(
    error: Exception,
    request: Request,
    user_id: Optional[str] = None,
    context: Optional[str] = None,
) -> None:
    """Log application errors.

    Args:
        error: Exception that occurred
        request: FastAPI request object
        user_id: Optional user ID
        context: Optional context description
    """
    logger = get_logger()

    log_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "path": request.url.path,
        "method": request.method,
        "client_ip": getattr(request.client, "host", "unknown") if request.client else "unknown",
    }

    if user_id:
        log_data["user_id"] = user_id

    if context:
        log_data["context"] = context

    logger.error(f"Application error: {log_data}", exc_info=True)


def log_database_event(
    operation: str,
    table: str,
    record_id: Optional[str] = None,
    user_id: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> None:
    """Log database operations.

    Args:
        operation: Database operation (create, update, delete)
        table: Database table name
        record_id: Optional record ID
        user_id: Optional user ID performing the operation
        extra_data: Optional additional data to log
    """
    logger = get_logger()

    log_data = {
        "operation": operation,
        "table": table,
    }

    if record_id:
        log_data["record_id"] = record_id

    if user_id:
        log_data["user_id"] = user_id

    if extra_data:
        log_data.update(extra_data)

    logger.info(f"Database event: {log_data}")


# Initialize logging on import
_log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(_log_level)
