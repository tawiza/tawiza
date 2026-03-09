"""
Narrative Analyzer - TAJINE génère des analyses narratives des territoires.

Utilise Ollama local pour produire des analyses en langage naturel
à partir des métriques et signaux.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger


@dataclass
class NarrativeAnalysis:
    """Analyse narrative d'un territoire."""
    territory_code: str
    territory_name: str
    generated_at: datetime
    
    # Sections narratives
    situation: str          # État actuel
    diagnostic: str         # Causes identifiées
    tendance: str          # Évolution probable
    recommandations: str   # Actions suggérées
    
    # Metadata
    confidence: float
    model_used: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "generated_at": self.generated_at.isoformat(),
            "narrative": {
                "situation": self.situation,
                "diagnostic": self.diagnostic,
                "tendance": self.tendance,
                "recommandations": self.recommandations,
            },
            "confidence": round(self.confidence, 2),
            "model_used": self.model_used,
        }
    
    def to_text(self) -> str:
        """Format texte lisible."""
        return f"""## Analyse de {self.territory_name}

### 📊 Situation actuelle
{self.situation}

### 🔍 Diagnostic
{self.diagnostic}

### 📈 Tendance
{self.tendance}

### 💡 Recommandations
{self.recommandations}

---
*Analyse générée le {self.generated_at.strftime('%d/%m/%Y')} par {self.model_used}*
"""


