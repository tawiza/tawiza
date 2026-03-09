"""Notification services."""

from .email_service import EmailConfig, EmailService, get_email_service

__all__ = ["EmailService", "EmailConfig", "get_email_service"]
