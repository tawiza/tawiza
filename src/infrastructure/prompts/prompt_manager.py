"""
Dynamic Prompt Manager

Système de gestion dynamique des prompts pour LLMs.

Features:
- Templates de prompts avec variables
- Support multi-formats (Alpaca, ChatML, Browser, etc.)
- Versioning des prompts
- Tracking d'utilisation
- Validation de templates
- Chargement depuis fichiers YAML/JSON
"""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from loguru import logger


class PromptFormat(StrEnum):
    """Formats de prompts supportés."""

    ALPACA = "alpaca"  # Instruction/Input/Output
    CHATML = "chatml"  # Messages (OpenAI-style)
    BROWSER = "browser"  # Browser automation tasks
    SIMPLE = "simple"  # Simple prompt/response
    SYSTEM_USER = "system_user"  # System + User prompt


@dataclass
class PromptTemplate:
    """
    Template de prompt avec variables dynamiques.

    Attributes:
        name: Nom unique du template
        format: Format du template (Alpaca, ChatML, etc.)
        template: Template string avec {variables}
        variables: Liste des variables requises
        description: Description du template
        version: Version du template
        metadata: Métadonnées additionnelles
        usage_count: Nombre d'utilisations
        created_at: Date de création
        updated_at: Date de dernière modification
    """

    name: str
    format: PromptFormat
    template: str
    variables: list[str] = field(default_factory=list)
    description: str = ""
    version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)
    usage_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        """Initialisation après création."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

        # Auto-détection des variables dans le template
        if not self.variables:
            self.variables = self._extract_variables()

    def _extract_variables(self) -> list[str]:
        """
        Extrait les variables du template.

        Returns:
            Liste des noms de variables trouvées
        """
        pattern = r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}"
        matches = re.findall(pattern, self.template)
        return list(set(matches))

    def validate_variables(self, **kwargs) -> tuple[bool, list[str]]:
        """
        Valide que toutes les variables requises sont fournies.

        Args:
            **kwargs: Variables à valider

        Returns:
            tuple: (is_valid, missing_variables)
        """
        provided = set(kwargs.keys())
        required = set(self.variables)
        missing = required - provided

        return len(missing) == 0, list(missing)

    def render(self, **kwargs) -> str:
        """
        Rend le template avec les variables fournies.

        Args:
            **kwargs: Variables pour le template

        Returns:
            str: Template rendu

        Raises:
            ValueError: Si des variables requises manquent
        """
        is_valid, missing = self.validate_variables(**kwargs)
        if not is_valid:
            raise ValueError(f"Variables manquantes pour le template '{self.name}': {missing}")

        # Incrémente le compteur d'utilisation
        self.usage_count += 1
        self.updated_at = datetime.utcnow()

        # Rend le template
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Variable inconnue dans le template: {e}")

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire."""
        data = asdict(self)
        data["format"] = self.format.value
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptTemplate":
        """Crée depuis un dictionnaire."""
        data = data.copy()
        data["format"] = PromptFormat(data["format"])
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class PromptManager:
    """
    Gestionnaire de prompts dynamique.

    Usage:
        manager = PromptManager()

        # Créer un template
        manager.register_template(
            name="browser_task",
            format=PromptFormat.BROWSER,
            template="Navigate to {url} and {action}",
            description="Template pour browser automation"
        )

        # Utiliser le template
        prompt = manager.render("browser_task", url="google.com", action="search for Python")

        # Sauvegarder
        manager.save_templates("prompts.json")
    """

    def __init__(self, templates_dir: Path | None = None):
        """
        Initialize prompt manager.

        Args:
            templates_dir: Répertoire pour stocker les templates
        """
        self.templates: dict[str, PromptTemplate] = {}
        self.templates_dir = templates_dir or Path("./prompts")
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Statistiques
        self.stats = {
            "total_renders": 0,
            "renders_by_template": {},
            "renders_by_format": {},
        }

        logger.info(f"PromptManager initialized (dir={self.templates_dir})")

    def register_template(
        self,
        name: str,
        format: PromptFormat,
        template: str,
        description: str = "",
        version: str = "1.0",
        metadata: dict[str, Any] | None = None,
        variables: list[str] | None = None,
    ) -> PromptTemplate:
        """
        Enregistre un nouveau template de prompt.

        Args:
            name: Nom unique du template
            format: Format du template
            template: Template string
            description: Description
            version: Version
            metadata: Métadonnées
            variables: Variables (auto-détectées si None)

        Returns:
            PromptTemplate: Template créé

        Raises:
            ValueError: Si un template avec ce nom existe déjà
        """
        if name in self.templates:
            logger.warning(f"Template '{name}' existe déjà, remplacement")

        template_obj = PromptTemplate(
            name=name,
            format=format,
            template=template,
            description=description,
            version=version,
            metadata=metadata or {},
            variables=variables or [],
        )

        self.templates[name] = template_obj

        logger.info(
            f"Template enregistré: '{name}' (format={format.value}, "
            f"variables={template_obj.variables})"
        )

        return template_obj

    def get_template(self, name: str) -> PromptTemplate | None:
        """
        Récupère un template par nom.

        Args:
            name: Nom du template

        Returns:
            PromptTemplate ou None si non trouvé
        """
        return self.templates.get(name)

    def render(self, template_name: str, **kwargs) -> str:
        """
        Rend un template avec les variables fournies.

        Args:
            template_name: Nom du template
            **kwargs: Variables pour le template

        Returns:
            str: Prompt rendu

        Raises:
            ValueError: Si template non trouvé ou variables manquantes
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' non trouvé")

        # Rend le template
        rendered = template.render(**kwargs)

        # Met à jour les statistiques
        self.stats["total_renders"] += 1
        self.stats["renders_by_template"][template_name] = (
            self.stats["renders_by_template"].get(template_name, 0) + 1
        )
        self.stats["renders_by_format"][template.format.value] = (
            self.stats["renders_by_format"].get(template.format.value, 0) + 1
        )

        logger.debug(f"Template rendu: '{template_name}' ({len(rendered)} chars)")

        return rendered

    def list_templates(self, format_filter: PromptFormat | None = None) -> list[PromptTemplate]:
        """
        Liste tous les templates.

        Args:
            format_filter: Filtrer par format (optionnel)

        Returns:
            Liste des templates
        """
        templates = list(self.templates.values())

        if format_filter:
            templates = [t for t in templates if t.format == format_filter]

        return templates

    def save_templates(self, filepath: Path | None = None):
        """
        Sauvegarde tous les templates dans un fichier JSON.

        Args:
            filepath: Chemin du fichier (défaut: templates_dir/templates.json)
        """
        if filepath is None:
            filepath = self.templates_dir / "templates.json"

        data = {
            "templates": [t.to_dict() for t in self.templates.values()],
            "stats": self.stats,
            "saved_at": datetime.utcnow().isoformat(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Templates sauvegardés: {filepath} ({len(self.templates)} templates)")

    def load_templates(self, filepath: Path | None = None):
        """
        Charge les templates depuis un fichier JSON.

        Args:
            filepath: Chemin du fichier (défaut: templates_dir/templates.json)
        """
        if filepath is None:
            filepath = self.templates_dir / "templates.json"

        if not filepath.exists():
            logger.warning(f"Fichier de templates non trouvé: {filepath}")
            return

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        # Charge les templates
        for template_data in data.get("templates", []):
            template = PromptTemplate.from_dict(template_data)
            self.templates[template.name] = template

        # Charge les stats
        if "stats" in data:
            self.stats = data["stats"]

        logger.info(f"Templates chargés: {filepath} ({len(self.templates)} templates)")

    def get_stats(self) -> dict[str, Any]:
        """
        Récupère les statistiques d'utilisation.

        Returns:
            dict: Statistiques
        """
        return {
            **self.stats,
            "total_templates": len(self.templates),
            "templates_by_format": {
                format.value: len([t for t in self.templates.values() if t.format == format])
                for format in PromptFormat
            },
        }

    def create_default_templates(self):
        """Crée des templates par défaut pour démarrer."""
        initial_count = len(self.templates)

        # Template browser automation
        self.register_template(
            name="browser_navigation",
            format=PromptFormat.BROWSER,
            template="Navigate to {url} and {action}",
            description="Navigation et action sur une page web",
            metadata={"category": "browser", "use_case": "automation"},
        )

        # Template browser avec contexte
        self.register_template(
            name="browser_task_detailed",
            format=PromptFormat.BROWSER,
            template="""Go to {url}
