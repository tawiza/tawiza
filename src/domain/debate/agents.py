"""Debate agents for multi-agent validation system.

This module provides a multi-agent debate system for data validation:
- ChercheurAgent: Analyzes and summarizes collected data
- CritiqueAgent: Identifies issues and validates findings
- VerificateurAgent: Cross-validates and provides final assessment
- FactCheckerAgent: Verifies claims against external sources
- SourceRankerAgent: Ranks sources by reliability
- SynthesisAgent: Creates final comprehensive summary

Each agent can optionally use an LLM for more intelligent analysis.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from loguru import logger


class AgentRole(Enum):
    """Roles that agents can play in the debate."""

    RESEARCHER = "researcher"
    CRITIC = "critic"
    VERIFIER = "verifier"
    FACT_CHECKER = "fact_checker"
    SOURCE_RANKER = "source_ranker"
    SYNTHESIZER = "synthesizer"


@dataclass
class AgentMessage:
    """Message from an agent during debate."""

    agent: str
    role: str
    content: str
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent": self.agent,
            "role": self.role,
            "content": self.content,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "issues": self.issues,
            "metadata": self.metadata,
        }


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers that agents can use."""

    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate text from prompt."""
        ...


class BaseAgent(ABC):
    """Base class for debate agents with optional LLM support.

    Agents can operate in two modes:
    1. Rule-based (default): Uses predefined logic for analysis
    2. LLM-enhanced: Uses an LLM for more intelligent responses

    Example:
        agent = ChercheurAgent(llm=my_llm_provider)
        result = await agent.process(data, context)
    """

    name: str
    role: str

    def __init__(self, llm: LLMProvider | None = None):
        """Initialize agent with optional LLM provider.

        Args:
            llm: Optional LLM provider for enhanced analysis
        """
        self._llm = llm

    @property
    def has_llm(self) -> bool:
        """Check if agent has LLM support enabled."""
        return self._llm is not None

    async def _generate_with_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str | None:
        """Generate response using LLM if available.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text or None if LLM not available
        """
        if self._llm is None:
            return None
        try:
            return await self._llm.generate(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"{self.name}: LLM generation failed: {e}")
            return None

    @abstractmethod
    async def process(
        self,
        data: dict[str, Any],
        context: list[AgentMessage],
    ) -> AgentMessage:
        """Process data and return agent's assessment."""
        pass


class ChercheurAgent(BaseAgent):
    """Researcher agent - collects and summarizes data.

    Role: Search for information, aggregate results, identify key findings.
    Can use LLM for more intelligent summarization.
    """

    name = "Chercheur"
    role = "researcher"

    SYSTEM_PROMPT = """# Identité
Tu es le Chercheur, premier analyste du pipeline Tawiza. Tu parles comme un consultant data qui présente ses découvertes à un client - clair, structuré, avec des insights actionnables.

# Mission
Analyser les données brutes collectées depuis les sources françaises (SIRENE, BODACC, BOAMP...) et produire une cartographie initiale du marché.

# Méthodologie (suis ces étapes)
1. **Inventaire** : Compte les résultats par source
2. **Qualité** : Évalue la complétude des données (SIRET présents ? Dates ? Géoloc ?)
3. **Patterns** : Identifie les tendances (secteurs dominants, zones géographiques, tailles)
4. **Anomalies** : Repère ce qui manque ou semble incohérent
5. **Synthèse** : Résume en 3-5 points clés pour les agents suivants

# Critères de confiance (0-100)
- 80+ : Données riches, 3+ sources, >10 résultats, SIRET majoritaires
- 60-79 : Données correctes, 2 sources, quelques lacunes mineures
- 40-59 : Données limitées, 1 source ou beaucoup de champs manquants
- <40 : Données insuffisantes pour analyse fiable

# Format de réponse
Réponds en français avec cette structure :

**📊 Cartographie des données**
[Résumé des sources et volumes]

**🔍 Ce que je vois**
[3-5 observations clés sur les données]

**⚠️ Points d'attention**
[Ce qui manque ou semble problématique]

**📈 Score de confiance : XX%**
[Justification en 1 phrase]"""

    def __init__(self, llm: LLMProvider | None = None):
        super().__init__(llm)

    async def process(
        self,
        data: dict[str, Any],
        context: list[AgentMessage],
    ) -> AgentMessage:
        """Analyze collected data and summarize findings."""
        results = data.get("results", [])
        data.get("sources", [])

        # Analyze results
        findings = []
        evidence = []

        # Group by source type
        by_source: dict[str, list] = {}
        for item in results:
            source = item.get("source", "unknown")
            by_source.setdefault(source, []).append(item)

        for source, items in by_source.items():
            findings.append(f"- {source}: {len(items)} résultats trouvés")
            if items:
                evidence.append(
                    {
                        "source": source,
                        "count": len(items),
                        "sample": items[0] if items else None,
                    }
                )

        # Calculate initial confidence based on data quantity and diversity
        source_diversity = len(by_source)
        total_results = len(results)

        if total_results == 0:
            confidence = 0
            content = "Aucun résultat trouvé dans les sources interrogées."
        elif source_diversity >= 3 and total_results >= 10:
            confidence = 80
            content = (
                f"Données riches collectées: {total_results} résultats de {source_diversity} sources.\n"
                + "\n".join(findings)
            )
        elif source_diversity >= 2:
            confidence = 60
            content = (
                f"Données modérées: {total_results} résultats de {source_diversity} sources.\n"
                + "\n".join(findings)
            )
        else:
            confidence = 40
            content = (
                f"Données limitées: {total_results} résultats d'une seule source.\n"
                + "\n".join(findings)
            )

        # Use LLM for enhanced analysis if available
        if self.has_llm and results:
            llm_prompt = f"""Analyse ces données de recherche et fournis un résumé:

Nombre total de résultats: {total_results}
Sources consultées: {", ".join(by_source.keys())}

Résultats par source:
{chr(10).join(findings)}

Échantillon de données:
{results[:3]}

Fournis:
1. Un résumé des principales informations trouvées
2. Les tendances ou patterns identifiés
3. La qualité globale des données"""

            llm_response = await self._generate_with_llm(llm_prompt, self.SYSTEM_PROMPT)
            if llm_response:
                content = f"{content}\n\n### Analyse LLM:\n{llm_response}"

        logger.debug(f"Chercheur: confidence={confidence}, sources={source_diversity}")

        return AgentMessage(
            agent=self.name,
            role=self.role,
            content=content,
            confidence=confidence,
            evidence=evidence,
        )


