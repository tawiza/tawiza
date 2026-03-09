#!/usr/bin/env python3
"""
Code Generator Agent Intelligent pour Tawiza-V2
Génération de code avancée avec IA et meilleures pratiques
"""

import ast
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import black
from jinja2 import Template
from loguru import logger

# Configuration du logging

@dataclass
class CodeGenerationRequest:
    """Requête de génération de code"""
    request_id: str
    language: str
    framework: str | None = None
    description: str = ""
    requirements: list[str] = None
    existing_code: str | None = None
    style_guide: str | None = None
    test_cases: list[str] = None
    performance_requirements: dict[str, Any] | None = None
    security_requirements: list[str] = None

@dataclass
class GeneratedCode:
    """Code généré"""
    request_id: str
    language: str
    code: str
    imports: list[str]
    functions: list[dict[str, Any]]
    classes: list[dict[str, Any]]
    tests: list[str]
    documentation: str
    dependencies: list[str]
    file_structure: dict[str, str]
    quality_score: float
    performance_analysis: dict[str, Any]
    security_analysis: dict[str, Any]
    timestamp: str

@dataclass
class CodeAnalysis:
    """Analyse de code"""
    complexity_score: float
    maintainability_score: float
    security_score: float
    performance_score: float
    test_coverage: float
    code_quality: float
    issues: list[dict[str, Any]]
    recommendations: list[str]