Task: {task}
{context}
Please complete this task step by step.""",
            description="Tâche browser détaillée avec contexte",
            metadata={"category": "browser", "use_case": "automation"},
        )

        # Template classification
        self.register_template(
            name="text_classification",
            format=PromptFormat.ALPACA,
            template="""### Instruction:
Classify the following text into one of these categories: {categories}

### Input:
{text}

### Response:
""",
            description="Classification de texte",
            metadata={"category": "classification", "use_case": "ml"},
        )

        # Template chat simple
        self.register_template(
            name="chat_simple",
            format=PromptFormat.SYSTEM_USER,
            template="""System: {system_prompt}

User: {user_message}""",
            description="Chat simple avec system prompt",
            metadata={"category": "chat", "use_case": "conversation"},
        )

        # Template NER
        self.register_template(
            name="named_entity_recognition",
            format=PromptFormat.ALPACA,
            template="""### Instruction:
Extract named entities from the following text. Return entities in JSON format with their types.

### Input:
{text}

### Response:
""",
            description="Extraction d'entités nommées",
            metadata={"category": "ner", "use_case": "ml"},
        )

        # Template summarization
        self.register_template(
            name="text_summarization",
            format=PromptFormat.SYSTEM_USER,
            template="""System: You are a helpful assistant that summarizes text concisely.