class CritiqueAgent(BaseAgent):
    """Critic agent - questions and validates findings.

    Role: Identify inconsistencies, question assumptions, find gaps.
    Can use LLM for deeper analysis of data quality issues.
    """

    name = "Critique"
    role = "critic"

    SYSTEM_PROMPT = """# Identité
Tu es le Critique, l'avocat du diable du pipeline. Tu penses comme un investisseur sceptique qui cherche les failles avant de prendre une décision. Tu n'es pas négatif - tu es exigeant pour protéger l'utilisateur des mauvaises conclusions.

# Mission
Challenger les données et les analyses précédentes. Identifier les incohérences, données manquantes, et hypothèses non vérifiées.

# Contexte inter-agents
Tu reçois :
- L'analyse du Chercheur (cartographie initiale)
- Le classement du SourceRanker (fiabilité des sources)

Ton rôle : trouver ce qu'ils ont pu manquer ou surestimer.

# Méthodologie (pense comme un auditeur)
1. **Complétude** : Qu'est-ce qui manque ? (SIRET absents, dates vides, géoloc manquante)
2. **Cohérence** : Y a-t-il des contradictions entre sources ?
3. **Fraîcheur** : Les données sont-elles à jour ? Risque d'obsolescence ?
4. **Représentativité** : L'échantillon est-il biaisé ? (surreprésentation géographique, sectorielle)
5. **Hypothèses cachées** : Quelles conclusions non prouvées les agents précédents ont-ils faites ?

# Questions à te poser
- "Si je devais investir 100K€ sur ces données, qu'est-ce qui me ferait hésiter ?"
- "Qu'est-ce qu'un concurrent verrait que nous avons raté ?"
- "Dans 6 mois, quelles données seront obsolètes ?"

# Critères de confiance (ajustement)
Tu RÉDUIS la confiance des agents précédents selon les problèmes trouvés :
- Problème mineur : -5 points (champ manquant non critique)
- Problème modéré : -10 points (source unique, données datées)
- Problème majeur : -20 points (incohérence factuelle, biais évident)

# Format de réponse
**🔎 Revue critique**
[Résumé de ton analyse des travaux précédents]

**⚠️ Problèmes identifiés**
[Liste numérotée avec sévérité : 🟡 mineur / 🟠 modéré / 🔴 majeur]

**❓ Questions ouvertes**
[Ce qu'il faudrait vérifier mais qu'on ne peut pas avec les données actuelles]

**💡 Pistes d'amélioration**
[Comment renforcer l'analyse]

**📈 Score de confiance ajusté : XX%**
[Score précédent - pénalités = nouveau score, avec justification]"""

    def __init__(self, llm: LLMProvider | None = None):
        super().__init__(llm)

    async def process(
        self,
        data: dict[str, Any],
        context: list[AgentMessage],
    ) -> AgentMessage:
        """Critique the findings and identify issues."""
        results = data.get("results", [])
        issues = []

        # Check for data quality issues
        if not results:
            issues.append("Aucune donnée à analyser")
            return AgentMessage(
                agent=self.name,
                role=self.role,
                content="Impossible de critiquer sans données.",
                confidence=0,
                issues=issues,
            )

        # Check for missing critical fields
        missing_siret = sum(1 for r in results if not r.get("siret"))
        if missing_siret > len(results) * 0.5:
            issues.append(
                f"{missing_siret}/{len(results)} résultats sans SIRET - identification difficile"
            )

        # Check for date freshness
        old_data = 0
        for r in results:
            date_field = r.get("published_dt") or r.get("date") or r.get("created_at")
            if not date_field:
                old_data += 1
        if old_data > len(results) * 0.3:
            issues.append(f"{old_data} résultats sans date - fraîcheur incertaine")

        # Check source reliability
        sources = {r.get("source", "unknown") for r in results}
        official_sources = {"sirene", "bodacc", "boamp", "ban"}
        unofficial_only = not sources.intersection(official_sources)
        if unofficial_only:
            issues.append("Aucune source officielle (INSEE, BODACC) - fiabilité réduite")

        # Check for contradictions in previous context
        if context:
            chercheur_msg = next((m for m in context if m.role == "researcher"), None)
            if chercheur_msg and chercheur_msg.confidence < 50:
                issues.append("Le Chercheur a signalé un faible niveau de confiance initial")

        # Calculate confidence adjustment
        confidence_penalty = len(issues) * 10
        base_confidence = context[-1].confidence if context else 50
        adjusted_confidence = max(0, base_confidence - confidence_penalty)

        if issues:
            content = "Points d'attention identifiés:\n" + "\n".join(f"⚠️ {i}" for i in issues)
        else:
            content = "✓ Aucun problème majeur détecté dans les données."
            adjusted_confidence = min(adjusted_confidence + 10, 100)

        # Use LLM for deeper analysis if available
        if self.has_llm and results:
            chercheur_content = ""
            if context:
                chercheur_msg = next((m for m in context if m.role == "researcher"), None)
                if chercheur_msg:
                    chercheur_content = chercheur_msg.content

            llm_prompt = f"""Analyse critique des données collectées:

Problèmes détectés automatiquement:
{chr(10).join(f"- {i}" for i in issues) if issues else "- Aucun problème détecté"}

Résumé du Chercheur:
{chercheur_content[:500] if chercheur_content else "Non disponible"}

Échantillon de données:
{results[:2]}

Identifie:
1. D'autres problèmes potentiels non détectés
2. Des incohérences dans les données
3. Des recommandations pour améliorer la qualité"""

            llm_response = await self._generate_with_llm(llm_prompt, self.SYSTEM_PROMPT)
            if llm_response:
                content = f"{content}\n\n### Critique LLM:\n{llm_response}"

        logger.debug(f"Critique: found {len(issues)} issues, confidence={adjusted_confidence}")

        return AgentMessage(
            agent=self.name,
            role=self.role,
            content=content,
            confidence=adjusted_confidence,
            issues=issues,
        )


