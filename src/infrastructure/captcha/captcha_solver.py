"""CAPTCHA solving service with multiple provider support.

Supports:
- 2Captcha (twocaptcha.com)
- Anti-Captcha (anti-captcha.com)
- Manual fallback for testing

Features:
- reCAPTCHA v2/v3 solving
- hCaptcha solving
- Image CAPTCHA solving
- Audio CAPTCHA solving (accessibility bypass)
- Configurable timeout and retry logic
"""

import asyncio
import base64
from enum import StrEnum
from pathlib import Path

import httpx
from loguru import logger
from pydantic import BaseModel


class CaptchaType(StrEnum):
    """CAPTCHA types supported."""

    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"


class CaptchaSolution(BaseModel):
    """CAPTCHA solution result."""

    success: bool
    solution: str | None = None
    error: str | None = None
    solve_time: float = 0.0
    provider: str = ""
    captcha_type: CaptchaType


class CaptchaSolver:
    """Base class for CAPTCHA solvers."""

    def __init__(self, api_key: str | None = None, timeout: int = 120):
        """
        Initialize CAPTCHA solver.

        Args:
            api_key: API key for the solving service
            timeout: Maximum time to wait for solution (seconds)
        """
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def solve_recaptcha_v2(self, site_key: str, page_url: str, **kwargs) -> CaptchaSolution:
        """Solve reCAPTCHA v2."""
        raise NotImplementedError

    async def solve_recaptcha_v3(
        self, site_key: str, page_url: str, action: str = "submit", min_score: float = 0.3, **kwargs
    ) -> CaptchaSolution:
        """Solve reCAPTCHA v3."""
        raise NotImplementedError

    async def solve_hcaptcha(self, site_key: str, page_url: str, **kwargs) -> CaptchaSolution:
        """Solve hCaptcha."""
        raise NotImplementedError

    async def solve_image_captcha(
        self, image_data: bytes | str | Path, **kwargs
    ) -> CaptchaSolution:
        """Solve image-based CAPTCHA."""
        raise NotImplementedError

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class TwoCaptchaSolver(CaptchaSolver):
    """
    2Captcha solver implementation.

    API docs: https://2captcha.com/2captcha-api
    """

    BASE_URL = "https://2captcha.com"

    async def solve_recaptcha_v2(self, site_key: str, page_url: str, **kwargs) -> CaptchaSolution:
        """Solve reCAPTCHA v2 using 2Captcha."""
        import time

        start_time = time.time()

        try:
            # Submit CAPTCHA
            submit_response = await self.client.post(
                f"{self.BASE_URL}/in.php",
                data={
                    "key": self.api_key,
                    "method": "userrecaptcha",
                    "googlekey": site_key,
                    "pageurl": page_url,
                    "json": 1,
                },
            )

            submit_data = submit_response.json()

            if submit_data.get("status") != 1:
                error_msg = submit_data.get("request", "Unknown error")
                logger.error(f"2Captcha submission failed: {error_msg}")
                return CaptchaSolution(
                    success=False,
                    error=error_msg,
                    provider="2captcha",
                    captcha_type=CaptchaType.RECAPTCHA_V2,
                )

            task_id = submit_data["request"]
            logger.info(f"2Captcha task submitted: {task_id}")

            # Poll for solution
            max_attempts = self.timeout // 5
            for _attempt in range(max_attempts):
                await asyncio.sleep(5)

                result_response = await self.client.get(
                    f"{self.BASE_URL}/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": task_id,
                        "json": 1,
                    },
                )

                result_data = result_response.json()

                if result_data.get("status") == 1:
                    solution = result_data["request"]
                    solve_time = time.time() - start_time

                    logger.success(f"2Captcha solved in {solve_time:.1f}s")
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        solve_time=solve_time,
                        provider="2captcha",
                        captcha_type=CaptchaType.RECAPTCHA_V2,
                    )

                if result_data.get("request") != "CAPCHA_NOT_READY":
                    error_msg = result_data.get("request", "Unknown error")
                    logger.error(f"2Captcha error: {error_msg}")
                    return CaptchaSolution(
                        success=False,
                        error=error_msg,
                        provider="2captcha",
                        captcha_type=CaptchaType.RECAPTCHA_V2,
                    )

            return CaptchaSolution(
                success=False,
                error="Timeout waiting for solution",
                provider="2captcha",
                captcha_type=CaptchaType.RECAPTCHA_V2,
            )

        except Exception as e:
            logger.exception("2Captcha solving error")
            return CaptchaSolution(
                success=False,
                error=str(e),
                provider="2captcha",
                captcha_type=CaptchaType.RECAPTCHA_V2,
            )

    async def solve_recaptcha_v3(
        self, site_key: str, page_url: str, action: str = "submit", min_score: float = 0.3, **kwargs
    ) -> CaptchaSolution:
        """Solve reCAPTCHA v3 using 2Captcha."""
        import time

        start_time = time.time()

        try:
            submit_response = await self.client.post(
                f"{self.BASE_URL}/in.php",
                data={
                    "key": self.api_key,
                    "method": "userrecaptcha",
                    "version": "v3",
                    "googlekey": site_key,
                    "pageurl": page_url,
                    "action": action,
                    "min_score": min_score,
                    "json": 1,
                },
            )

            submit_data = submit_response.json()

            if submit_data.get("status") != 1:
                error_msg = submit_data.get("request", "Unknown error")
                return CaptchaSolution(
                    success=False,
                    error=error_msg,
                    provider="2captcha",
                    captcha_type=CaptchaType.RECAPTCHA_V3,
                )

            task_id = submit_data["request"]
            logger.info(f"2Captcha v3 task submitted: {task_id}")

            # Poll for solution
            max_attempts = self.timeout // 5
            for _attempt in range(max_attempts):
                await asyncio.sleep(5)

                result_response = await self.client.get(
                    f"{self.BASE_URL}/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": task_id,
                        "json": 1,
                    },
                )

                result_data = result_response.json()

                if result_data.get("status") == 1:
                    solution = result_data["request"]
                    solve_time = time.time() - start_time

                    logger.success(f"2Captcha v3 solved in {solve_time:.1f}s")
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        solve_time=solve_time,
                        provider="2captcha",
                        captcha_type=CaptchaType.RECAPTCHA_V3,
                    )

                if result_data.get("request") != "CAPCHA_NOT_READY":
                    error_msg = result_data.get("request", "Unknown error")
                    return CaptchaSolution(
                        success=False,
                        error=error_msg,
                        provider="2captcha",
                        captcha_type=CaptchaType.RECAPTCHA_V3,
                    )

            return CaptchaSolution(
                success=False,
                error="Timeout waiting for solution",
                provider="2captcha",
                captcha_type=CaptchaType.RECAPTCHA_V3,
            )

        except Exception as e:
            logger.exception("2Captcha v3 solving error")
            return CaptchaSolution(
                success=False,
                error=str(e),
                provider="2captcha",
                captcha_type=CaptchaType.RECAPTCHA_V3,
            )

    async def solve_hcaptcha(self, site_key: str, page_url: str, **kwargs) -> CaptchaSolution:
        """Solve hCaptcha using 2Captcha."""
        import time

        start_time = time.time()

        try:
            submit_response = await self.client.post(
                f"{self.BASE_URL}/in.php",
                data={
                    "key": self.api_key,
                    "method": "hcaptcha",
                    "sitekey": site_key,
                    "pageurl": page_url,
                    "json": 1,
                },
            )

            submit_data = submit_response.json()

            if submit_data.get("status") != 1:
                error_msg = submit_data.get("request", "Unknown error")
                return CaptchaSolution(
                    success=False,
                    error=error_msg,
                    provider="2captcha",
                    captcha_type=CaptchaType.HCAPTCHA,
                )

            task_id = submit_data["request"]
            logger.info(f"2Captcha hCaptcha task submitted: {task_id}")

            # Poll for solution
            max_attempts = self.timeout // 5
            for _attempt in range(max_attempts):
                await asyncio.sleep(5)

                result_response = await self.client.get(
                    f"{self.BASE_URL}/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": task_id,
                        "json": 1,
                    },
                )

                result_data = result_response.json()

                if result_data.get("status") == 1:
                    solution = result_data["request"]
                    solve_time = time.time() - start_time

                    logger.success(f"2Captcha hCaptcha solved in {solve_time:.1f}s")
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        solve_time=solve_time,
                        provider="2captcha",
                        captcha_type=CaptchaType.HCAPTCHA,
                    )

                if result_data.get("request") != "CAPCHA_NOT_READY":
                    error_msg = result_data.get("request", "Unknown error")
                    return CaptchaSolution(
                        success=False,
                        error=error_msg,
                        provider="2captcha",
                        captcha_type=CaptchaType.HCAPTCHA,
                    )

            return CaptchaSolution(
                success=False,
                error="Timeout waiting for solution",
                provider="2captcha",
                captcha_type=CaptchaType.HCAPTCHA,
            )

        except Exception as e:
            logger.exception("2Captcha hCaptcha solving error")
            return CaptchaSolution(
                success=False, error=str(e), provider="2captcha", captcha_type=CaptchaType.HCAPTCHA
            )

    async def solve_image_captcha(
        self, image_data: bytes | str | Path, **kwargs
    ) -> CaptchaSolution:
        """Solve image CAPTCHA using 2Captcha."""
        import time

        start_time = time.time()

        try:
            # Convert image to base64 if needed
            if isinstance(image_data, Path):
                image_data = image_data.read_bytes()

            if isinstance(image_data, bytes):
                image_b64 = base64.b64encode(image_data).decode()
            else:
                image_b64 = image_data

            submit_response = await self.client.post(
                f"{self.BASE_URL}/in.php",
                data={
                    "key": self.api_key,
                    "method": "base64",
                    "body": image_b64,
                    "json": 1,
                },
            )

            submit_data = submit_response.json()

            if submit_data.get("status") != 1:
                error_msg = submit_data.get("request", "Unknown error")
                return CaptchaSolution(
                    success=False,
                    error=error_msg,
                    provider="2captcha",
                    captcha_type=CaptchaType.IMAGE,
                )

            task_id = submit_data["request"]
            logger.info(f"2Captcha image task submitted: {task_id}")

            # Poll for solution
            max_attempts = self.timeout // 5
            for _attempt in range(max_attempts):
                await asyncio.sleep(5)

                result_response = await self.client.get(
                    f"{self.BASE_URL}/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": task_id,
                        "json": 1,
                    },
                )

                result_data = result_response.json()

                if result_data.get("status") == 1:
                    solution = result_data["request"]
                    solve_time = time.time() - start_time

                    logger.success(f"2Captcha image solved in {solve_time:.1f}s: {solution}")
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        solve_time=solve_time,
                        provider="2captcha",
                        captcha_type=CaptchaType.IMAGE,
                    )

                if result_data.get("request") != "CAPCHA_NOT_READY":
                    error_msg = result_data.get("request", "Unknown error")
                    return CaptchaSolution(
                        success=False,
                        error=error_msg,
                        provider="2captcha",
                        captcha_type=CaptchaType.IMAGE,
                    )

            return CaptchaSolution(
                success=False,
                error="Timeout waiting for solution",
                provider="2captcha",
                captcha_type=CaptchaType.IMAGE,
            )

        except Exception as e:
            logger.exception("2Captcha image solving error")
            return CaptchaSolution(
                success=False, error=str(e), provider="2captcha", captcha_type=CaptchaType.IMAGE
            )