User: Please summarize the following text in {max_words} words or less:

{text}""",
            description="Résumé de texte",
            metadata={"category": "summarization", "use_case": "ml"},
        )

        # Template code generation
        self.register_template(
            name="code_generation",
            format=PromptFormat.SYSTEM_USER,
            template="""System: You are an expert programmer. Write clean, well-documented code.

User: Write a {language} function to {task}.
Requirements: {requirements}""",
            description="Génération de code",
            metadata={"category": "code", "use_case": "development"},
        )

        # Code review
        self.register_template(
            name="code_review",
            format=PromptFormat.SYSTEM_USER,
            template="""System: You are an expert code reviewer. Analyze code for bugs, security issues, performance problems, and best practices violations.

User: Review the following {language} code:

```{language}
{code}
```

Provide a detailed review with:
1. Bugs and errors
2. Security vulnerabilities
3. Performance issues
4. Best practices violations
5. Suggestions for improvement""",
            description="Review de code avec analyse complète",
            metadata={"category": "code", "use_case": "quality"},
        )

        # Data validation
        self.register_template(
            name="data_validation",
            format=PromptFormat.ALPACA,
            template="""### Instruction:
Validate the following data against these rules: {rules}
Return validation results in JSON format with fields: is_valid, errors, warnings.

### Input:
{data}

### Response:
""",
            description="Validation de données avec règles",
            metadata={"category": "validation", "use_case": "ml"},
        )

        # Error analysis
        self.register_template(
            name="error_analysis",
            format=PromptFormat.SYSTEM_USER,
            template="""System: You are an expert at analyzing errors and exceptions. Provide clear explanations and solutions.

User: Analyze this error and provide:
1. Root cause
2. Why it happened
3. How to fix it
4. How to prevent it in the future

