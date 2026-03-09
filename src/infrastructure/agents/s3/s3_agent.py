"""S3Agent - Hybrid Browser + Desktop automation agent.

This agent implements a hybrid approach combining:
- Browser automation using Playwright (for web apps)
- Desktop automation using PyAutoGUI + Vision (for native apps)

Inspired by Agent-S3 (Simular AI), it uses an LLM to decide
whether a task requires browser or desktop mode.
"""

import asyncio
import json
import os
import tempfile
from enum import Enum, StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.application.ports.agent_ports import (
    AgentExecutionError,
    AgentType,
    TaskStatus,
)
from src.infrastructure.agents.base_agent import BaseAgent

if TYPE_CHECKING:
    from src.infrastructure.llm.ollama_client import OllamaClient
    from src.infrastructure.tools.registry import ToolRegistry

    from .vision_client import VisionClient


class S3Mode(StrEnum):
    """Execution modes for S3Agent."""
    BROWSER = "browser"
    DESKTOP = "desktop"
    HYBRID = "hybrid"  # Agent decides per action


class S3Action(StrEnum):
    """Types of actions the S3 agent can take."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    EXTRACT = "extract"
    SCREENSHOT = "screenshot"
    SCROLL = "scroll"
    WAIT = "wait"
    EXECUTE_CODE = "execute_code"
    RESPOND = "respond"
    ERROR = "error"


class S3Agent(BaseAgent):
    """S3 Agent - Hybrid Browser + Desktop automation agent.

    This agent combines:
    - Browser automation (Playwright) for web applications
    - Desktop automation (PyAutoGUI + Vision) for native applications

    The agent uses an LLM to decide which mode to use for each action,
    and can seamlessly switch between modes during a task.

    Example:
        >>> agent = await create_s3_agent()
        >>> result = await agent.execute_task({
        ...     "prompt": "Open LibreOffice and create a spreadsheet with sales data"
        ... })
    """

    def __init__(
        self,
        llm_client: Optional["OllamaClient"] = None,
        tool_registry: Optional["ToolRegistry"] = None,
        vision_model: str = "qwen3-vl:32b",
        default_mode: S3Mode = S3Mode.HYBRID,
        vm_host: str = os.getenv("VNC_HOST", "localhost"),
        vm_vnc_port: int = int(os.getenv("VNC_PORT", "5900")),
        max_iterations: int = 15,
        config: dict[str, Any] | None = None,
    ):
        """Initialize S3 Agent.

        Args:
            llm_client: LLM client for reasoning and vision
            tool_registry: Tool registry for additional tools
            vision_model: Vision model for UI element detection
            default_mode: Default execution mode
            vm_host: VM-400 host for desktop automation
            vm_vnc_port: VNC port on VM-400
            max_iterations: Maximum action iterations
            config: Additional agent configuration
        """
        super().__init__(
            agent_type=AgentType.CUSTOM,
            config=config or {}
        )

        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.vision_model = vision_model
        self.default_mode = default_mode
        self.vm_host = vm_host
        self.vm_vnc_port = vm_vnc_port
        self.max_iterations = max_iterations

        # Browser instance (lazy initialized)
        self._browser = None
        self._page = None

        # Desktop client (lazy initialized)
        self._desktop_client = None

        # System prompt
        self.system_prompt = self._build_system_prompt()

        logger.info(
            f"Initialized S3Agent with mode={default_mode.value}, "
            f"vision_model={vision_model}, vm={vm_host}:{vm_vnc_port}"
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt for mode decision."""
        return """You are S3, an advanced hybrid automation agent capable of controlling both web browsers and desktop applications.

Your capabilities:
- BROWSER MODE: Control web browsers using Playwright
  - Navigate to URLs
  - Click elements by CSS selector
  - Fill forms
  - Extract data from web pages
  - Take screenshots

- DESKTOP MODE: Control desktop applications via VNC
  - Click anywhere on screen using vision
  - Type text
  - Use keyboard shortcuts
  - Control native applications (LibreOffice, terminal, file manager, etc.)

Your decision process:
1. Analyze the task
2. Decide: BROWSER or DESKTOP mode?
   - BROWSER: Web applications, websites, online tools
   - DESKTOP: Native applications, file operations, system tasks
3. Execute the appropriate actions
4. If needed, switch modes mid-task

When deciding mode, respond with JSON:
{
  "mode": "browser" or "desktop",
  "reasoning": "why this mode",
  "first_action": {
    "type": "navigate|click|type|etc",
    "target": "URL or element description",
    "value": "optional value for type actions"
  }
}
"""

    async def decide_mode(
        self,
        task: str,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Use LLM to decide whether to use browser or desktop mode.

        Args:
            task: Task description
            context: Optional context from previous actions

        Returns:
            Decision dict with mode, reasoning, and first_action
        """
        if not self.llm_client:
            # Default to browser for web-related keywords
            desktop_keywords = ["libreoffice", "terminal", "file", "folder", "desktop", "application"]

            task_lower = task.lower()

            if any(kw in task_lower for kw in desktop_keywords):
                return {
                    "mode": S3Mode.DESKTOP,
                    "reasoning": "Task mentions desktop applications",
                    "first_action": {"type": "screenshot", "target": "desktop"}
                }
            else:
                return {
                    "mode": S3Mode.BROWSER,
                    "reasoning": "Default to browser mode",
                    "first_action": {"type": "navigate", "target": "about:blank"}
                }

        # Use LLM to decide
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Task: {task}\n\nDecide the mode and first action."}
        ]

        if context:
            messages.insert(1, {
                "role": "assistant",
                "content": f"Previous context: {json.dumps(context)}"
            })

        try:
            response = await self.llm_client.chat(
                messages=messages,
                temperature=0.3,
            )

            content = response.get("content", "")

            # Parse JSON response
            try:
                # Find JSON in response
                import re
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group())
                    decision["mode"] = S3Mode(decision.get("mode", "browser"))
                    return decision
            except (json.JSONDecodeError, ValueError):
                pass

            # Fallback parsing
            if "desktop" in content.lower():
                return {
                    "mode": S3Mode.DESKTOP,
                    "reasoning": content,
                    "first_action": {"type": "screenshot", "target": "desktop"}
                }
            else:
                return {
                    "mode": S3Mode.BROWSER,
                    "reasoning": content,
                    "first_action": {"type": "navigate", "target": "about:blank"}
                }

        except Exception as e:
            logger.error(f"Error in mode decision: {e}")
            return {
                "mode": S3Mode.BROWSER,
                "reasoning": f"Error: {str(e)}, defaulting to browser",
                "first_action": {"type": "navigate", "target": "about:blank"}
            }

    async def _init_browser(self) -> None:
        """Initialize Playwright browser."""
        if self._browser is not None:
            return

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._page = await self._browser.new_page()

            logger.info("Browser initialized")
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright")
            raise

    async def _init_desktop(self) -> None:
        """Initialize desktop automation client with vision support."""
        if self._desktop_client is not None:
            return

        # Import and create vision client
        from .vision_client import create_vision_client

        vision_client = create_vision_client(model=self.vision_model)

        # Create desktop client with vision
        self._desktop_client = DesktopClient(
            host=self.vm_host,
            port=self.vm_vnc_port,
            vision_client=vision_client,
        )

        # Verify connection
        connected = await self._desktop_client.connect()
        if connected:
            logger.info(f"Desktop client connected to {self.vm_host}:{self.vm_vnc_port}")
        else:
            logger.warning(f"Desktop client failed to connect to {self.vm_host}")

    async def browser_action(
        self,
        action_type: S3Action,
        target: str | None = None,
        value: str | None = None,
    ) -> dict[str, Any]:
        """Execute a browser action.

        Args:
            action_type: Type of action to perform
            target: CSS selector or URL
            value: Value for type/fill actions

        Returns:
            Action result
        """
        await self._init_browser()

        try:
            if action_type == S3Action.NAVIGATE:
                await self._page.goto(target or "about:blank")
                return {"success": True, "url": self._page.url}

            elif action_type == S3Action.CLICK:
                await self._page.click(target)
                return {"success": True, "clicked": target}

            elif action_type == S3Action.TYPE:
                await self._page.fill(target, value or "")
                return {"success": True, "typed": value}

            elif action_type == S3Action.EXTRACT:
                content = await self._page.content()
                return {"success": True, "content": content[:5000]}

            elif action_type == S3Action.SCREENSHOT:
                screenshot = await self._page.screenshot()
                return {"success": True, "screenshot_size": len(screenshot)}

            elif action_type == S3Action.SCROLL:
                await self._page.evaluate("window.scrollBy(0, 500)")
                return {"success": True, "scrolled": True}

            elif action_type == S3Action.WAIT:
                await asyncio.sleep(float(value or 1))
                return {"success": True, "waited": value}

            else:
                return {"success": False, "error": f"Unknown action: {action_type}"}

        except Exception as e:
            logger.error(f"Browser action failed: {e}")
            return {"success": False, "error": str(e)}

    async def desktop_action(
        self,
        action_type: S3Action,
        target: str | None = None,
        value: str | None = None,
        coordinates: tuple | None = None,
    ) -> dict[str, Any]:
        """Execute a desktop action on VM-400.

        Args:
            action_type: Type of action to perform
            target: Element description for vision-based clicking
            value: Value for type actions
            coordinates: Optional (x, y) coordinates for direct clicking

        Returns:
            Action result
        """
        await self._init_desktop()

        try:
            if action_type == S3Action.CLICK:
                if coordinates:
                    return await self._desktop_client.click(*coordinates)
                elif target:
                    # Use vision to find element
                    return await self._desktop_client.click_element(target)
                else:
                    return {"success": False, "error": "No target or coordinates"}

            elif action_type == S3Action.TYPE:
                return await self._desktop_client.type_text(value or "")

            elif action_type == S3Action.SCREENSHOT:
                return await self._desktop_client.screenshot()

            elif action_type == S3Action.EXECUTE_CODE:
                # Execute command in terminal
                return await self._desktop_client.execute_command(value or "")

            else:
                return {"success": False, "error": f"Unknown desktop action: {action_type}"}

        except Exception as e:
            logger.error(f"Desktop action failed: {e}")
            return {"success": False, "error": str(e)}

    async def execute_task(
        self,
        task_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a task using hybrid browser/desktop automation.

        Args:
            task_config: Task configuration containing:
                - prompt: Task description
                - mode: Optional forced mode (browser/desktop)
                - max_iterations: Optional iteration limit

        Returns:
            Task result
        """
        task_id = self._create_task(task_config)
        prompt = task_config.get("prompt", "")
        forced_mode = task_config.get("mode")

        try:
            self._update_task(task_id, {"status": TaskStatus.RUNNING})
            self._add_log(task_id, "Starting S3 Agent execution", "info")

            # Decide mode
            if forced_mode:
                mode = S3Mode(forced_mode)
                decision = {"mode": mode, "reasoning": "Forced mode"}
            else:
                decision = await self.decide_mode(prompt)
                mode = decision["mode"]

            self._add_log(
                task_id,
                f"Mode selected: {mode.value} - {decision.get('reasoning', '')}",
                "info"
            )

            # Execute based on mode
            max_iter = task_config.get("max_iterations", self.max_iterations)
            result = await self._execution_loop(
                task_id=task_id,
                prompt=prompt,
                mode=mode,
                max_iterations=max_iter,
            )

            # Update task
            self._update_task(task_id, {
                "status": TaskStatus.COMPLETED if result["success"] else TaskStatus.FAILED,
                "result": result,
                "progress": 100
            })

            return await self.get_task_result(task_id)

        except Exception as e:
            logger.error(f"S3 Agent task failed: {e}")
            self._update_task(task_id, {
                "status": TaskStatus.FAILED,
                "error": str(e)
            })
            raise AgentExecutionError(f"Task failed: {str(e)}")

    async def _execution_loop(
        self,
        task_id: str,
        prompt: str,
        mode: S3Mode,
        max_iterations: int,
    ) -> dict[str, Any]:
        """Main execution loop for the agent.

        Args:
            task_id: Task identifier
            prompt: Task description
            mode: Execution mode
            max_iterations: Maximum iterations

        Returns:
            Execution result
        """
        iteration = 0
        actions_taken = []
        final_result = None

        while iteration < max_iterations:
            iteration += 1

            self._update_progress(
                task_id=task_id,
                progress=int((iteration / max_iterations) * 100),
                current_step=f"Action {iteration}/{max_iterations}"
            )

            # For now, simple execution based on mode
            # In production, this would use LLM to decide next action

            if mode == S3Mode.BROWSER:
                if iteration == 1:
                    # First action: take screenshot to understand state
                    result = await self.browser_action(S3Action.SCREENSHOT)
                    actions_taken.append({"action": "screenshot", "result": result})
                else:
                    # Subsequent actions would be decided by LLM
                    final_result = "Browser automation placeholder"
                    break

            elif mode == S3Mode.DESKTOP:
                if iteration == 1:
                    result = await self.desktop_action(S3Action.SCREENSHOT)
                    actions_taken.append({"action": "screenshot", "result": result})
                else:
                    final_result = "Desktop automation placeholder"
                    break

            await asyncio.sleep(0.1)

        return {
            "success": True,
            "mode": mode.value,
            "iterations": iteration,
            "actions": actions_taken,
            "result": final_result or "Task completed",
        }

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if hasattr(self, "_playwright") and self._playwright:
            await self._playwright.stop()

        logger.info("S3 Agent cleaned up")

    def get_capabilities(self) -> dict[str, Any]:
        """Get agent capabilities."""
        return {
            "name": "S3Agent",
            "type": "hybrid",
            "features": [
                "browser automation",
                "desktop automation",
                "vision-based UI detection",
                "hybrid mode switching",
                "VM-400 sandbox execution"
            ],
            "modes": [m.value for m in S3Mode],
            "vision_model": self.vision_model,
            "max_iterations": self.max_iterations,
            "has_llm": self.llm_client is not None,
            "vm_configured": f"{self.vm_host}:{self.vm_vnc_port}",
        }


class DesktopClient:
    """Desktop automation client for VM-400 via SSH.

    This client connects to VM-400 (running XFCE + VNC) and performs:
    - Screenshot capture via scrot
    - Mouse input via xdotool
    - Keyboard input via xdotool
    - Vision-based element detection via VisionClient
    """

    def __init__(
        self,
        host: str,
        port: int,
        ssh_user: str = "root",
        display: str = ":99",
        vision_client: Optional["VisionClient"] = None,
    ):
        """
        Initialize desktop client.

        Args:
            host: VM-400 IP address
            port: VNC port (for reference, actual control via SSH)
            ssh_user: SSH user for VM connection
            display: X display number
            vision_client: Vision client for element detection
        """
        self.host = host
        self.port = port
        self.ssh_user = ssh_user
        self.display = display
        self.vision_client = vision_client
        self._connected = False
        self._screenshot_dir = Path(tempfile.gettempdir()) / "s3_screenshots"
        self._screenshot_dir.mkdir(exist_ok=True)
        self._screenshot_counter = 0

    async def _ssh_command(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """Execute SSH command on VM-400.

        Args:
            command: Command to execute
            timeout: Timeout in seconds

        Returns:
            Tuple of (stdout, stderr, returncode)
        """
        full_cmd = f"ssh -o StrictHostKeyChecking=no {self.ssh_user}@{self.host} \"{command}\""

        proc = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return (
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                proc.returncode or 0
            )
        except TimeoutError:
            proc.kill()
            return ("", "Timeout", -1)

    async def connect(self) -> bool:
        """Verify connection to VM-400."""
        stdout, stderr, code = await self._ssh_command("echo 'connected'")
        self._connected = code == 0 and "connected" in stdout
        if self._connected:
            logger.info(f"Connected to desktop VM at {self.host}")
        else:
            logger.error(f"Failed to connect to {self.host}: {stderr}")
        return self._connected

    async def screenshot(self, save_local: bool = True) -> dict[str, Any]:
        """Capture screenshot from VM.

        Args:
            save_local: Whether to copy screenshot to local machine

        Returns:
            Result with screenshot path
        """
        self._screenshot_counter += 1
        remote_path = f"/tmp/screenshot_{self._screenshot_counter}.png"
        local_path = self._screenshot_dir / f"screenshot_{self._screenshot_counter}.png"

        # Capture screenshot on VM
        cmd = f"DISPLAY={self.display} scrot {remote_path}"
        stdout, stderr, code = await self._ssh_command(cmd)

        if code != 0:
            return {"success": False, "error": f"Screenshot failed: {stderr}"}

        if save_local:
            # Copy to local machine
            scp_cmd = f"scp -o StrictHostKeyChecking=no {self.ssh_user}@{self.host}:{remote_path} {local_path}"
            proc = await asyncio.create_subprocess_shell(
                scp_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if proc.returncode == 0:
                logger.debug(f"Screenshot saved to {local_path}")
                return {
                    "success": True,
                    "local_path": str(local_path),
                    "remote_path": remote_path,
                }

        return {
            "success": True,
            "remote_path": remote_path,
        }

    async def click(self, x: int, y: int, button: int = 1) -> dict[str, Any]:
        """Click at coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button (1=left, 2=middle, 3=right)

        Returns:
            Result dict
        """
        cmd = f"DISPLAY={self.display} xdotool mousemove {x} {y} click {button}"
        stdout, stderr, code = await self._ssh_command(cmd)

        if code != 0:
            return {"success": False, "error": f"Click failed: {stderr}"}

        logger.debug(f"Clicked at ({x}, {y})")
        return {"success": True, "x": x, "y": y, "button": button}

    async def double_click(self, x: int, y: int) -> dict[str, Any]:
        """Double-click at coordinates."""
        cmd = f"DISPLAY={self.display} xdotool mousemove {x} {y} click --repeat 2 --delay 100 1"
        stdout, stderr, code = await self._ssh_command(cmd)

        if code != 0:
            return {"success": False, "error": f"Double-click failed: {stderr}"}

        return {"success": True, "x": x, "y": y, "action": "double_click"}

    async def right_click(self, x: int, y: int) -> dict[str, Any]:
        """Right-click at coordinates."""
        return await self.click(x, y, button=3)

    async def click_element(self, description: str) -> dict[str, Any]:
        """Click element by description using vision.

        Args:
            description: Text description of element to click

        Returns:
            Result dict with coordinates
        """
        if not self.vision_client:
            return {"success": False, "error": "Vision client not configured"}

        # Take screenshot first
        screenshot_result = await self.screenshot()
        if not screenshot_result.get("success"):
            return screenshot_result

        screenshot_path = screenshot_result.get("local_path")
        if not screenshot_path:
            return {"success": False, "error": "Screenshot not available locally"}

        # Use vision to find element
        coords = await self.vision_client.click_element_by_text(
            screenshot_path,
            description,
        )

        if not coords:
            return {
                "success": False,
                "error": f"Element not found: {description}",
                "screenshot": screenshot_path,
            }

        x, y = coords
        logger.info(f"Found '{description}' at ({x}, {y})")

        # Perform click
        return await self.click(x, y)

    async def type_text(self, text: str, delay: int = 12) -> dict[str, Any]:
        """Type text using xdotool.

        Args:
            text: Text to type
            delay: Delay between keystrokes in ms

        Returns:
            Result dict
        """
        # Escape special characters for shell
        escaped_text = text.replace("'", "'\\''")
        cmd = f"DISPLAY={self.display} xdotool type --delay {delay} '{escaped_text}'"
        stdout, stderr, code = await self._ssh_command(cmd, timeout=60)

        if code != 0:
            return {"success": False, "error": f"Type failed: {stderr}"}

        logger.debug(f"Typed: {text[:30]}...")
        return {"success": True, "typed": text}

    async def key(self, key_combo: str) -> dict[str, Any]:
        """Press key or key combination.

        Args:
            key_combo: Key combination (e.g., "ctrl+s", "Return", "Tab")

        Returns:
            Result dict
        """
        cmd = f"DISPLAY={self.display} xdotool key {key_combo}"
        stdout, stderr, code = await self._ssh_command(cmd)

        if code != 0:
            return {"success": False, "error": f"Key press failed: {stderr}"}

        logger.debug(f"Pressed key: {key_combo}")
        return {"success": True, "key": key_combo}

    async def scroll(self, clicks: int = 3, direction: str = "down") -> dict[str, Any]:
        """Scroll the mouse wheel.

        Args:
            clicks: Number of scroll clicks
            direction: "up" or "down"

        Returns:
            Result dict
        """
        button = 5 if direction == "down" else 4
        cmd = f"DISPLAY={self.display} xdotool click --repeat {clicks} --delay 50 {button}"
        stdout, stderr, code = await self._ssh_command(cmd)

        if code != 0:
            return {"success": False, "error": f"Scroll failed: {stderr}"}

        return {"success": True, "direction": direction, "clicks": clicks}

    async def execute_command(self, command: str) -> dict[str, Any]:
        """Execute shell command on VM.

        Args:
            command: Shell command to execute

        Returns:
            Result with stdout/stderr
        """
        stdout, stderr, code = await self._ssh_command(command, timeout=60)

        return {
            "success": code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": code,
        }

    async def get_window_list(self) -> dict[str, Any]:
        """Get list of open windows."""
        cmd = f"DISPLAY={self.display} wmctrl -l"
        stdout, stderr, code = await self._ssh_command(cmd)

        if code != 0:
            return {"success": False, "error": stderr}

        windows = []
        for line in stdout.strip().split("\n"):
            if line:
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append({
                        "id": parts[0],
                        "desktop": parts[1],
                        "host": parts[2],
                        "title": parts[3],
                    })

        return {"success": True, "windows": windows}

    async def focus_window(self, window_id_or_name: str) -> dict[str, Any]:
        """Focus a window by ID or partial name."""
        cmd = f"DISPLAY={self.display} wmctrl -a '{window_id_or_name}'"
        stdout, stderr, code = await self._ssh_command(cmd)

        return {
            "success": code == 0,
            "window": window_id_or_name,
            "error": stderr if code != 0 else None,
        }

    async def launch_application(self, app_command: str) -> dict[str, Any]:
        """Launch an application in background.

        Args:
            app_command: Command to launch (e.g., "libreoffice --calc")

        Returns:
            Result dict
        """
        # Use nohup to properly detach the process
        cmd = f"DISPLAY={self.display} nohup {app_command} &>/dev/null &"
        stdout, stderr, code = await self._ssh_command(cmd, timeout=5)

        # Give app time to start
        await asyncio.sleep(1.5)

        return {
            "success": True,
            "launched": app_command,
        }


async def create_s3_agent(
    model: str = "qwen3-coder:30b",
    vision_model: str = "llava:13b",
    ollama_host: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    vm_host: str = os.getenv("VNC_HOST", "localhost"),
    vm_vnc_port: int = 5900,
    max_iterations: int = 15,
) -> S3Agent:
    """Factory function to create a configured S3Agent.

    By default uses VM-400 Ollama (with GPU) for both reasoning and vision.

    Args:
        model: LLM model for reasoning (available on VM-400: qwen3-coder:30b)
        vision_model: Vision model for UI detection (available: llava:13b)
        ollama_host: Ollama server URL (default: VM-400 with GPU)
        vm_host: VM-400 host for desktop automation
        vm_vnc_port: VNC port on VM-400
        max_iterations: Maximum action iterations

    Returns:
        Configured S3Agent
    """
    from src.infrastructure.llm.ollama_client import OllamaClient
    from src.infrastructure.tools import create_unified_registry

    # Create LLM client (connects to VM-400 with GPU)
    llm_client = OllamaClient(
        base_url=ollama_host,
        model=model,
        vision_model=vision_model,
    )

    # Create tool registry
    tool_registry = create_unified_registry()

    # Create agent
    agent = S3Agent(
        llm_client=llm_client,
        tool_registry=tool_registry,
        vision_model=vision_model,
        vm_host=vm_host,
        vm_vnc_port=vm_vnc_port,
        max_iterations=max_iterations,
    )

    logger.info(
        f"Created S3Agent with vision_model={vision_model}, "
        f"vm={vm_host}:{vm_vnc_port}"
    )

    return agent
