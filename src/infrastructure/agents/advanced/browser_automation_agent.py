#!/usr/bin/env python3
"""
Browser Automation Agent Avancé pour Tawiza-V2
Automatisation intelligente du navigateur avec OpenManus et capacités avancées
"""

import asyncio
import base64
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from playwright.async_api import Page, async_playwright

# Configuration du logging

@dataclass
class BrowserAction:
    """Action du navigateur"""
    action_type: str  # click, type, scroll, screenshot, etc.
    selector: str | None = None
    value: str | None = None
    coordinates: tuple[int, int] | None = None
    wait_time: float = 0.5
    description: str = ""

@dataclass
class AutomationTask:
    """Tâche d'automatisation"""
    task_id: str
    url: str
    objective: str
    actions: list[BrowserAction]
    max_steps: int = 50
    timeout: float = 300.0
    headless: bool = True
    user_agent: str | None = None
    viewport: dict[str, int] | None = None

@dataclass
class AutomationResult:
    """Résultat de l'automatisation"""
    task_id: str
    success: bool
    url: str
    final_url: str
    actions_performed: int
    data_extracted: dict[str, Any]
    screenshots: list[str]
    error_message: str | None = None
    execution_time: float = 0.0
    timestamp: str = ""

@dataclass
class ElementInfo:
    """Informations sur un élément web"""
    tag_name: str
    text: str
    attributes: dict[str, str]
    position: dict[str, int]
    size: dict[str, int]
    is_visible: bool
    is_interactable: bool