class TAJINENarrativeAnalyzer:
    """
    Analyseur narratif utilisant TAJINE/Ollama pour générer
    des analyses en langage naturel.
    """
    
    # Prompt template pour l'analyse narrative
    ANALYSIS_PROMPT = """Tu es un expert en économie territoriale française. Analyse les données suivantes pour {territory_name} ({territory_code}) et produis une analyse concise.

DONNÉES ACTUELLES:
- Indice de vitalité: {vitality_index}/100
- Créations d'entreprises: {creations}
- Fermetures: {closures}
- Solde net: {net_creation:+d}
- Taux de chômage: {unemployment_rate:.1f}%
- Offres d'emploi: {job_offers}
- Procédures collectives: {procedures}

SIGNAUX DÉTECTÉS:
{signals_text}

SECTEURS DOMINANTS:
{sectors_text}

Produis une analyse structurée en 4 parties (2-3 phrases chacune):
1. SITUATION: État actuel du territoire
2. DIAGNOSTIC: Causes probables de cette situation
3. TENDANCE: Évolution attendue à court terme
4. RECOMMANDATIONS: Actions prioritaires

Sois factuel, concis et actionnable. Évite le jargon."""

    def __init__(self, model: str = "qwen2.5:7b"):
        self.model = model
        self._ollama_client = None
    
    @property
    def ollama_client(self):
        """Lazy loading du client Ollama."""
        if self._ollama_client is None:
            try:
                from src.infrastructure.llm.ollama_client import OllamaClient
                self._ollama_client = OllamaClient(model=self.model)
            except Exception as e:
                logger.warning(f"Ollama client not available: {e}")
                self._ollama_client = None
        return self._ollama_client
    
    async def analyze(
        self,
        territory_code: str,
        territory_name: str,
        metrics: dict[str, Any],
        signals: list[dict[str, Any]] | None = None,
        sectors: dict[str, Any] | None = None,
    ) -> NarrativeAnalysis:
        """
        Génère une analyse narrative pour un territoire.
        
        Args:
            territory_code: Code du département
            territory_name: Nom du territoire
            metrics: Métriques actuelles
            signals: Signaux détectés (optionnel)
            sectors: Analyse sectorielle (optionnel)
        """
        now = datetime.utcnow()
        
        # Formater les signaux
        signals_text = "Aucun signal particulier"
        if signals:
            signals_text = "\n".join([
                f"- {s.get('severity', 'info').upper()}: {s.get('title', 'Signal')}"
                for s in signals[:5]
            ])
        
        # Formater les secteurs
        sectors_text = "Données sectorielles non disponibles"
        if sectors and sectors.get("summary"):
            top = sectors["summary"].get("top_creators", [])[:3]
            if top:
                sectors_text = "\n".join([
                    f"- {s['short_name']}: {s['creations']} créations"
                    for s in top
                ])
        
        # Construire le prompt
        prompt = self.ANALYSIS_PROMPT.format(
            territory_name=territory_name,
            territory_code=territory_code,
            vitality_index=metrics.get("vitality_index", 50),
            creations=metrics.get("creations", 0),
            closures=metrics.get("closures", 0),
            net_creation=metrics.get("net_creation", 0),
            unemployment_rate=metrics.get("unemployment_rate", 7.0),
            job_offers=metrics.get("job_offers", 0),
            procedures=metrics.get("procedures", 0),
            signals_text=signals_text,
            sectors_text=sectors_text,
        )
        
        # Appeler Ollama ou générer une analyse par défaut
        if self.ollama_client:
            try:
                response = await self._call_ollama(prompt)
                sections = self._parse_response(response)
                return NarrativeAnalysis(
                    territory_code=territory_code,
                    territory_name=territory_name,
                    generated_at=now,
                    situation=sections.get("situation", "Analyse non disponible"),
                    diagnostic=sections.get("diagnostic", "Analyse non disponible"),
                    tendance=sections.get("tendance", "Analyse non disponible"),
                    recommandations=sections.get("recommandations", "Analyse non disponible"),
                    confidence=0.8,
                    model_used=self.model,
                )
            except Exception as e:
                logger.error(f"Ollama analysis failed: {e}")
        
        # Fallback : analyse basée sur les règles
        return self._generate_rule_based_analysis(
            territory_code, territory_name, metrics, signals, now
        )
    
    async def _call_ollama(self, prompt: str) -> str:
        """Appelle Ollama pour générer l'analyse."""
        import httpx
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 500},
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")
    
    def _parse_response(self, response: str) -> dict[str, str]:
        """Parse la réponse LLM en sections."""
        sections = {
            "situation": "",
            "diagnostic": "",
            "tendance": "",
            "recommandations": "",
        }
        
        current_section = None
        lines = response.split("\n")
        
        for line in lines:
            line_lower = line.lower().strip()
            
            if "situation" in line_lower and ":" in line_lower:
                current_section = "situation"
                continue
            elif "diagnostic" in line_lower and ":" in line_lower:
                current_section = "diagnostic"
                continue
            elif "tendance" in line_lower and ":" in line_lower:
                current_section = "tendance"
                continue
            elif "recommandation" in line_lower and ":" in line_lower:
                current_section = "recommandations"
                continue
            
            if current_section and line.strip():
                sections[current_section] += line.strip() + " "
        
        # Nettoyer
        for k in sections:
            sections[k] = sections[k].strip()
        
        return sections
    
    def _generate_rule_based_analysis(
        self,
        territory_code: str,
        territory_name: str,
        metrics: dict[str, Any],
        signals: list[dict[str, Any]] | None,
        now: datetime,
    ) -> NarrativeAnalysis:
        """Génère une analyse basée sur des règles (fallback sans LLM)."""
        vitality = metrics.get("vitality_index", 50)
        net = metrics.get("net_creation", 0)
        unemployment = metrics.get("unemployment_rate", 7.0)
        
        # Situation
        if vitality >= 60:
            situation = f"{territory_name} affiche une bonne dynamique économique avec un indice de vitalité de {vitality:.1f}/100."
        elif vitality >= 45:
            situation = f"{territory_name} présente une situation économique stable avec une vitalité de {vitality:.1f}/100."
        else:
            situation = f"{territory_name} traverse une période difficile avec un indice de vitalité de {vitality:.1f}/100."
        
        # Diagnostic
        if net > 0:
            diagnostic = f"Le solde net de +{net} entreprises indique une création supérieure aux fermetures."
        elif net < 0:
            diagnostic = f"Le solde négatif de {net} entreprises révèle plus de fermetures que de créations."
        else:
            diagnostic = "Le nombre de créations équilibre les fermetures."
        
        if unemployment > 9:
            diagnostic += f" Le chômage élevé ({unemployment:.1f}%) pèse sur l'attractivité."
        elif unemployment < 6:
            diagnostic += f" Le faible taux de chômage ({unemployment:.1f}%) témoigne d'un marché de l'emploi tendu."
        
        # Tendance
        if signals:
            critical = [s for s in signals if s.get("severity") in ("alert", "critical")]
            if critical:
                tendance = "Plusieurs signaux d'alerte suggèrent une vigilance accrue à court terme."
            else:
                tendance = "Les indicateurs ne montrent pas de dégradation imminente."
        else:
            tendance = "La tendance reste à confirmer avec plus de données historiques."
        
        # Recommandations
        if vitality < 45:
            recommandations = "Priorité : identifier les secteurs en difficulté et accompagner les entreprises fragiles."
        elif unemployment > 9:
            recommandations = "Focus sur l'emploi : renforcer les dispositifs d'insertion et attirer des entreprises."
        else:
            recommandations = "Maintenir la dynamique et surveiller les secteurs émergents."
        
        return NarrativeAnalysis(
            territory_code=territory_code,
            territory_name=territory_name,
            generated_at=now,
            situation=situation,
            diagnostic=diagnostic,
            tendance=tendance,
            recommandations=recommandations,
            confidence=0.6,
            model_used="rule-based",
        )


# Singleton
_analyzer: TAJINENarrativeAnalyzer | None = None


def get_narrative_analyzer(model: str = "qwen2.5:7b") -> TAJINENarrativeAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = TAJINENarrativeAnalyzer(model=model)
    return _analyzer