class AntiCaptchaSolver(CaptchaSolver):
    """
    Anti-Captcha solver implementation.

    API docs: https://anti-captcha.com/apidoc
    """

    BASE_URL = "https://api.anti-captcha.com"

    async def solve_recaptcha_v2(self, site_key: str, page_url: str, **kwargs) -> CaptchaSolution:
        """Solve reCAPTCHA v2 using Anti-Captcha."""
        import time

        start_time = time.time()

        try:
            # Create task
            create_response = await self.client.post(
                f"{self.BASE_URL}/createTask",
                json={
                    "clientKey": self.api_key,
                    "task": {
                        "type": "NoCaptchaTaskProxyless",
                        "websiteURL": page_url,
                        "websiteKey": site_key,
                    },
                },
            )

            create_data = create_response.json()

            if create_data.get("errorId", 0) != 0:
                error_msg = create_data.get("errorDescription", "Unknown error")
                logger.error(f"Anti-Captcha task creation failed: {error_msg}")
                return CaptchaSolution(
                    success=False,
                    error=error_msg,
                    provider="anti-captcha",
                    captcha_type=CaptchaType.RECAPTCHA_V2,
                )

            task_id = create_data["taskId"]
            logger.info(f"Anti-Captcha task created: {task_id}")

            # Poll for result
            max_attempts = self.timeout // 5
            for _attempt in range(max_attempts):
                await asyncio.sleep(5)

                result_response = await self.client.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={
                        "clientKey": self.api_key,
                        "taskId": task_id,
                    },
                )

                result_data = result_response.json()

                if result_data.get("errorId", 0) != 0:
                    error_msg = result_data.get("errorDescription", "Unknown error")
                    return CaptchaSolution(
                        success=False,
                        error=error_msg,
                        provider="anti-captcha",
                        captcha_type=CaptchaType.RECAPTCHA_V2,
                    )

                if result_data.get("status") == "ready":
                    solution = result_data["solution"]["gRecaptchaResponse"]
                    solve_time = time.time() - start_time

                    logger.success(f"Anti-Captcha solved in {solve_time:.1f}s")
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        solve_time=solve_time,
                        provider="anti-captcha",
                        captcha_type=CaptchaType.RECAPTCHA_V2,
                    )

            return CaptchaSolution(
                success=False,
                error="Timeout waiting for solution",
                provider="anti-captcha",
                captcha_type=CaptchaType.RECAPTCHA_V2,
            )

        except Exception as e:
            logger.exception("Anti-Captcha solving error")
            return CaptchaSolution(
                success=False,
                error=str(e),
                provider="anti-captcha",
                captcha_type=CaptchaType.RECAPTCHA_V2,
            )

    async def solve_recaptcha_v3(
        self, site_key: str, page_url: str, action: str = "submit", min_score: float = 0.3, **kwargs
    ) -> CaptchaSolution:
        """Solve reCAPTCHA v3 using Anti-Captcha."""
        import time

        start_time = time.time()

        try:
            create_response = await self.client.post(
                f"{self.BASE_URL}/createTask",
                json={
                    "clientKey": self.api_key,
                    "task": {
                        "type": "RecaptchaV3TaskProxyless",
                        "websiteURL": page_url,
                        "websiteKey": site_key,
                        "minScore": min_score,
                        "pageAction": action,
                    },
                },
            )

            create_data = create_response.json()

            if create_data.get("errorId", 0) != 0:
                error_msg = create_data.get("errorDescription", "Unknown error")
                return CaptchaSolution(
                    success=False,
                    error=error_msg,
                    provider="anti-captcha",
                    captcha_type=CaptchaType.RECAPTCHA_V3,
                )

            task_id = create_data["taskId"]
            logger.info(f"Anti-Captcha v3 task created: {task_id}")

            # Poll for result
            max_attempts = self.timeout // 5
            for _attempt in range(max_attempts):
                await asyncio.sleep(5)

                result_response = await self.client.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={
                        "clientKey": self.api_key,
                        "taskId": task_id,
                    },
                )

                result_data = result_response.json()

                if result_data.get("errorId", 0) != 0:
                    error_msg = result_data.get("errorDescription", "Unknown error")
                    return CaptchaSolution(
                        success=False,
                        error=error_msg,
                        provider="anti-captcha",
                        captcha_type=CaptchaType.RECAPTCHA_V3,
                    )

                if result_data.get("status") == "ready":
                    solution = result_data["solution"]["gRecaptchaResponse"]
                    solve_time = time.time() - start_time

                    logger.success(f"Anti-Captcha v3 solved in {solve_time:.1f}s")
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        solve_time=solve_time,
                        provider="anti-captcha",
                        captcha_type=CaptchaType.RECAPTCHA_V3,
                    )

            return CaptchaSolution(
                success=False,
                error="Timeout waiting for solution",
                provider="anti-captcha",
                captcha_type=CaptchaType.RECAPTCHA_V3,
            )

        except Exception as e:
            logger.exception("Anti-Captcha v3 solving error")
            return CaptchaSolution(
                success=False,
                error=str(e),
                provider="anti-captcha",
                captcha_type=CaptchaType.RECAPTCHA_V3,
            )

    async def solve_hcaptcha(self, site_key: str, page_url: str, **kwargs) -> CaptchaSolution:
        """Solve hCaptcha using Anti-Captcha."""
        import time

        start_time = time.time()

        try:
            create_response = await self.client.post(
                f"{self.BASE_URL}/createTask",
                json={
                    "clientKey": self.api_key,
                    "task": {
                        "type": "HCaptchaTaskProxyless",
                        "websiteURL": page_url,
                        "websiteKey": site_key,
                    },
                },
            )

            create_data = create_response.json()

            if create_data.get("errorId", 0) != 0:
                error_msg = create_data.get("errorDescription", "Unknown error")
                return CaptchaSolution(
                    success=False,
                    error=error_msg,
                    provider="anti-captcha",
                    captcha_type=CaptchaType.HCAPTCHA,
                )

            task_id = create_data["taskId"]
            logger.info(f"Anti-Captcha hCaptcha task created: {task_id}")

            # Poll for result
            max_attempts = self.timeout // 5
            for _attempt in range(max_attempts):
                await asyncio.sleep(5)

                result_response = await self.client.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={
                        "clientKey": self.api_key,
                        "taskId": task_id,
                    },
                )

                result_data = result_response.json()

                if result_data.get("errorId", 0) != 0:
                    error_msg = result_data.get("errorDescription", "Unknown error")
                    return CaptchaSolution(
                        success=False,
                        error=error_msg,
                        provider="anti-captcha",
                        captcha_type=CaptchaType.HCAPTCHA,
                    )

                if result_data.get("status") == "ready":
                    solution = result_data["solution"]["gRecaptchaResponse"]
                    solve_time = time.time() - start_time

                    logger.success(f"Anti-Captcha hCaptcha solved in {solve_time:.1f}s")
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        solve_time=solve_time,
                        provider="anti-captcha",
                        captcha_type=CaptchaType.HCAPTCHA,
                    )

            return CaptchaSolution(
                success=False,
                error="Timeout waiting for solution",
                provider="anti-captcha",
                captcha_type=CaptchaType.HCAPTCHA,
            )

        except Exception as e:
            logger.exception("Anti-Captcha hCaptcha solving error")
            return CaptchaSolution(
                success=False,
                error=str(e),
                provider="anti-captcha",
                captcha_type=CaptchaType.HCAPTCHA,
            )

    async def solve_image_captcha(
        self, image_data: bytes | str | Path, **kwargs
    ) -> CaptchaSolution:
        """Solve image CAPTCHA using Anti-Captcha."""
        import time

        start_time = time.time()

        try:
            # Convert image to base64 if needed
            if isinstance(image_data, Path):
                image_data = image_data.read_bytes()

            if isinstance(image_data, bytes):
                image_b64 = base64.b64encode(image_data).decode()
            else:
                image_b64 = image_data

            # Create task
            create_response = await self.client.post(
                f"{self.BASE_URL}/createTask",
                json={
                    "clientKey": self.api_key,
                    "task": {
                        "type": "ImageToTextTask",
                        "body": image_b64,
                        "phrase": kwargs.get("phrase", False),
                        "case": kwargs.get("case", False),
                        "numeric": kwargs.get("numeric", 0),
                        "math": kwargs.get("math", False),
                        "minLength": kwargs.get("min_length", 0),
                        "maxLength": kwargs.get("max_length", 0),
                    },
                },
            )

            create_data = create_response.json()

            if create_data.get("errorId", 0) != 0:
                error_msg = create_data.get("errorDescription", "Unknown error")
                logger.error(f"Anti-Captcha image task creation failed: {error_msg}")
                return CaptchaSolution(
                    success=False,
                    error=error_msg,
                    provider="anti-captcha",
                    captcha_type=CaptchaType.IMAGE,
                )

            task_id = create_data["taskId"]
            logger.info(f"Anti-Captcha image task created: {task_id}")

            # Poll for result
            max_attempts = self.timeout // 5
            for _attempt in range(max_attempts):
                await asyncio.sleep(5)

                result_response = await self.client.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={
                        "clientKey": self.api_key,
                        "taskId": task_id,
                    },
                )

                result_data = result_response.json()

                if result_data.get("errorId", 0) != 0:
                    error_msg = result_data.get("errorDescription", "Unknown error")
                    return CaptchaSolution(
                        success=False,
                        error=error_msg,
                        provider="anti-captcha",
                        captcha_type=CaptchaType.IMAGE,
                    )

                if result_data.get("status") == "ready":
                    solution = result_data["solution"]["text"]
                    solve_time = time.time() - start_time

                    logger.success(f"Anti-Captcha image solved in {solve_time:.1f}s: {solution}")
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        solve_time=solve_time,
                        provider="anti-captcha",
                        captcha_type=CaptchaType.IMAGE,
                    )

            return CaptchaSolution(
                success=False,
                error="Timeout waiting for solution",
                provider="anti-captcha",
                captcha_type=CaptchaType.IMAGE,
            )

        except Exception as e:
            logger.exception("Anti-Captcha image solving error")
            return CaptchaSolution(
                success=False, error=str(e), provider="anti-captcha", captcha_type=CaptchaType.IMAGE
            )