class VerificateurAgent(BaseAgent):
    """Verifier agent - cross-validates with external sources.

    Role: Verify claims, check consistency, provide final assessment.
    Can use LLM for more nuanced verification reasoning.
    """

    name = "Vérificateur"
    role = "verifier"

    SYSTEM_PROMPT = """# Identité
Tu es le Vérificateur, le juge du pipeline. Tu synthétises les analyses de tous les agents et rends un verdict motivé. Tu parles comme un consultant senior qui présente un audit complet - avec des chiffres impressionnants et des conclusions claires.

# Mission
Consolider les analyses, produire un bilan chiffré exhaustif, et rendre un verdict de fiabilité avec recommandations d'usage.

# Contexte inter-agents
Tu as accès à tout le débat :
- **Chercheur** : Cartographie initiale
- **SourceRanker** : Évaluation des sources
- **Critique** : Problèmes identifiés
- **FactChecker** : Faits vérifiés

# Métriques à calculer et afficher
Toujours montrer l'AMPLEUR de l'analyse :
- **Volume total** : X résultats analysés (affiche "1.2M" si > 1 million, "15K" si > 1000)
- **Sources consultées** : X sources sur Y disponibles
- **Taux de complétude** : X% des champs critiques renseignés
- **Taux de vérification** : X% corroborés par source officielle
- **Couverture géographique** : X départements / X régions
- **Couverture temporelle** : données de [date min] à [date max]
- **Entités uniques** : X entreprises distinctes identifiées

# Méthodologie
1. **Compiler les métriques** de tous les agents
2. **Calculer les taux** (complétude, vérification, couverture)
3. **Pondérer les scores** des agents
4. **Rendre un verdict** basé sur les chiffres
5. **Contextualiser** : comparer à ce qu'on attendrait idéalement

# Échelle de verdict
- **✅ HAUTE CONFIANCE (80-100)** : Analyse robuste, données exploitables
- **⚡ CONFIANCE MOYENNE (60-79)** : Solide avec réserves mineures
- **⚠️ CONFIANCE LIMITÉE (40-59)** : Indicatif seulement
- **❌ INSUFFISANT (<40)** : Données inexploitables

# Format de réponse
**⚖️ VERDICT : [NIVEAU]**

**📊 BILAN CHIFFRÉ**
┌─────────────────────────────────────┐
│ 📁 Volume analysé    : XX XXX résultats
│ 🔌 Sources actives   : X/Y sources
│ ✅ Taux vérification : XX%
│ 📋 Complétude SIRET  : XX%
│ 🗺️ Couverture        : X départements
│ 📅 Période           : [date] → [date]
│ 🏢 Entités uniques   : X entreprises
└─────────────────────────────────────┘

**📈 SCORES PAR AGENT**
| Agent | Score | Contribution |
|-------|-------|--------------|
| Chercheur | XX% | [point clé] |
| SourceRanker | XX% | [point clé] |
| Critique | XX% | [point clé] |
| FactChecker | XX% | [point clé] |

**🎯 CONCLUSIONS SOLIDES**
[Ce qu'on peut affirmer avec certitude]

**⚠️ LIMITES**
[Ce qui reste incertain]

**💼 USAGE RECOMMANDÉ**
[Pour quoi utiliser ces données / pour quoi éviter]

**📈 SCORE FINAL : XX%**
[Formule : (Chercheur×0.2 + SourceRanker×0.2 + Critique×0.25 + FactChecker×0.35)]"""

    def __init__(self, llm: LLMProvider | None = None):
        super().__init__(llm)

    async def process(
        self,
        data: dict[str, Any],
        context: list[AgentMessage],
    ) -> AgentMessage:
        """Verify findings and provide final assessment."""
        results = data.get("results", [])

        # Collect all issues from previous agents
        all_issues = []
        for msg in context:
            all_issues.extend(msg.issues)

        # Cross-validation checks
        verification_results = []

        # Check SIRET validity (format check)
        sirets = [r.get("siret") for r in results if r.get("siret")]
        valid_sirets = [s for s in sirets if len(str(s).replace(" ", "")) == 14]
        if sirets:
            verification_results.append(f"SIRET valides: {len(valid_sirets)}/{len(sirets)}")

        # Check for corroborating evidence
        by_entity: dict[str, list] = {}
        for r in results:
            key = r.get("siret") or r.get("name", "unknown")
            by_entity.setdefault(key, []).append(r.get("source"))

        multi_source_entities = sum(1 for sources in by_entity.values() if len(set(sources)) > 1)
        if multi_source_entities > 0:
            verification_results.append(f"Entités multi-sources (fiables): {multi_source_entities}")

        # Calculate final confidence
        base_confidence = context[-1].confidence if context else 50

        # Boost for multi-source verification
        if multi_source_entities > 0:
            base_confidence += 10

        # Penalty for remaining issues
        base_confidence -= len(all_issues) * 5

        final_confidence = max(0, min(100, base_confidence))

        # Generate verdict
        if final_confidence >= 80:
            verdict = "✅ HAUTE CONFIANCE - Données vérifiées et corroborées"
        elif final_confidence >= 60:
            verdict = "⚡ CONFIANCE MOYENNE - Quelques points à vérifier"
        elif final_confidence >= 40:
            verdict = "⚠️ CONFIANCE FAIBLE - Vérification manuelle recommandée"
        else:
            verdict = "❌ CONFIANCE TRÈS FAIBLE - Données insuffisantes"

        content = f"{verdict}\n\nVérifications effectuées:\n" + "\n".join(
            f"• {v}" for v in verification_results
        )

        if all_issues:
            content += "\n\nProblèmes non résolus:\n" + "\n".join(f"• {i}" for i in all_issues[:3])

        # Use LLM for enhanced verification if available
        if self.has_llm and results:
            context_summary = "\n".join(f"- {m.agent}: {m.content[:200]}" for m in context[-3:])
            llm_prompt = f"""Synthèse de vérification des données:

Verdict actuel: {verdict}
Confiance: {final_confidence}%

Contexte des agents précédents:
{context_summary}

Vérifications effectuées:
{chr(10).join(f"- {v}" for v in verification_results)}

Problèmes identifiés:
{chr(10).join(f"- {i}" for i in all_issues[:5]) if all_issues else "- Aucun"}

Fournis:
1. Une évaluation finale de la fiabilité des données
2. Des recommandations pour l'utilisateur"""

            llm_response = await self._generate_with_llm(llm_prompt, self.SYSTEM_PROMPT)
            if llm_response:
                content = f"{content}\n\n### Vérification LLM:\n{llm_response}"

        logger.debug(f"Vérificateur: final_confidence={final_confidence}")

        return AgentMessage(
            agent=self.name,
            role=self.role,
            content=content,
            confidence=final_confidence,
            issues=all_issues,
        )