class BrowserAutomationAgent:
    """Agent d'automatisation de navigateur avancé"""

    def __init__(self):
        self.name = "BrowserAutomationAgent"
        self.agent_type = "browser_automation"
        self.capabilities = [
            "web_navigation",
            "form_filling",
            "data_extraction",
            "screenshot_capture",
            "element_interaction",
            "page_analysis"
        ]
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_initialized = False
        self.active_tasks = {}
        self.task_history = []
        self.automation_rules = self._load_automation_rules()

    async def initialize(self):
        """Initialiser l'agent d'automatisation"""
        logger.info("🌐 Initialisation du Browser Automation Agent...")

        try:
            self.playwright = await async_playwright().start()

            # Configuration avancée du navigateur
            browser_config = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-features=TranslateUI",
                    "--disable-ipc-flooding-protection",
                    "--enable-features=NetworkService,NetworkServiceInProcess"
                ]
            }

            # Lancer le navigateur
            self.browser = await self.playwright.chromium.launch(**browser_config)

            # Configuration du contexte
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="fr-FR",
                timezone_id="Europe/Paris",
                permissions=["geolocation", "notifications"],
                java_script_enabled=True
            )

            # Activer la console et les logs
            self.context.on("console", self._handle_console_message)
            self.context.on("page", self._handle_new_page)

            self.is_initialized = True
            logger.info("✅ Browser Automation Agent initialisé avec succès")

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation: {e}")
            raise

    async def cleanup(self):
        """Nettoyer les ressources"""
        logger.info("🧹 Nettoyage du Browser Automation Agent...")

        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

            logger.info("✅ Nettoyage terminé")

        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage: {e}")

    async def execute_task(self, task: AutomationTask) -> AutomationResult:
        """Exécuter une tâche d'automatisation"""
        logger.info(f"🚀 Exécution de la tâche: {task.task_id}")

        start_time = time.time()
        task_id = task.task_id

        try:
            # Créer une nouvelle page pour cette tâche
            page = await self.context.new_page()
            self.active_tasks[task_id] = page

            # Configurer la page
            await self._setup_page(page, task)

            # Naviguer vers l'URL
            await page.goto(task.url, wait_until="networkidle", timeout=30000)

            # Exécuter les actions
            result = await self._execute_actions(page, task)

            # Capturer des données supplémentaires
            additional_data = await self._extract_page_data(page)
            result.data_extracted.update(additional_data)

            # Fermer la page
            await page.close()
            del self.active_tasks[task_id]

            # Calculer le temps d'exécution
            result.execution_time = time.time() - start_time
            result.timestamp = datetime.now().isoformat()

            logger.info(f"✅ Tâche {task_id} complétée en {result.execution_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'exécution de la tâche {task_id}: {e}")

            # Nettoyer en cas d'erreur
            if task_id in self.active_tasks:
                try:
                    await self.active_tasks[task_id].close()
                    del self.active_tasks[task_id]
                except Exception as e:
                    logger.debug(f"Failed to close page for task {task_id}: {e}")

            return AutomationResult(
                task_id=task_id,
                success=False,
                url=task.url,
                final_url=task.url,
                actions_performed=0,
                data_extracted={},
                screenshots=[],
                error_message=str(e),
                execution_time=time.time() - start_time,
                timestamp=datetime.now().isoformat()
            )

    async def _setup_page(self, page: Page, task: AutomationTask):
        """Configurer la page pour l'automatisation"""
        # Définir le viewport si spécifié
        if task.viewport:
            await page.set_viewport_size(task.viewport)

        # Configurer le user agent si spécifié
        if task.user_agent:
            await page.set_user_agent(task.user_agent)

        # Bloquer les ressources inutiles pour améliorer les performances
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico}", lambda route: route.abort())
        await page.route("**/*.css", lambda route: route.continue_())
        await page.route("**/*.js", lambda route: route.continue_())

        # Attendre que la page soit prête
        await page.wait_for_load_state("domcontentloaded")

    async def _execute_actions(self, page: Page, task: AutomationTask) -> AutomationResult:
        """Exécuter les actions de la tâche"""
        actions_performed = 0
        screenshots = []
        extracted_data = {}
        final_url = task.url

        for i, action in enumerate(task.actions):
            if actions_performed >= task.max_steps:
                logger.warning(f"⚠️ Limite d'actions atteinte: {task.max_steps}")
                break

            try:
                logger.info(f"🎯 Action {i+1}/{len(task.actions)}: {action.description}")

                # Exécuter l'action
                success = await self._perform_action(page, action)

                if success:
                    actions_performed += 1

                    # Capturer une capture d'écran si nécessaire
                    if action.action_type in ["click", "type", "scroll"]:
                        screenshot = await self._capture_screenshot(page)
                        if screenshot:
                            screenshots.append(screenshot)

                    # Extraire des données après certaines actions
                    if action.action_type == "click":
                        data = await self._extract_current_data(page)
                        extracted_data.update(data)

                    # Attendre si nécessaire
                    if action.wait_time > 0:
                        await asyncio.sleep(action.wait_time)

                else:
                    logger.warning(f"⚠️ Action échouée: {action.description}")

            except Exception as e:
                logger.error(f"❌ Erreur lors de l'action {action.description}: {e}")
                continue

        # Obtenir l'URL finale
        final_url = page.url

        return AutomationResult(
            task_id=task.task_id,
            success=True,
            url=task.url,
            final_url=final_url,
            actions_performed=actions_performed,
            data_extracted=extracted_data,
            screenshots=screenshots,
            error_message=None,
            execution_time=0.0,
            timestamp=""
        )

    async def _perform_action(self, page: Page, action: BrowserAction) -> bool:
        """Exécuter une action individuelle"""
        try:
            if action.action_type == "click":
                if action.selector:
                    await page.click(action.selector)
                elif action.coordinates:
                    await page.mouse.click(action.coordinates[0], action.coordinates[1])

            elif action.action_type == "type":
                if action.selector and action.value:
                    await page.fill(action.selector, action.value)

            elif action.action_type == "scroll":
                if action.coordinates:
                    await page.mouse.wheel(action.coordinates[0], action.coordinates[1])
                else:
                    await page.evaluate("window.scrollBy(0, 500)")

            elif action.action_type == "wait":
                wait_time = float(action.value) if action.value else action.wait_time
                await asyncio.sleep(wait_time)

            elif action.action_type == "screenshot":
                # La capture d'écran est gérée au niveau supérieur
                pass

            elif action.action_type == "extract":
                # L'extraction de données est gérée au niveau supérieur
                pass

            elif action.action_type == "navigate":
                if action.value:
                    await page.goto(action.value, wait_until="networkidle")

            elif action.action_type == "select":
                if action.selector and action.value:
                    await page.select_option(action.selector, action.value)

            elif action.action_type == "hover":
                if action.selector:
                    await page.hover(action.selector)
                elif action.coordinates:
                    await page.mouse.move(action.coordinates[0], action.coordinates[1])

            else:
                logger.warning(f"⚠️ Type d'action non supporté: {action.action_type}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'exécution de l'action {action.action_type}: {e}")
            return False

    async def _capture_screenshot(self, page: Page) -> str | None:
        """Capturer une capture d'écran de la page"""
        try:
            screenshot_bytes = await page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            return screenshot_b64
        except Exception as e:
            logger.error(f"❌ Erreur lors de la capture d'écran: {e}")
            return None

    async def _extract_page_data(self, page: Page) -> dict[str, Any]:
        """Extraire des données de la page"""
        try:
            # Extraire le texte principal
            main_text = await page.inner_text("body")

            # Extraire les liens
            links = await page.eval_on_selector_all("a", "elements => elements.map(e => ({href: e.href, text: e.textContent}))")

            # Extraire les images
            images = await page.eval_on_selector_all("img", "elements => elements.map(e => ({src: e.src, alt: e.alt}))")

            # Extraire les formulaires
            forms = await page.eval_on_selector_all("form", "elements => elements.map(e => ({action: e.action, method: e.method}))")

            # Extraire les titres
            title = await page.title()

            # Extraire les métadonnées (avec timeout court pour éviter blocage)
            try:
                meta_description = await page.get_attribute('meta[name="description"]', "content", timeout=2000)
            except Exception as e:
                logger.debug(f"Failed to extract meta description: {e}")
                meta_description = None
            try:
                meta_keywords = await page.get_attribute('meta[name="keywords"]', "content", timeout=2000)
            except Exception as e:
                logger.debug(f"Failed to extract meta keywords: {e}")
                meta_keywords = None

            return {
                "title": title,
                "main_text": main_text[:1000],  # Limiter la taille
                "links": links[:20],  # Limiter le nombre
                "images": images[:20],
                "forms": forms[:10],
                "meta_description": meta_description,
                "meta_keywords": meta_keywords,
                "url": page.url
            }

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction des données: {e}")
            return {}

    async def _extract_current_data(self, page: Page) -> dict[str, Any]:
        """Extraire des données supplémentaires après une action"""
        try:
            # Vérifier s'il y a des messages d'erreur
            error_elements = await page.query_selector_all(".error, .alert-error, [role='alert']")
            errors = []
            for element in error_elements:
                error_text = await element.text_content()
                if error_text:
                    errors.append(error_text.strip())

            # Vérifier s'il y a des messages de succès
            success_elements = await page.query_selector_all(".success, .alert-success, .message-success")
            successes = []
            for element in success_elements:
                success_text = await element.text_content()
                if success_text:
                    successes.append(success_text.strip())

            return {
                "errors": errors,
                "successes": successes,
                "current_url": page.url
            }

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction des données actuelles: {e}")
            return {}

    def _handle_console_message(self, msg):
        """Gérer les messages de console"""
        logger.debug(f"📝 Console: {msg.text}")

    def _handle_new_page(self, page):
        """Gérer les nouvelles pages"""
        logger.info(f"📄 Nouvelle page ouverte: {page.url}")

    def _load_automation_rules(self) -> dict[str, Any]:
        """Charger les règles d'automatisation"""
        # Règles par défaut pour l'automatisation intelligente
        return {
            "wait_for_elements": True,
            "retry_failed_actions": 3,
            "screenshot_on_error": True,
            "extract_data_after_actions": True,
            "handle_popups": True,
            "auto_scroll": True,
            "smart_wait": True
        }

    async def create_automation_task(self, url: str, objective: str, **kwargs) -> AutomationTask:
        """Créer une tâche d'automatisation intelligente"""
        task_id = str(uuid.uuid4())

        # Analyser l'objectif et générer des actions
        actions = await self._generate_actions_from_objective(objective, url)

        return AutomationTask(
            task_id=task_id,
            url=url,
            objective=objective,
            actions=actions,
            max_steps=kwargs.get("max_steps", 50),
            timeout=kwargs.get("timeout", 300.0),
            headless=kwargs.get("headless", True),
            user_agent=kwargs.get("user_agent"),
            viewport=kwargs.get("viewport")
        )

    async def _generate_actions_from_objective(self, objective: str, url: str) -> list[BrowserAction]:
        """Générer des actions à partir de l'objectif"""
        actions = []

        # Analyser l'objectif et créer des actions appropriées
        objective_lower = objective.lower()

        # Actions basiques selon l'objectif
        if "remplir" in objective_lower or "saisir" in objective_lower:
            actions.append(BrowserAction(
                action_type="wait",
                wait_time=2.0,
                description="Attendre le chargement du formulaire"
            ))

        if "cliquer" in objective_lower or "clic" in objective_lower:
            actions.append(BrowserAction(
                action_type="wait",
                wait_time=1.0,
                description="Attendre avant de cliquer"
            ))

        if "extraire" in objective_lower or "récupérer" in objective_lower:
            actions.append(BrowserAction(
                action_type="wait",
                wait_time=1.0,
                description="Attendre avant l'extraction"
            ))

        # Toujours finir par une capture d'écran et une extraction
        actions.append(BrowserAction(
            action_type="screenshot",
            description="Capturer l'état final"
        ))

        actions.append(BrowserAction(
            action_type="extract",
            description="Extraire les données finales"
        ))

        return actions

    async def get_element_info(self, page: Page, selector: str) -> ElementInfo | None:
        """Obtenir des informations détaillées sur un élément"""
        try:
            element = await page.query_selector(selector)
            if not element:
                return None

            # Obtenir les propriétés de l'élément
            properties = await element.evaluate("""(element) => {
                const rect = element.getBoundingClientRect();
                const computedStyle = window.getComputedStyle(element);
                return {
                    tagName: element.tagName.toLowerCase(),
                    text: element.textContent,
                    attributes: Array.from(element.attributes).reduce((acc, attr) => {
                        acc[attr.name] = attr.value;
                        return acc;
                    }, {}),
                    position: {
                        top: rect.top,
                        left: rect.left,
                        right: rect.right,
                        bottom: rect.bottom
                    },
                    size: {
                        width: rect.width,
                        height: rect.height
                    },
                    isVisible: computedStyle.display !== 'none' && computedStyle.visibility !== 'hidden',
                    isInteractable: element.offsetParent !== null && !element.disabled
                };
            }""")

            return ElementInfo(
                tag_name=properties["tagName"],
                text=properties["text"],
                attributes=properties["attributes"],
                position=properties["position"],
                size=properties["size"],
                is_visible=properties["isVisible"],
                is_interactable=properties["isInteractable"]
            )

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'obtention des informations de l'élément: {e}")
            return None

    async def wait_for_element(self, page: Page, selector: str, timeout: float = 10.0) -> bool:
        """Attendre qu'un élément soit présent"""
        try:
            await page.wait_for_selector(selector, timeout=timeout * 1000)
            return True
        except Exception as e:
            logger.error(f"❌ Élément non trouvé: {selector} après {timeout}s: {e}")
            return False

    async def smart_wait_for_page_load(self, page: Page, timeout: float = 30.0) -> bool:
        """Attendre intelligemment le chargement de la page"""
        try:
            # Attendre que l'état du réseau soit idle
            await page.wait_for_load_state("networkidle", timeout=timeout * 1000)

            # Attendre que le DOM soit prêt
            await page.wait_for_load_state("domcontentloaded")

            # Vérifier qu'au moins un élément principal est présent
            try:
                await page.wait_for_selector("body", timeout=5000)
            except Exception as e:
                logger.warning(f"⚠️ Corps de la page non trouvé: {e}")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'attente du chargement: {e}")
            return False

    async def execute_from_prompt(self, prompt: str) -> dict[str, Any]:
        """Execute browser task from natural language prompt.

        Parses the prompt to extract URL and objective, then executes the task.
        This is the entry point for AgentOrchestrator integration.

        Args:
            prompt: Natural language description of the browser task
                   e.g., "Go to google.com and search for python tutorials"
                   e.g., "Navigate to https://example.com and extract all links"

        Returns:
            Dict with task result including extracted data and screenshots
        """
        import re

        # Extract URL from prompt
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, prompt)

        # Also check for domain-like patterns without protocol
        domain_pattern = r'\b([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'
        domains = re.findall(domain_pattern, prompt)

        if urls:
            url = urls[0]
        elif domains:
            # Add https:// prefix
            url = f"https://{domains[0]}"
        else:
            # Default to a search if no URL found
            search_query = prompt.replace(" ", "+")
            url = f"https://www.google.com/search?q={search_query}"

        # Clean objective (remove URL from prompt)
        objective = prompt
        for u in urls:
            objective = objective.replace(u, "").strip()

        if not objective:
            objective = f"Navigate and explore {url}"

        logger.info(f"Browser task: URL={url}, Objective={objective[:50]}...")

        try:
            # Initialize if needed
            if not self.is_initialized:
                await self.initialize()

            # Create and execute task
            task = await self.create_automation_task(url, objective)
            result = await self.execute_task(task)

            return {
                "success": result.success,
                "url": result.url,
                "final_url": result.final_url,
                "data": result.data_extracted,
                "screenshots": result.screenshots,
                "actions_performed": result.actions_performed,
                "execution_time": result.execution_time,
                "error": result.error_message,
            }

        except Exception as e:
            logger.error(f"Browser task failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "url": url,
            }


# Fonctions utilitaires
def create_browser_automation_agent() -> BrowserAutomationAgent:
    """Créer et initialiser l'agent d'automatisation"""
    return BrowserAutomationAgent()

async def automate_web_task(url: str, objective: str, **kwargs) -> AutomationResult:
    """Automatiser une tâche web simple"""
    agent = create_browser_automation_agent()

    try:
        await agent.initialize()

        # Créer la tâche
        task = await agent.create_automation_task(url, objective, **kwargs)

        # Exécuter la tâche
        result = await agent.execute_task(task)

        return result

    finally:
        await agent.cleanup()

# Export
__all__ = [
    'BrowserAutomationAgent',
    'AutomationTask',
    'AutomationResult',
    'BrowserAction',
    'ElementInfo',
    'create_browser_automation_agent',
    'automate_web_task'
]