class CodeGeneratorAgent:
    """Agent de génération de code intelligent"""

    def __init__(self):
        self.name = "CodeGeneratorAgent"
        self.agent_type = "code_generator"
        self.capabilities = [
            "code_generation",
            "code_analysis",
            "code_refactoring",
            "test_generation",
            "documentation_generation"
        ]
        self.is_initialized = False
        self.templates = {}
        self.code_patterns = {}
        self.best_practices = {}
        self.security_rules = {}
        self.performance_tips = {}
        self.generation_history = []

    async def initialize(self):
        """Initialiser l'agent de génération de code"""
        logger.info("💻 Initialisation du Code Generator Agent...")

        try:
            # Charger les templates
            await self._load_templates()

            # Charger les patterns de code
            await self._load_code_patterns()

            # Charger les meilleures pratiques
            await self._load_best_practices()

            # Charger les règles de sécurité
            await self._load_security_rules()

            # Charger les conseils de performance
            await self._load_performance_tips()

            self.is_initialized = True
            logger.info("✅ Code Generator Agent initialisé avec succès")

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation: {e}")
            raise

    async def _load_templates(self):
        """Charger les templates de code"""
        logger.info("📋 Chargement des templates...")

        # Templates Python
        self.templates["python"] = {
            "class": Template("""
class {{ class_name }}:
    \"\"\"{{ description }}\"\"\"

    def __init__(self{% for param in init_params %}, {{ param }}{% endfor %}):
        {% for param in init_params %}
        self.{{ param }} = {{ param }}
        {% endfor %}

    {% for method in methods %}
    def {{ method.name }}(self{% for param in method.params %}, {{ param }}{% endfor %}):
        \"\"\"{{ method.description }}\"\"\"
        {{ method.body }}

    {% endfor %}
"""),
            "function": Template("""
def {{ function_name }}({% for param in params %}{{ param }}{% if not loop.last %}, {% endif %}{% endfor %}):
    \"\"\"{{ description }}\"\"\"
    {{ body }}
"""),
            "test": Template("""
def test_{{ function_name }}():
    \"\"\"Test pour {{ function_name }}\"\"\"
    # Arrange
    {{ arrange_code }}

    # Act
    {{ act_code }}

    # Assert
    {{ assert_code }}
""")
        }

        # Templates JavaScript
        self.templates["javascript"] = {
            "class": Template("""
class {{ class_name }} {
    constructor({% for param in init_params %}{{ param }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {% for param in init_params %}
        this.{{ param }} = {{ param }};
        {% endfor %}
    }

    {% for method in methods %}
    {{ method.name }}({% for param in method.params %}{{ param }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ method.body }}
    }

    {% endfor %}
}
"""),
            "function": Template("""
function {{ function_name }}({% for param in params %}{{ param }}{% if not loop.last %}, {% endif %}{% endfor %}) {
    {{ body }}
}
""")
        }

        logger.info("✅ Templates chargés")

    async def _load_code_patterns(self):
        """Charger les patterns de code"""
        logger.info("🔧 Chargement des patterns de code...")

        self.code_patterns = {
            "python": {
                "singleton": """
class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
""",
                "factory": """
class Factory:
    @staticmethod
    def create(type):
        if type == "type1":
            return Type1()
        elif type == "type2":
            return Type2()
        raise ValueError(f"Unknown type: {type}")
""",
                "observer": """
class Observer:
    def update(self, subject):
        pass

class Subject:
    def __init__(self):
        self._observers = []

    def attach(self, observer):
        self._observers.append(observer)

    def notify(self):
        for observer in self._observers:
            observer.update(self)
"""
            },
            "javascript": {
                "singleton": """
class Singleton {
    constructor() {
        if (Singleton.instance) {
            return Singleton.instance;
        }
        Singleton.instance = this;
    }
}
""",
                "factory": """
class Factory {
    static create(type) {
        switch (type) {
            case 'type1':
                return new Type1();
            case 'type2':
                return new Type2();
            default:
                throw new Error(`Unknown type: ${type}`);
        }
    }
}
"""
            }
        }

        logger.info("✅ Patterns de code chargés")

    async def _load_best_practices(self):
        """Charger les meilleures pratiques"""
        logger.info("📚 Chargement des meilleures pratiques...")

        self.best_practices = {
            "python": [
                "Utilisez des noms de variables et de fonctions descriptifs",
                "Suivez la PEP 8 pour le style de code",
                "Ajoutez des docstrings à toutes les fonctions et classes",
                "Utilisez des annotations de type",
                "Gérez les exceptions de manière appropriée",
                "Écrivez des tests unitaires",
                "Utilisez des context managers pour les ressources",
                "Préférez la composition à l'héritage",
                "Gardez les fonctions petites et focalisées",
                "Utilisez des constantes pour les valeurs magiques"
            ],
            "javascript": [
                "Utilisez const et let au lieu de var",
                "Utilisez des fonctions fléchées pour la lisibilité",
                "Évitez les mutations d'état",
                "Utilisez des promesses ou async/await",
                "Gérez les erreurs proprement",
                "Utilisez des modules pour organiser le code",
                "Écrivez des tests unitaires",
                "Utilisez un linter comme ESLint",
                "Documentez votre code",
                "Utilisez des patterns de conception appropriés"
            ]
        }

        logger.info("✅ Meilleures pratiques chargées")

    async def _load_security_rules(self):
        """Charger les règles de sécurité"""
        logger.info("🔒 Chargement des règles de sécurité...")

        self.security_rules = {
            "python": [
                "N'exécutez jamais du code utilisateur non vérifié",
                "Utilisez des requêtes paramétrées pour les bases de données",
                "Validez et nettoyez toutes les entrées utilisateur",
                "Utilisez des secrets pour les informations sensibles",
                "Implémentez une authentification appropriée",
                "Utilisez HTTPS pour les communications",
                "Gérez les erreurs sans exposer d'informations sensibles",
                "Utilisez des bibliothèques de cryptographie éprouvées",
                "Gardez les dépendances à jour",
                "Effectuez des audits de sécurité réguliers"
            ],
            "javascript": [
                "Évitez l'injection de HTML non échappé",
                "Utilisez Content Security Policy",
                "Validez toutes les entrées côté client et serveur",
                "Utilisez des tokens CSRF",
                "Implémentez une authentification appropriée",
                "Utilisez HTTPS",
                "Évitez les évaluations de code dynamique",
                "Protégez contre les attaques XSS",
                "Gardez les dépendances à jour",
                "Utilisez des bibliothèques de cryptographie sécurisées"
            ]
        }

        logger.info("✅ Règles de sécurité chargées")

    async def _load_performance_tips(self):
        """Charger les conseils de performance"""
        logger.info("⚡ Chargement des conseils de performance...")

        self.performance_tips = {
            "python": [
                "Utilisez des générateurs pour les grandes données",
                "Préférez les compréhensions de liste aux boucles",
                "Utilisez des ensembles pour les recherches rapides",
                "Évitez les opérations coûteuses dans les boucles",
                "Utilisez le multiprocessing pour les tâches CPU-bound",
                "Utilisez l'asyncio pour les tâches I/O-bound",
                "Profilez votre code pour identifier les goulots d'étranglement",
                "Utilisez des bibliothèques optimisées comme NumPy",
                "Mettez en cache les résultats coûteux",
                "Utilisez des structures de données appropriées"
            ],
            "javascript": [
                "Minimisez les reflows et repaints du DOM",
                "Utilisez la délégation d'événements",
                "Mettez en cache les sélecteurs DOM",
                "Utilisez des Web Workers pour les tâches lourdes",
                "Optimisez les boucles et évitez les boucles imbriquées",
                "Utilisez des techniques de lazy loading",
                "Minifiez et compressez votre code",
                "Utilisez des CDN pour les bibliothèques",
                "Implémentez un cache approprié",
                "Utilisez des techniques de debouncing et throttling"
            ]
        }

        logger.info("✅ Conseils de performance chargés")

    async def generate_code(self, request: CodeGenerationRequest) -> GeneratedCode:
        """Générer du code selon la requête"""
        logger.info(f"🚀 Génération de code {request.language}: {request.description}")

        datetime.now()

        try:
            # Analyser la requête
            analysis = await self._analyze_request(request)

            # Générer le code principal
            main_code = await self._generate_main_code(request, analysis)

            # Générer les tests
            tests = await self._generate_tests(request, analysis)

            # Générer la documentation
            documentation = await self._generate_documentation(request, analysis)

            # Analyser la qualité du code
            quality_analysis = await self._analyze_code_quality(main_code, request.language)

            # Analyser les performances
            performance_analysis = await self._analyze_performance(main_code, request.language)

            # Analyser la sécurité
            security_analysis = await self._analyze_security(main_code, request.language)

            # Créer la structure de fichiers
            file_structure = await self._create_file_structure(
                request, main_code, tests, documentation, analysis
            )

            # Calculer le score de qualité global
            quality_score = self._calculate_quality_score(quality_analysis, performance_analysis, security_analysis)

            generated_code = GeneratedCode(
                request_id=request.request_id,
                language=request.language,
                code=main_code,
                imports=analysis.get("imports", []),
                functions=analysis.get("functions", []),
                classes=analysis.get("classes", []),
                tests=tests,
                documentation=documentation,
                dependencies=analysis.get("dependencies", []),
                file_structure=file_structure,
                quality_score=quality_score,
                performance_analysis=performance_analysis,
                security_analysis=security_analysis,
                timestamp=datetime.now().isoformat()
            )

            # Ajouter à l'historique
            self.generation_history.append(generated_code)

            logger.info(f"✅ Code généré avec succès (Score: {quality_score:.1f}/100)")
            return generated_code

        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération de code: {e}")
            raise

    async def _analyze_request(self, request: CodeGenerationRequest) -> dict[str, Any]:
        """Analyser la requête de génération"""
        logger.info("🔍 Analyse de la requête...")

        analysis = {
            "complexity": "medium",
            "patterns_needed": [],
            "imports": [],
            "functions": [],
            "classes": [],
            "dependencies": [],
            "estimated_lines": 50
        }

        # Analyser la description
        description_lower = request.description.lower()

        # Détecter les patterns nécessaires
        if "singleton" in description_lower:
            analysis["patterns_needed"].append("singleton")
        if "factory" in description_lower:
            analysis["patterns_needed"].append("factory")
        if "observer" in description_lower:
            analysis["patterns_needed"].append("observer")

        # Détecter les imports nécessaires
        if request.language == "python":
            if "async" in description_lower or "await" in description_lower:
                analysis["imports"].append("asyncio")
            if "json" in description_lower:
                analysis["imports"].append("json")
            if "datetime" in description_lower:
                analysis["imports"].append("datetime")
            if "http" in description_lower or "request" in description_lower:
                analysis["imports"].extend(["httpx", "typing"])

        # Analyser les exigences
        if request.requirements:
            for req in request.requirements:
                req_lower = req.lower()
                if "performance" in req_lower:
                    analysis["complexity"] = "high"
                if "security" in req_lower:
                    analysis["dependencies"].append("cryptography")

        # Estimer la complexité
        if len(request.requirements or []) > 5:
            analysis["complexity"] = "high"
            analysis["estimated_lines"] = 200
        elif len(request.requirements or []) > 2:
            analysis["complexity"] = "medium"
            analysis["estimated_lines"] = 100

        logger.info(f"📊 Analyse complétée: complexité={analysis['complexity']}")
        return analysis

    async def _generate_main_code(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Générer le code principal"""
        logger.info("💻 Génération du code principal...")

        language = request.language

        # Commencer avec les imports
        code_lines = []

        # Ajouter les imports
        for imp in analysis.get("imports", []):
            if language == "python":
                code_lines.append(f"import {imp}")
            elif language == "javascript":
                code_lines.append(f"const {imp} = require('{imp}');")

        code_lines.append("")

        # Ajouter les patterns nécessaires
        for pattern in analysis.get("patterns_needed", []):
            if pattern in self.code_patterns.get(language, {}):
                code_lines.append(self.code_patterns[language][pattern])
                code_lines.append("")

        # Générer le code basé sur la description
        if language == "python":
            main_code = await self._generate_python_code(request, analysis)
        elif language == "javascript":
            main_code = await self._generate_javascript_code(request, analysis)
        else:
            main_code = f"# Code {language} non supporté encore"

        code_lines.append(main_code)

        # Joindre tout le code
        full_code = "\n".join(code_lines)

        # Formatter le code
        formatted_code = await self._format_code(full_code, language)

        logger.info("✅ Code principal généré")
        return formatted_code

    async def _generate_python_code(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Générer du code Python"""
        description = request.description

        # Analyser la description pour créer des fonctions/classes appropriées
        if "class" in description.lower():
            return self._create_python_class(request, analysis)
        elif "function" in description.lower():
            return self._create_python_function(request, analysis)
        else:
            return self._create_python_module(request, analysis)

    def _create_python_class(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Créer une classe Python"""
        class_name = self._extract_class_name(request.description) or "GeneratedClass"

        # Créer les méthodes basées sur les exigences
        methods = []

        for _i, req in enumerate(request.requirements or []):
            method_name = self._generate_method_name(req)
            methods.append({
                "name": method_name,
                "description": req,
                "params": ["self", "*args", "**kwargs"],
                "body": f"        \"\"\"{req}\"\"\"\n        pass  # TODO: Implémenter la méthode"
            })

        # Ajouter des méthodes standards
        methods.extend([
            {
                "name": "__init__",
                "description": "Initialise l'instance",
                "params": ["self"],
                "body": "        \"\"\"Initialise l'instance\"\"\"\n        pass"
            },
            {
                "name": "__str__",
                "description": "Représentation string de l'objet",
                "params": ["self"],
                "body": f"        \"\"\"Représentation string\"\"\"\n        return f'{class_name}()'"
            }
        ])

        # Générer avec le template
        template = self.templates["python"]["class"]
        return template.render(
            class_name=class_name,
            description=request.description,
            init_params=[],
            methods=methods
        )

    def _create_python_function(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Créer une fonction Python"""
        function_name = self._extract_function_name(request.description) or "generated_function"

        # Créer la fonction avec les exigences
        params = []
        for i, _req in enumerate(request.requirements or []):
            param_name = f"param_{i+1}"
            params.append(param_name)

        # Générer le corps de la fonction
        body = f"    \"\"\"{request.description}\"\"\"\n"
        body += "    try:\n"
        body += "        # TODO: Implémenter la fonction\n"
        body += "        result = None\n"
        body += "        return result\n"
        body += "    except Exception as e:\n"
        body += "        logger.error(f'Erreur dans {function_name}: {e}')\n"
        body += "        raise"

        # Générer avec le template
        template = self.templates["python"]["function"]
        return template.render(
            function_name=function_name,
            description=request.description,
            params=params,
            body=body
        )

    def _create_python_module(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Créer un module Python complet"""
        code_parts = []

        # Ajouter la description
        code_parts.append(f'"""{request.description}"""')
        code_parts.append("")

        # Ajouter les constantes
        code_parts.append("# Constants")
        code_parts.append("VERSION = '1.0.0'")
        code_parts.append("DEFAULT_TIMEOUT = 30")
        code_parts.append("")

        # Ajouter les fonctions utilitaires
        code_parts.append("# Utility functions")
        code_parts.append(self._create_python_function(request, analysis))
        code_parts.append("")

        # Ajouter une classe principale
        code_parts.append("# Main class")
        code_parts.append(self._create_python_class(request, analysis))

        return "\n".join(code_parts)

    async def _generate_javascript_code(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Générer du code JavaScript"""
        # Similar à Python mais adapté pour JavaScript
        description = request.description

        if "class" in description.lower():
            return self._create_javascript_class(request, analysis)
        elif "function" in description.lower():
            return self._create_javascript_function(request, analysis)
        else:
            return self._create_javascript_module(request, analysis)

    def _create_javascript_class(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Créer une classe JavaScript"""
        class_name = self._extract_class_name(request.description) or "GeneratedClass"

        methods = []
        for _i, req in enumerate(request.requirements or []):
            method_name = self._generate_method_name(req)
            methods.append({
                "name": method_name,
                "description": req,
                "params": [],
                "body": f"// {req}\n// TODO: Implémenter la méthode"
            })

        # Ajouter le constructeur
        methods.insert(0, {
            "name": "constructor",
            "description": "Constructeur de la classe",
            "params": [],
            "body": "// Initialisation\nthis.createdAt = new Date();"
        })

        template = self.templates["javascript"]["class"]
        return template.render(
            class_name=class_name,
            init_params=[],
            methods=methods
        )

    def _create_javascript_function(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Créer une fonction JavaScript"""
        function_name = self._extract_function_name(request.description) or "generatedFunction"

        params = []
        for i, _req in enumerate(request.requirements or []):
            param_name = f"param{i+1}"
            params.append(param_name)

        body = f"// {request.description}\n"
        body += "try {\n"
        body += "    // TODO: Implémenter la fonction\n"
        body += "    const result = null;\n"
        body += "    return result;\n"
        body += "} catch (error) {\n"
        body += f"    console.error('Erreur dans {function_name}:', error);\n"
        body += "    throw error;\n"
        body += "}"

        template = self.templates["javascript"]["function"]
        return template.render(
            function_name=function_name,
            params=params,
            body=body
        )

    def _create_javascript_module(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Créer un module JavaScript complet"""
        code_parts = []

        # Commentaire d'en-tête
        code_parts.append(f"// {request.description}")
        code_parts.append("")

        # Constantes
        code_parts.append("// Constants")
        code_parts.append("const VERSION = '1.0.0';")
        code_parts.append("const DEFAULT_TIMEOUT = 30000;")
        code_parts.append("")

        # Fonctions
        code_parts.append("// Functions")
        code_parts.append(self._create_javascript_function(request, analysis))
        code_parts.append("")

        # Classe
        code_parts.append("// Class")
        code_parts.append(self._create_javascript_class(request, analysis))
        code_parts.append("")

        # Export
        code_parts.append("// Export")
        code_parts.append("module.exports = {")
        code_parts.append("    VERSION,")
        code_parts.append("    // Add exports here")
        code_parts.append("};")

        return "\n".join(code_parts)

    async def _generate_tests(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> list[str]:
        """Générer des tests"""
        logger.info("🧪 Génération des tests...")

        tests = []

        if request.language == "python":
            # Test basique
            test_code = """
import pytest
from generated_module import *

class TestGeneratedCode:
    def test_initialization(self):
        \"\"\"Test de l'initialisation\"\"\"
        # TODO: Implémenter le test
        assert True

    def test_functionality(self):
        \"\"\"Test de la fonctionnalité principale\"\"\"
        # TODO: Implémenter le test
        assert True

    def test_error_handling(self):
        \"\"\"Test de la gestion d'erreurs\"\"\"
        # TODO: Implémenter le test
        assert True
"""
            tests.append(test_code)

        # Ajouter des tests basés sur les exigences
        for i, req in enumerate(request.test_cases or []):
            test_template = self.templates["python"]["test"]
            test_code = test_template.render(
                function_name=f"requirement_{i+1}",
                arrange_code="# Configuration du test",
                act_code=f"# Exécuter: {req}",
                assert_code="# Vérifier le résultat"
            )
            tests.append(test_code)

        logger.info(f"✅ {len(tests)} tests générés")
        return tests

    async def _generate_documentation(self, request: CodeGenerationRequest, analysis: dict[str, Any]) -> str:
        """Générer la documentation"""
        logger.info("📚 Génération de la documentation...")

        doc_parts = []

        # Documentation principale
        doc_parts.append(f"# {request.description}")
        doc_parts.append("")
        doc_parts.append("## Description")
        doc_parts.append(request.description)
        doc_parts.append("")

        # Exigences
        if request.requirements:
            doc_parts.append("## Exigences")
            for req in request.requirements:
                doc_parts.append(f"- {req}")
            doc_parts.append("")

        # Installation
        doc_parts.append("## Installation")
        doc_parts.append("```bash")
        doc_parts.append(f"pip install {' '.join(analysis.get('dependencies', []))}")
        doc_parts.append("```")
        doc_parts.append("")

        # Utilisation
        doc_parts.append("## Utilisation")
        doc_parts.append("```python")
        doc_parts.append("# TODO: Exemple d'utilisation")
        doc_parts.append("```")
        doc_parts.append("")

        # API
        doc_parts.append("## API")
        doc_parts.append("### Classes")
        doc_parts.append("### Fonctions")
        doc_parts.append("")

        # Notes de sécurité
        if request.security_requirements:
            doc_parts.append("## Sécurité")
            for req in request.security_requirements:
                doc_parts.append(f"- {req}")
            doc_parts.append("")

        documentation = "\n".join(doc_parts)

        logger.info("✅ Documentation générée")
        return documentation

    async def _analyze_code_quality(self, code: str, language: str) -> dict[str, Any]:
        """Analyser la qualité du code"""
        logger.info("🔍 Analyse de la qualité du code...")

        analysis = {
            "complexity_score": 0.0,
            "maintainability_score": 0.0,
            "issues": [],
            "recommendations": []
        }

        try:
            if language == "python":
                # Analyser avec ast
                try:
                    tree = ast.parse(code)

                    # Compter les fonctions et classes
                    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

                    analysis["functions_count"] = len(functions)
                    analysis["classes_count"] = len(classes)

                    # Calculer une complexité approximative
                    analysis["complexity_score"] = min(100, len(functions) * 10 + len(classes) * 20)

                    # Vérifier la présence de docstrings
                    missing_docs = []
                    for func in functions:
                        if not ast.get_docstring(func):
                            missing_docs.append(func.name)

                    if missing_docs:
                        analysis["issues"].append({
                            "type": "missing_documentation",
                            "functions": missing_docs
                        })

                except SyntaxError as e:
                    analysis["issues"].append({
                        "type": "syntax_error",
                        "message": str(e)
                    })

            # Analyser avec des outils externes si disponibles
            try:
                # Formater avec black
                formatted_code = black.format_str(code, mode=black.FileMode())
                if formatted_code != code:
                    analysis["recommendations"].append("Formater le code avec black")

            except Exception as e:
                logger.warning(f"⚠️ Impossible de formater avec black: {e}")

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse de qualité: {e}")

        logger.info("✅ Analyse de qualité complétée")
        return analysis

    async def _analyze_performance(self, code: str, language: str) -> dict[str, Any]:
        """Analyser les performances du code"""
        logger.info("⚡ Analyse des performances...")

        analysis = {
            "performance_score": 0.0,
            "bottlenecks": [],
            "recommendations": []
        }

        try:
            if language == "python":
                # Rechercher des patterns de performance
                if "for " in code and "range" in code:
                    analysis["recommendations"].append("Considérez l'utilisation de compréhensions de liste")

                if "import" in code and "requests" in code:
                    analysis["recommendations"].append("Utilisez httpx pour les requêtes asynchrones")

                if "open(" in code and "close()" not in code:
                    analysis["recommendations"].append("Utilisez des context managers pour les fichiers")

                # Score de performance basique
                analysis["performance_score"] = 75.0  # Score par défaut

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse de performance: {e}")

        logger.info("✅ Analyse de performance complétée")
        return analysis

    async def _analyze_security(self, code: str, language: str) -> dict[str, Any]:
        """Analyser la sécurité du code"""
        logger.info("🔒 Analyse de la sécurité...")

        analysis = {
            "security_score": 0.0,
            "vulnerabilities": [],
            "recommendations": []
        }

        try:
            # Rechercher des vulnérabilités communes
            if language == "python":
                if "eval(" in code or "exec(" in code:
                    analysis["vulnerabilities"].append({
                        "type": "code_injection",
                        "severity": "high",
                        "message": "Utilisation d'eval() ou exec() détectée"
                    })

                if "subprocess.call" in code and "shell=True" in code:
                    analysis["vulnerabilities"].append({
                        "type": "command_injection",
                        "severity": "high",
                        "message": "Injection de commande possible"
                    })

                if "sqlite3" in code and "f\"" in code:
                    analysis["vulnerabilities"].append({
                        "type": "sql_injection",
                        "severity": "medium",
                        "message": "Risque d'injection SQL avec f-strings"
                    })

            # Score de sécurité
            analysis["security_score"] = max(0, 100 - len(analysis["vulnerabilities"]) * 20)

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse de sécurité: {e}")

        logger.info("✅ Analyse de sécurité complétée")
        return analysis

    async def _format_code(self, code: str, language: str) -> str:
        """Formater le code"""
        try:
            if language == "python":
                # Formatter avec black
                try:
                    formatted = black.format_str(code, mode=black.FileMode())
                    return formatted
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de formater avec black: {e}")

            return code

        except Exception as e:
            logger.error(f"❌ Erreur lors du formatage: {e}")
            return code

    def _calculate_quality_score(self, quality_analysis: dict[str, Any],
                                performance_analysis: dict[str, Any],
                                security_analysis: dict[str, Any]) -> float:
        """Calculer le score de qualité global"""
        try:
            quality_score = quality_analysis.get("complexity_score", 0) * 0.3
            performance_score = performance_analysis.get("performance_score", 75) * 0.3
            security_score = security_analysis.get("security_score", 100) * 0.4

            total_score = quality_score + performance_score + security_score
            return min(100, max(0, total_score))

        except Exception as e:
            logger.error(f"❌ Erreur lors du calcul du score: {e}")
            return 50.0  # Score par défaut

    async def _create_file_structure(
        self,
        request: CodeGenerationRequest,
        main_code: str,
        tests: list[str],
        documentation: str,
        analysis: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Créer la structure de fichiers"""
        file_structure = {}
        analysis = analysis or {}

        # Fichier principal
        extension = "py" if request.language == "python" else "js"
        main_filename = f"generated_code.{extension}"
        file_structure[main_filename] = main_code

        # Fichier de tests
        test_filename = f"test_generated_code.{extension}"
        file_structure[test_filename] = "\n\n".join(tests)

        # Documentation
        file_structure["README.md"] = documentation

        # Configuration
        if request.language == "python":
            file_structure["requirements.txt"] = "\n".join(analysis.get("dependencies", []))
            file_structure["pyproject.toml"] = self._generate_pyproject_toml(request, analysis)
        elif request.language == "javascript":
            file_structure["package.json"] = self._generate_package_json(request)

        return file_structure

    def _generate_pyproject_toml(
        self, request: CodeGenerationRequest, analysis: dict[str, Any] | None = None
    ) -> str:
        """Générer pyproject.toml"""
        analysis = analysis or {}
        deps = json.dumps(analysis.get("dependencies", []))
        return f"""
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "generated-code-{request.request_id}"
version = "1.0.0"
description = "{request.description}"
authors = [{{name = "AI Generator", email = "ai@example.com"}}]
dependencies = {deps}

[tool.black]
line-length = 88
target-version = ['py38']

[tool.pytest.ini_options]
testpaths = ["tests"]
"""

    def _generate_package_json(self, request: CodeGenerationRequest) -> str:
        """Générer package.json"""
        return json.dumps({
            "name": f"generated-code-{request.request_id}",
            "version": "1.0.0",
            "description": request.description,
            "main": "generated_code.js",
            "scripts": {
                "test": "jest",
                "lint": "eslint ."
            },
            "dependencies": {},
            "devDependencies": {
                "jest": "^29.0.0",
                "eslint": "^8.0.0"
            }
        }, indent=2)

    # Méthodes utilitaires
    def _extract_class_name(self, description: str) -> str | None:
        """Extraire le nom de la classe de la description"""
        # Rechercher des patterns comme "class MyClass" ou "MyClass class"
        patterns = [
            r'class\s+(\w+)',
            r'(\w+)\s+class',
            r'créer\s+une?\s+classe\s+(\w+)',
            r'create\s+a?\s+class\s+(\w+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_function_name(self, description: str) -> str | None:
        """Extraire le nom de la fonction de la description"""
        patterns = [
            r'function\s+(\w+)',
            r'(\w+)\s+function',
            r'créer\s+une?\s+fonction\s+(\w+)',
            r'create\s+a?\s+function\s+(\w+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _generate_method_name(self, requirement: str) -> str:
        """Générer un nom de méthode à partir d'une exigence"""
        # Simplification: prendre les premiers mots importants
        words = requirement.lower().split()
        important_words = [w for w in words if len(w) > 3 and w not in ["pour", "avec", "dans", "sur"]]

        if important_words:
            method_name = "_".join(important_words[:3])
            return method_name.lower()
        else:
            return "generated_method"

    async def execute_from_prompt(self, prompt: str) -> dict[str, Any]:
        """Execute code generation from natural language prompt.

        This method allows the agent to be called from the TUI with plain text.
        It parses the prompt to extract code generation parameters.

        Args:
            prompt: Natural language code generation request

        Returns:
            Dict with generated code and analysis
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"💻 Executing code generation from prompt: {prompt[:100]}...")

        # Detect language from prompt
        language = "python"  # default
        prompt_lower = prompt.lower()

        if any(word in prompt_lower for word in ["javascript", "js", "node", "typescript", "ts"]):
            language = "javascript"
        elif any(word in prompt_lower for word in ["python", "py"]):
            language = "python"
        elif any(word in prompt_lower for word in ["rust", "cargo"]):
            language = "rust"
        elif any(word in prompt_lower for word in ["go", "golang"]):
            language = "go"

        # Detect framework
        framework = None
        if "fastapi" in prompt_lower:
            framework = "fastapi"
        elif "flask" in prompt_lower:
            framework = "flask"
        elif "django" in prompt_lower:
            framework = "django"
        elif "react" in prompt_lower:
            framework = "react"
        elif "vue" in prompt_lower:
            framework = "vue"

        # Extract requirements (sentences after "requirements:" or bulleted items)
        requirements = []
        req_match = re.search(r'requirements?:?\s*(.+?)(?:\.|$)', prompt, re.IGNORECASE)
        if req_match:
            req_text = req_match.group(1)
            requirements = [r.strip() for r in re.split(r'[,;]', req_text) if r.strip()]

        # Create request
        import time
        request = CodeGenerationRequest(
            request_id=f"prompt_{int(time.time())}",
            language=language,
            framework=framework,
            description=prompt,
            requirements=requirements or None
        )

        try:
            # Generate code
            result = await self.generate_code(request)

            return {
                "success": True,
                "language": result.language,
                "code": result.code,
                "tests": result.tests,
                "documentation": result.documentation,
                "quality_score": result.quality_score,
                "dependencies": result.dependencies,
                "file_structure": list(result.file_structure.keys()),
                "functions_count": len(result.functions),
                "classes_count": len(result.classes),
                "performance_analysis": result.performance_analysis,
                "security_analysis": result.security_analysis
            }

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "prompt": prompt
            }


# Fonctions utilitaires
def create_code_generator_agent() -> CodeGeneratorAgent:
    """Créer et initialiser l'agent de génération de code"""
    return CodeGeneratorAgent()

async def generate_code_simple(description: str, language: str = "python", **kwargs) -> GeneratedCode:
    """Générer du code de manière simple"""
    agent = create_code_generator_agent()

    try:
        await agent.initialize()

        # Créer la requête
        request = CodeGenerationRequest(
            request_id=f"simple_{int(time.time())}",
            language=language,
            description=description,
            requirements=kwargs.get("requirements", []),
            **kwargs
        )

        # Générer le code
        result = await agent.generate_code(request)

        return result

    finally:
        pass  # Pas de cleanup nécessaire


# Export
__all__ = [
    'CodeGeneratorAgent',
    'CodeGenerationRequest',
    'GeneratedCode',
    'CodeAnalysis',
    'create_code_generator_agent',
    'generate_code_simple'
]