Error: {error_type}
Message: {error_message}
Stack trace: {stack_trace}""",
            description="Analyse d'erreurs et solutions",
            metadata={"category": "debugging", "use_case": "development"},
        )

        # Fine-tuning data preparation
        self.register_template(
            name="finetuning_data_prep",
            format=PromptFormat.ALPACA,
            template="""### Instruction:
Convert the following raw data into a fine-tuning dataset for {task_type}.
Format: {format_type}
Requirements: {requirements}

### Input:
{raw_data}

### Response:
""",
            description="Préparation de données pour fine-tuning",
            metadata={"category": "ml", "use_case": "fine-tuning"},
        )

        # Annotation assistance
        self.register_template(
            name="annotation_assistant",
            format=PromptFormat.ALPACA,
            template="""### Instruction:
Suggest annotations for the following data based on these labels: {labels}
Task type: {task_type}
Return suggestions in JSON format with confidence scores.

### Input:
{data}

### Response:
""",
            description="Assistant d'annotation avec suggestions",
            metadata={"category": "annotation", "use_case": "ml"},
        )

        # SQL generation
        self.register_template(
            name="sql_generation",
            format=PromptFormat.SYSTEM_USER,
            template="""System: You are an expert SQL developer. Generate efficient, safe SQL queries.

User: Generate a SQL query for: {description}
Database type: {db_type}
Tables: {tables}

Requirements:
- Use proper joins
- Include WHERE clauses for filtering
- Add indexes suggestions if needed
- Prevent SQL injection""",
            description="Génération de requêtes SQL",
            metadata={"category": "database", "use_case": "development"},
        )

        # API documentation
        self.register_template(
            name="api_documentation",
            format=PromptFormat.SYSTEM_USER,
            template="""System: You are a technical writer specializing in API documentation.

User: Document the following API endpoint:
Method: {method}
Path: {path}
Description: {description}

Include:
1. Endpoint description
2. Request parameters
3. Request body schema
4. Response schema
5. Example request
6. Example response
7. Error codes""",
            description="Documentation d'API endpoints",
            metadata={"category": "documentation", "use_case": "development"},
        )

        # Sentiment analysis
        self.register_template(
            name="sentiment_analysis",
            format=PromptFormat.ALPACA,
            template="""### Instruction:
Analyze the sentiment of the following text.
Return: sentiment (positive/negative/neutral), confidence score, and key phrases.

### Input:
{text}

### Response:
""",
            description="Analyse de sentiment avec confiance",
            metadata={"category": "nlp", "use_case": "ml"},
        )

        # Question answering
        self.register_template(
            name="question_answering",
            format=PromptFormat.ALPACA,
            template="""### Instruction:
Answer the following question based on the given context.
If the answer is not in the context, say 'I don't know'.

### Context:
{context}

### Question:
{question}

### Answer:
""",
            description="Réponse à des questions basée sur contexte",
            metadata={"category": "qa", "use_case": "ml"},
        )

        # Translation
        self.register_template(
            name="translation",
            format=PromptFormat.SYSTEM_USER,
            template="""System: You are an expert translator. Translate accurately while preserving meaning and tone.

User: Translate the following text from {source_lang} to {target_lang}:

{text}""",
            description="Traduction de texte entre langues",
            metadata={"category": "translation", "use_case": "nlp"},
        )

        logger.info(f"Templates par défaut créés ({len(self.templates) - initial_count} templates)")


# Global prompt manager instance
_prompt_manager: PromptManager | None = None


def get_prompt_manager(templates_dir: Path | None = None) -> PromptManager:
    """
    Get or create global prompt manager instance.

    Args:
        templates_dir: Directory for templates (optional)

    Returns:
        PromptManager: Global instance
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager(templates_dir)
        # Charge les templates existants ou crée les defaults
        _prompt_manager.load_templates()
        if not _prompt_manager.templates:
            _prompt_manager.create_default_templates()
            _prompt_manager.save_templates()
    return _prompt_manager
