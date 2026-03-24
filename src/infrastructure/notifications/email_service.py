"""Email notification service using SMTP."""

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from loguru import logger


@dataclass
class EmailConfig:
    """Email service configuration."""

    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    use_tls: bool = True
    from_email: str = "noreply@tawiza.local"
    from_name: str = "Tawiza Notifications"


class EmailService:
    """Service for sending email notifications.

    Supports SMTP with TLS/SSL for secure email delivery.
    Can be configured via environment variables or direct initialization.
    """

    def __init__(self, config: EmailConfig | None = None):
        """
        Initialize email service.

        Args:
            config: Email configuration. If None, loads from environment.
        """
        if config:
            self.config = config
        else:
            self.config = self._load_config_from_env()

        self._enabled = bool(self.config.smtp_host and self.config.smtp_host != "localhost")

        if self._enabled:
            logger.info(
                f"Email service initialized: {self.config.smtp_host}:{self.config.smtp_port}"
            )
        else:
            logger.debug("Email service disabled (no SMTP host configured)")

    def _load_config_from_env(self) -> EmailConfig:
        """Load configuration from environment variables."""
        import os

        return EmailConfig(
            smtp_host=os.getenv("SMTP_HOST", "localhost"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            from_email=os.getenv("SMTP_FROM_EMAIL", "noreply@tawiza.local"),
            from_name=os.getenv("SMTP_FROM_NAME", "Tawiza Notifications"),
        )

    @property
    def is_enabled(self) -> bool:
        """Check if email service is enabled."""
        return self._enabled

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html_body: str | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        """
        Send an email.

        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            reply_to: Optional reply-to address

        Returns:
            Result dict with status and message
        """
        if not self._enabled:
            logger.debug(f"Email not sent (disabled): {subject} -> {to}")
            return {"status": "disabled", "message": "Email service not configured"}

        # Normalize recipients
        recipients = [to] if isinstance(to, str) else to

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = ", ".join(recipients)

            if reply_to:
                msg["Reply-To"] = reply_to

            # Attach plain text
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # Attach HTML if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Send in thread pool to not block
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._send_smtp,
                recipients,
                msg.as_string(),
            )

            logger.info(f"Email sent: '{subject}' -> {recipients}")
            return {"status": "sent", "recipients": recipients}

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"status": "error", "message": str(e)}

    def _send_smtp(self, recipients: list[str], message: str) -> None:
        """Send email via SMTP (blocking, run in executor)."""
        context = ssl.create_default_context()

        if self.config.use_tls:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls(context=context)
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_email, recipients, message)
        else:
            with smtplib.SMTP_SSL(
                self.config.smtp_host, self.config.smtp_port, context=context
            ) as server:
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_email, recipients, message)

    async def send_analysis_notification(
        self,
        to: str,
        analysis_name: str,
        analysis_id: str,
        response_preview: str,
        dashboard_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Send analysis completion notification.

        Args:
            to: Recipient email
            analysis_name: Name of the analysis
            analysis_id: Analysis ID
            response_preview: Preview of the response
            dashboard_url: Optional link to dashboard

        Returns:
            Send result
        """
        subject = f"[Tawiza] Analyse terminée: {analysis_name}"

        body = f"""Bonjour,

Votre analyse TAJINE "{analysis_name}" est terminée.

Résumé:
{response_preview[:500]}{"..." if len(response_preview) > 500 else ""}

ID de l'analyse: {analysis_id}
"""

        if dashboard_url:
            body += f"\nVoir les détails: {dashboard_url}/dashboard/analytics\n"

        body += "\n--\nTawiza - Intelligence Territoriale"

        # HTML version
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; }}
        .preview {{ background: white; padding: 15px; border-radius: 4px; border-left: 3px solid #00d4aa; margin: 15px 0; }}
        .btn {{ display: inline-block; background: #00d4aa; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }}
        .footer {{ color: #666; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>✨ Analyse TAJINE terminée</h2>
        </div>
        <div class="content">
            <p>Votre analyse <strong>"{analysis_name}"</strong> est terminée.</p>

            <div class="preview">
                <strong>Résumé:</strong><br>
                {response_preview[:500]}{"..." if len(response_preview) > 500 else ""}
            </div>

            <p><small>ID: {analysis_id}</small></p>

            {'<p><a href="' + dashboard_url + '/dashboard/analytics" class="btn">Voir les détails</a></p>' if dashboard_url else ""}

            <div class="footer">
                Tawiza - Intelligence Territoriale
            </div>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(to, subject, body, html_body)


# Global instance (lazy loaded)
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get or create the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