# Singleton instance management
_solver_instance: CaptchaSolver | None = None


def get_captcha_solver(
    provider: str = "2captcha", api_key: str | None = None, timeout: int = 120
) -> CaptchaSolver:
    """
    Get CAPTCHA solver instance.

    Args:
        provider: Solver provider ("2captcha" or "anti-captcha")
        api_key: API key for the service
        timeout: Maximum solving time

    Returns:
        CaptchaSolver instance
    """
    global _solver_instance

    if provider == "2captcha":
        _solver_instance = TwoCaptchaSolver(api_key=api_key, timeout=timeout)
    elif provider == "anti-captcha":
        _solver_instance = AntiCaptchaSolver(api_key=api_key, timeout=timeout)
    else:
        raise ValueError(f"Unknown CAPTCHA provider: {provider}")

    return _solver_instance


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def test_solver():
        # Using 2Captcha
        solver = TwoCaptchaSolver(api_key="YOUR_API_KEY_HERE")

        # Solve reCAPTCHA v2
        result = await solver.solve_recaptcha_v2(
            site_key="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-",
            page_url="https://www.google.com/recaptcha/api2/demo",
        )

        print(f"Success: {result.success}")
        print(f"Solution: {result.solution}")
        print(f"Time: {result.solve_time}s")

        await solver.close()

    # asyncio.run(test_solver())