class FactCheckerAgent(BaseAgent):
    """Fact checker agent - verifies claims against known data.

    Role: Cross-reference claims with authoritative sources,
    detect potential misinformation, verify key facts.
    """

    name = "Fact-Checker"
    role = "fact_checker"

    SYSTEM_PROMPT = """# Identité
Tu es le Fact-Checker, le journaliste d'investigation du pipeline. Tu appliques la règle d'or : "Une info non corroborée n'est pas une info". Tu expliques ton travail comme un fact-checker de média qui montre ses sources.

# Mission
Vérifier que les informations clés sont corroborées par des sources officielles. Distinguer les faits vérifiés des affirmations non prouvées.

# Contexte inter-agents
Tu reçois :
- Cartographie du Chercheur
- Classement des sources du SourceRanker
- Problèmes identifiés par le Critique

Ton rôle : établir ce qui est PROUVÉ vs ce qui est SUPPOSÉ.

# Sources autoritatives (les seules qui "prouvent")
- **SIRENE** : Existence légale de l'entreprise, SIRET, NAF, effectifs déclarés
- **BODACC** : Événements juridiques (création, radiation, procédures)
- **BOAMP** : Marchés publics attribués (preuve d'activité)
- **BAN** : Adresse vérifiée

# Méthodologie de vérification
1. **Extraction des claims** : Quelles affirmations sont faites sur les entités ?
2. **Cross-référencement** : Cette entité existe-t-elle dans SIRENE/BODACC ?
3. **Corroboration** : Combien de sources confirment la même info ?
4. **Statut par entité** :
   - ✅ VÉRIFIÉ : Présent dans source officielle
   - ⚠️ PARTIELLEMENT VÉRIFIÉ : Source officielle + non-officielle concordantes
   - ❓ NON VÉRIFIÉ : Uniquement sources non-officielles
   - ❌ CONTRADICTOIRE : Sources en désaccord

# Critères de confiance
- 80+ : >70% des entités vérifiées par source officielle
- 60-79 : 50-70% vérifiées, reste partiellement vérifié
- 40-59 : <50% vérifiées, beaucoup de non-vérifiés
- <40 : Majorité non vérifiée ou contradictions

# Format de réponse
**📋 Bilan de vérification**
[X/Y entités vérifiées par sources officielles]

**✅ Faits confirmés**
[Liste des informations prouvées avec source]

**⚠️ À confirmer**
[Informations plausibles mais non prouvées]

**❌ Alertes**
[Contradictions ou informations douteuses]

**📈 Score de confiance : XX%**
[Basé sur le ratio vérifié/total]"""

    # Known reliable source types for fact-checking
    AUTHORITATIVE_SOURCES = {"sirene", "bodacc", "boamp", "ban", "subventions"}

    def __init__(self, llm: LLMProvider | None = None):
        super().__init__(llm)

    async def process(
        self,
        data: dict[str, Any],
        context: list[AgentMessage],
    ) -> AgentMessage:
        """Verify facts in the data against authoritative sources."""
        results = data.get("results", [])
        verified_facts = []
        unverified_claims = []
        issues = []

        # Group results by entity (SIRET or name)
        entities: dict[str, list[dict]] = {}
        for r in results:
            key = r.get("siret") or r.get("name", "unknown")
            entities.setdefault(key, []).append(r)

        # Check each entity against authoritative sources
        for entity_key, entity_results in entities.items():
            sources = {r.get("source") for r in entity_results}
            auth_sources = sources.intersection(self.AUTHORITATIVE_SOURCES)

            if auth_sources:
                verified_facts.append(
                    {
                        "entity": entity_key,
                        "verified_by": list(auth_sources),
                        "claim_count": len(entity_results),
                    }
                )
            else:
                unverified_claims.append(
                    {
                        "entity": entity_key,
                        "sources": list(sources),
                    }
                )

        # Calculate confidence based on verification ratio
        total_entities = len(entities)
        verified_count = len(verified_facts)

        if total_entities == 0:
            confidence = 0
            content = "Aucune entité à vérifier."
        else:
            verification_ratio = verified_count / total_entities
            confidence = int(verification_ratio * 100)

            content_parts = [
                f"Vérification factuelle: {verified_count}/{total_entities} entités vérifiées"
            ]

            if verified_facts:
                content_parts.append("\n✓ Faits vérifiés:")
                for fact in verified_facts[:5]:
                    content_parts.append(
                        f"  • {fact['entity'][:30]} (via {', '.join(fact['verified_by'])})"
                    )

            if unverified_claims:
                issues.append(f"{len(unverified_claims)} entités sans source officielle")
                content_parts.append("\n⚠️ Claims non vérifiés:")
                for claim in unverified_claims[:3]:
                    content_parts.append(
                        f"  • {claim['entity'][:30]} (sources: {', '.join(claim['sources'])})"
                    )

            content = "\n".join(content_parts)

        # Use LLM for enhanced fact-checking if available
        if self.has_llm and results:
            llm_prompt = f"""Analyse de fact-checking:

Entités vérifiées: {verified_count}/{total_entities}
Sources autoritatives utilisées: {", ".join(self.AUTHORITATIVE_SOURCES)}

Faits vérifiés:
{chr(10).join(f"- {f['entity']}: {f['verified_by']}" for f in verified_facts[:5]) if verified_facts else "- Aucun"}

Claims non vérifiés:
{chr(10).join(f"- {c['entity']}: {c['sources']}" for c in unverified_claims[:5]) if unverified_claims else "- Aucun"}

Évalue:
1. La fiabilité globale des informations
2. Les risques de désinformation
3. Des sources supplémentaires à consulter"""

            llm_response = await self._generate_with_llm(llm_prompt, self.SYSTEM_PROMPT)
            if llm_response:
                content = f"{content}\n\n### Fact-Check LLM:\n{llm_response}"

        logger.debug(f"FactChecker: verified={verified_count}/{total_entities}")

        return AgentMessage(
            agent=self.name,
            role=self.role,
            content=content,
            confidence=confidence,
            issues=issues,
            metadata={
                "verified_facts": verified_facts,
                "unverified_claims": unverified_claims,
            },
        )


