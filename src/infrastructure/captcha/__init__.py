"""CAPTCHA solving infrastructure for browser automation."""

from .captcha_solver import (
    AntiCaptchaSolver,
    CaptchaSolution,
    CaptchaSolver,
    CaptchaType,
    TwoCaptchaSolver,
    get_captcha_solver,
)

__all__ = [
    "CaptchaSolver",
    "CaptchaType",
    "CaptchaSolution",
    "TwoCaptchaSolver",
    "AntiCaptchaSolver",
    "get_captcha_solver",
]