class SourceRankerAgent(BaseAgent):
    """Source ranker agent - evaluates and ranks data sources.

    Role: Assess source reliability, freshness, and relevance.
    Provide a ranking of sources for the given query.
    """

    name = "Source-Ranker"
    role = "source_ranker"

    SYSTEM_PROMPT = """# Identité
Tu es le Source-Ranker, l'expert en évaluation de fiabilité. Tu agis comme un bibliothécaire rigoureux qui classe les sources par crédibilité. Tu expliques tes choix comme un consultant qui justifie ses recommandations.

# Mission
Évaluer et classer les sources de données utilisées, en distinguant les sources officielles (haute fiabilité) des sources secondaires (à vérifier).

# Contexte inter-agents
Tu reçois l'analyse du Chercheur. Utilise ses observations pour contextualiser ton évaluation des sources.

# Hiérarchie de fiabilité (référence)
- **Tier 1 (90-100)** : SIRENE (INSEE), BODACC, BOAMP, BAN → Officielles, légales
- **Tier 2 (70-89)** : Subventions data.gouv → Officielles mais parfois datées
- **Tier 3 (50-69)** : GDELT, Google News → Agrégateurs, vérifier les faits
- **Tier 4 (<50)** : RSS générique, sources inconnues → Non vérifiées

# Méthodologie
1. **Inventaire sources** : Liste les sources présentes dans les données
2. **Classification** : Attribue un tier à chaque source
3. **Couverture** : Évalue si le mix de sources est équilibré
4. **Risques** : Identifie les dépendances à des sources peu fiables
5. **Recommandation** : Suggère des sources complémentaires si nécessaire

# Critères de confiance
- 80+ : Majorité de sources Tier 1-2, bonne diversité
- 60-79 : Mix équilibré avec quelques sources Tier 3
- 40-59 : Dépendance forte aux sources Tier 3-4
- <40 : Sources majoritairement non officielles

# Format de réponse
**🏆 Classement des sources**
[Liste ordonnée avec score et justification courte]

**⚖️ Équilibre du mix**
[Analyse de la diversité et complémentarité]

**🎯 Recommandation**
[Sources à privilégier / à compléter]

**📈 Score de confiance : XX%**
[Basé sur la qualité du mix de sources]"""

    # Source reliability scores (0-100)
    SOURCE_RELIABILITY = {
        "sirene": 95,  # Official INSEE registry
        "bodacc": 90,  # Official legal announcements
        "boamp": 90,  # Official public procurement
        "ban": 85,  # Official address database
        "subventions": 80,  # Government grants data
        "gdelt": 60,  # News aggregator
        "google_news": 55,  # RSS news feed
        "rss": 50,  # Generic RSS feeds
        "unknown": 30,  # Unknown sources
    }

    def __init__(self, llm: LLMProvider | None = None):
        super().__init__(llm)

    async def process(
        self,
        data: dict[str, Any],
        context: list[AgentMessage],
    ) -> AgentMessage:
        """Rank and evaluate data sources."""
        results = data.get("results", [])

        # Analyze sources
        source_stats: dict[str, dict] = {}
        for r in results:
            source = r.get("source", "unknown")
            if source not in source_stats:
                source_stats[source] = {
                    "count": 0,
                    "reliability": self.SOURCE_RELIABILITY.get(source, 30),
                    "has_dates": 0,
                    "has_siret": 0,
                }
            source_stats[source]["count"] += 1
            if r.get("published_dt") or r.get("date") or r.get("created_at"):
                source_stats[source]["has_dates"] += 1
            if r.get("siret"):
                source_stats[source]["has_siret"] += 1

        # Calculate composite scores
        ranked_sources = []
        for source, stats in source_stats.items():
            # Base reliability
            score = stats["reliability"]

            # Bonus for data completeness
            if stats["count"] > 0:
                date_ratio = stats["has_dates"] / stats["count"]
                siret_ratio = stats["has_siret"] / stats["count"]
                score += int(date_ratio * 5)  # +5 for all dated
                score += int(siret_ratio * 10)  # +10 for all with SIRET

            ranked_sources.append(
                {
                    "source": source,
                    "score": min(score, 100),
                    "count": stats["count"],
                    "reliability": stats["reliability"],
                }
            )

        # Sort by score descending
        ranked_sources.sort(key=lambda x: x["score"], reverse=True)

        # Calculate overall confidence based on best sources
        if not ranked_sources:
            confidence = 0
            content = "Aucune source à évaluer."
        else:
            # Weighted average of top sources
            top_scores = [s["score"] for s in ranked_sources[:3]]
            confidence = int(sum(top_scores) / len(top_scores))

            content_parts = ["Classement des sources:"]
            for i, src in enumerate(ranked_sources, 1):
                reliability_label = (
                    "🟢" if src["score"] >= 80 else "🟡" if src["score"] >= 60 else "🔴"
                )
                content_parts.append(
                    f"{i}. {reliability_label} {src['source']}: {src['score']}/100 ({src['count']} résultats)"
                )

            content = "\n".join(content_parts)

        issues = []
        low_reliability = [s for s in ranked_sources if s["score"] < 50]
        if low_reliability:
            issues.append(
                f"{len(low_reliability)} sources peu fiables: {', '.join(s['source'] for s in low_reliability)}"
            )

        # Use LLM for enhanced source analysis if available
        if self.has_llm and ranked_sources:
            llm_prompt = f"""Analyse des sources de données:

Classement actuel:
{chr(10).join(f"- {s['source']}: {s['score']}/100 ({s['count']} résultats)" for s in ranked_sources)}

Évalue:
1. La pertinence du classement pour cette recherche
2. Des sources complémentaires à considérer
3. La diversité et l'équilibre des sources"""

            llm_response = await self._generate_with_llm(llm_prompt, self.SYSTEM_PROMPT)
            if llm_response:
                content = f"{content}\n\n### Analyse LLM:\n{llm_response}"

        logger.debug(f"SourceRanker: top_confidence={confidence}")

        return AgentMessage(
            agent=self.name,
            role=self.role,
            content=content,
            confidence=confidence,
            issues=issues,
            metadata={"ranked_sources": ranked_sources},
        )


class SynthesisAgent(BaseAgent):
    """Synthesis agent - creates comprehensive final summary.

    Role: Aggregate findings from all agents, create actionable summary,
    highlight key insights and recommendations.
    """

    name = "Synthèse"
    role = "synthesizer"

    SYSTEM_PROMPT = """# Identité
Tu es l'agent Synthèse, le directeur de mission qui conclut l'audit. Tu parles comme un partner de cabinet de conseil qui présente les conclusions au comité de direction - clair, actionnable, orienté décision.

# Mission
Transformer tout le débat en un rapport exécutif actionnable. Pas de jargon technique - des insights business et des recommandations concrètes.

# Contexte inter-agents
Tu as l'intégralité du débat :
- **Chercheur** : Cartographie des données
- **SourceRanker** : Fiabilité des sources
- **Critique** : Problèmes identifiés
- **FactChecker** : Faits vérifiés
- **Vérificateur** : Verdict et métriques

Ton rôle : rendre tout ça ACTIONNABLE.

# Méthodologie
1. **Executive Summary** : 3 phrases max pour un décideur pressé
2. **Chiffres clés** : Les 5 métriques les plus importantes
3. **Insights** : Qu'est-ce qu'on a appris ? (pas juste les données, les CONCLUSIONS)
4. **Risques** : Qu'est-ce qui pourrait mal tourner si on utilise ces données ?
5. **Actions recommandées** : Quoi faire maintenant ? (priorisé)
6. **Prochaines étapes** : Comment aller plus loin ?

# Règles de rédaction
- **Pas de conditionnel** : "Nous recommandons" pas "Nous pourrions recommander"
- **Chiffres en évidence** : Toujours mettre les stats importantes en gras
- **Actions concrètes** : "Contacter les 5 entreprises clés" pas "Envisager des contacts"
- **Priorisation** : Toujours numéroter par ordre d'importance

# Format de réponse
**📋 SYNTHÈSE EXÉCUTIVE**
[3 phrases max - le strict essentiel pour un décideur]

**🔢 CHIFFRES CLÉS**
• **XX** résultats analysés
• **XX%** de fiabilité globale
• **XX** entreprises vérifiées
• **XX** sources consultées
• **XX** alertes à traiter

**💡 INSIGHTS PRINCIPAUX**
1. [Insight le plus important]
2. [Second insight]
3. [Troisième insight]

**⚠️ RISQUES À CONSIDÉRER**
1. [Risque principal + impact]
2. [Risque secondaire]

**🎯 ACTIONS RECOMMANDÉES**
1. **[PRIORITÉ HAUTE]** : [Action immédiate]
2. **[PRIORITÉ MOYENNE]** : [Action à planifier]
3. **[OPTIONNEL]** : [Action si ressources disponibles]

**➡️ PROCHAINES ÉTAPES**
[Comment approfondir / sources complémentaires / contacts suggérés]

**📈 CONFIANCE GLOBALE : XX%**
[Verdict final en une phrase percutante]"""

    def __init__(self, llm: LLMProvider | None = None):
        super().__init__(llm)

    async def process(
        self,
        data: dict[str, Any],
        context: list[AgentMessage],
    ) -> AgentMessage:
        """Create comprehensive synthesis of all findings."""
        results = data.get("results", [])

        # Aggregate data from context
        all_issues = []
        all_evidence = []
        confidence_scores = []

        for msg in context:
            all_issues.extend(msg.issues)
            all_evidence.extend(msg.evidence)
            if msg.confidence > 0:
                confidence_scores.append(msg.confidence)

        # Remove duplicates while preserving order
        unique_issues = list(dict.fromkeys(all_issues))

        # Calculate synthesis confidence
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            # Penalize for issues
            confidence = max(0, avg_confidence - len(unique_issues) * 3)
        else:
            confidence = 0

        # Build synthesis content
        synthesis_parts = ["## Synthèse de l'Analyse\n"]

        # Key metrics
        synthesis_parts.append(f"**Résultats analysés:** {len(results)}")
        synthesis_parts.append(f"**Agents consultés:** {len(context)}")
        synthesis_parts.append(
            f"**Confiance moyenne:** {int(avg_confidence) if confidence_scores else 0}%"
        )

        # Key findings
        if all_evidence:
            synthesis_parts.append("\n### Principaux résultats")
            sources_with_results = set()
            for ev in all_evidence:
                if ev.get("source") and ev.get("count", 0) > 0:
                    sources_with_results.add(ev["source"])
            if sources_with_results:
                synthesis_parts.append(
                    f"Sources actives: {', '.join(sorted(sources_with_results))}"
                )

        # Issues summary
        if unique_issues:
            synthesis_parts.append("\n### Points d'attention")
            for issue in unique_issues[:5]:
                synthesis_parts.append(f"• {issue}")

        # Recommendations
        synthesis_parts.append("\n### Recommandations")
        if confidence >= 80:
            synthesis_parts.append("✅ Données fiables - Prêtes pour utilisation")
        elif confidence >= 60:
            synthesis_parts.append("⚡ Vérifier les points d'attention avant utilisation")
        elif confidence >= 40:
            synthesis_parts.append("⚠️ Enrichir avec des sources officielles (SIRENE, BODACC)")
        else:
            synthesis_parts.append("❌ Données insuffisantes - Nouvelle recherche recommandée")

        content = "\n".join(synthesis_parts)

        # Use LLM for enhanced synthesis if available
        if self.has_llm and context:
            agents_summary = "\n".join(
                f"**{m.agent}** (confiance: {m.confidence}%): {m.content[:300]}" for m in context
            )
            llm_prompt = f"""Synthèse finale de l'analyse multi-agents:

Résultats analysés: {len(results)}
Agents consultés: {len(context)}
Confiance moyenne: {int(avg_confidence) if confidence_scores else 0}%

Contributions des agents:
{agents_summary}

Problèmes identifiés:
{chr(10).join(f"- {i}" for i in unique_issues[:5]) if unique_issues else "- Aucun"}

Fournis:
1. Une synthèse exécutive en 3-5 points clés
2. Les décisions à prendre
3. Les prochaines étapes recommandées"""

            llm_response = await self._generate_with_llm(llm_prompt, self.SYSTEM_PROMPT)
            if llm_response:
                content = f"{content}\n\n### Synthèse LLM:\n{llm_response}"

        logger.debug(f"Synthesis: final_confidence={confidence}")

        return AgentMessage(
            agent=self.name,
            role=self.role,
            content=content,
            confidence=confidence,
            issues=unique_issues,
            metadata={
                "total_results": len(results),
                "agents_consulted": len(context),
                "issues_count": len(unique_issues),
            },
        )
