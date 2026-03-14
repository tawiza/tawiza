"""MCP Tools for Automated Prospection.

Provides lead scoring, contact enrichment, and personalized message
generation for sales prospection.
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP


@dataclass
class Lead:
    """A scored and enriched lead."""

    siret: str
    nom: str
    score: int  # 0-100
    tier: str  # "A", "B", "C", "D"
    commune: str = ""
    effectif: str = ""
    activite: str = ""
    adresse: str = ""
    # Enrichment
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    description: str | None = None
    # Scoring details
    score_details: dict = field(default_factory=dict)
    # Prospection
    message: str | None = None
    contacted: bool = False

    def to_dict(self) -> dict:
        return {
            "siret": self.siret,
            "nom": self.nom,
            "score": self.score,
            "tier": self.tier,
            "commune": self.commune,
            "effectif": self.effectif,
            "activite": self.activite,
            "adresse": self.adresse,
            "website": self.website,
            "email": self.email,
            "phone": self.phone,
            "linkedin": self.linkedin,
            "description": self.description,
            "score_details": self.score_details,
            "message": self.message,
            "contacted": self.contacted,
        }


# Scoring weights
SCORING_WEIGHTS = {
    "effectif": 30,  # Company size
    "recent_creation": 15,  # Created in last 3 years
    "sector_match": 25,  # Matches target sectors
    "location": 15,  # In target location
    "web_presence": 15,  # Has website/digital presence
}

TARGET_SECTORS = [
    "62",  # Programmation, conseil informatique
    "63",  # Services d'information
    "70",  # Conseil de gestion
    "71",  # Architecture, ingénierie
    "72",  # R&D scientifique
    "73",  # Publicité, études de marché
    "74",  # Autres activités spécialisées
]


async def check_financial_health(siren: str) -> dict:
    """
    Check financial health of a company using BODACC data.

    Evaluates:
    - Collective procedures (bankruptcy, liquidation) = RED FLAG
    - Recent capital changes = indicator of activity
    - Company stability (no adverse events)

    Args:
        siren: Company SIREN number (9 digits)

    Returns:
        dict with score (0-15), detail, and risk_level
    """
    from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter

    result = {
        "score": 10,  # Default: neutral score
        "max": 15,
        "detail": "Pas de signaux négatifs détectés",
        "risk_level": "low",
        "events": [],
    }

    try:
        adapter = BodaccAdapter()

        # Check for collective procedures (bankruptcy, liquidation)
        procedures = await adapter.search(
            {
                "siren": siren,
                "type": "procedure",
                "limit": 5,
            }
        )

        if procedures:
            # RED FLAG: Company has collective procedures
            recent_procedure = procedures[0]
            result["score"] = 0
            result["detail"] = (
                f"⚠️ Procédure collective détectée: {recent_procedure.get('type_label', 'procédure')}"
            )
            result["risk_level"] = "critical"
            result["events"] = [
                {
                    "type": p.get("type"),
                    "date": p.get("date_publication"),
                    "detail": p.get("contenu", "")[:100] if p.get("contenu") else None,
                }
                for p in procedures[:3]
            ]
            return result

        # Check for recent modifications (capital changes, etc.)
        modifications = await adapter.search(
            {
                "siren": siren,
                "type": "modification",
                "limit": 5,
            }
        )

        # Check for radiation (closure)
        radiations = await adapter.search(
            {
                "siren": siren,
                "type": "radiation",
                "limit": 1,
            }
        )

        if radiations:
            result["score"] = 0
            result["detail"] = "❌ Entreprise radiée (fermée)"
            result["risk_level"] = "critical"
            return result

        # Score based on activity and stability
        if modifications:
            # Has recent activity - could be positive or neutral
            mod_count = len(modifications)
            if mod_count >= 3:
                # Lots of changes - monitor
                result["score"] = 8
                result["detail"] = f"📋 {mod_count} modifications récentes (activité normale)"
                result["risk_level"] = "medium"
            else:
                # Some activity - good sign
                result["score"] = 12
                result["detail"] = f"✅ Entreprise active ({mod_count} modification(s) récente(s))"
                result["risk_level"] = "low"
            result["events"] = [
                {
                    "type": m.get("type"),
                    "date": m.get("date_publication"),
                }
                for m in modifications[:3]
            ]
        else:
            # No recent events - stable but check if company exists
            # Check for creation to confirm company exists
            creations = await adapter.search(
                {
                    "siren": siren,
                    "type": "creation",
                    "limit": 1,
                }
            )

            if creations:
                result["score"] = 15
                result["detail"] = "✅ Entreprise stable, aucun événement négatif"
                result["risk_level"] = "low"
            else:
                # No BODACC data at all - could be very new or data not available
                result["score"] = 10
                result["detail"] = "ℹ️ Pas de données BODACC disponibles"
                result["risk_level"] = "unknown"

    except Exception as e:
        logger.warning(f"Financial health check failed for {siren}: {e}")
        result["score"] = 10
        result["detail"] = "⚠️ Vérification impossible (erreur API)"
        result["risk_level"] = "unknown"

    return result


MESSAGE_PROMPT = """Tu es un expert en prospection B2B. Genere un message de prospection personnalise pour cette entreprise.

**Entreprise cible:**
- Nom: {nom}
- Secteur: {activite}
- Effectif: {effectif}
- Localisation: {commune}
- Description: {description}

**Contexte:**
- Offre: {offre}
- Ton: {ton}

**Contraintes:**
- Maximum 150 mots
- Personnalise avec le nom de l'entreprise
- Accroche pertinente basee sur leur secteur
- Call-to-action clair
- Pas de formules generiques ("Cher Monsieur/Madame")

**Reponds uniquement avec le message, sans guillemets ni formatage.**
"""


def register_prospection_tools(mcp: FastMCP) -> None:
    """Register prospection tools on the MCP server."""

    @mcp.tool()
    async def tawiza_prospect(
        query: str,
        territory: str,
        limit: int = 50,
        min_tier: Literal["A", "B", "C", "D"] = "B",
        enrich: bool = True,
        generate_messages: bool = False,
        offre: str = "solutions d'intelligence territoriale",
        ctx: Context = None,
    ) -> str:
        """Genere une liste de leads scores et enrichis pour prospection.

        Pipeline complet:
        1. Recherche entreprises correspondantes
        2. Scoring multicritere (effectif, secteur, localisation, web)
        3. Enrichissement contacts (website, email, telephone)
        4. Generation de messages personnalises (optionnel)

        Args:
            query: Type d'entreprise recherche (ex: "startup tech", "cabinet conseil")
            territory: Territoire cible (ex: "Lille", "Hauts-de-France")
            limit: Nombre max de leads
            min_tier: Tier minimum (A=top 25%, B=25-50%, C=50-75%, D=bottom 25%)
            enrich: Enrichir les contacts (plus lent mais plus complet)
            generate_messages: Generer des messages personnalises (plus lent)
            offre: Description de votre offre pour les messages

        Returns:
            JSON avec leads scores, enrichis et messages
        """
        from src.infrastructure.agents.camel.tools.territorial_tools import sirene_search

        def notify(msg: str, progress: int = None):
            if ctx:
                try:
                    ctx.info(msg)
                    if progress is not None:
                        ctx.report_progress(progress, 100, msg)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        notify(f"Prospection: {query} sur {territory}", 0)
        start_time = datetime.now()

        # Step 1: Search enterprises
        notify("[1/4] Recherche entreprises...", 10)

        full_query = f"{query} {territory}"
        try:
            result = sirene_search(query=full_query, limite=limit * 2)  # Get more to filter
            enterprises = result.get("enterprises", []) if result.get("success") else []
        except Exception as e:
            logger.error(f"Sirene search failed: {e}")
            enterprises = []

        if not enterprises:
            # Fallback to orchestrator
            from src.application.orchestration.data_orchestrator import DataOrchestrator

            orchestrator = DataOrchestrator()
            orch_result = await orchestrator.search(query=full_query, limit_per_source=limit * 2)
            for sr in orch_result.source_results:
                enterprises.extend(sr.results)

        notify(f"[1/4] {len(enterprises)} entreprises trouvees", 20)

        if not enterprises:
            return json.dumps(
                {
                    "success": False,
                    "error": "Aucune entreprise trouvee",
                },
                ensure_ascii=False,
            )

        # Step 2: Score leads
        notify("[2/4] Scoring des leads...", 30)

        leads = []
        current_year = datetime.now().year

        for ent in enterprises:
            score_details = {}
            total_score = 0

            # Effectif scoring (0-30 points)
            effectif = ent.get("effectif", ent.get("trancheEffectifs", ""))
            try:
                eff_val = int(str(effectif).split("-")[0].replace("+", "")) if effectif else 0
            except (ValueError, TypeError):
                eff_val = 0

            if eff_val >= 50:
                eff_score = 30
            elif eff_val >= 20:
                eff_score = 25
            elif eff_val >= 10:
                eff_score = 20
            elif eff_val >= 5:
                eff_score = 15
            else:
                eff_score = 5
            score_details["effectif"] = eff_score
            total_score += eff_score

            # Recent creation (0-15 points)
            creation = ent.get("dateCreation", "")
            try:
                year = int(str(creation)[:4]) if creation else 0
                if current_year - year <= 2:
                    creation_score = 15
                elif current_year - year <= 5:
                    creation_score = 10
                else:
                    creation_score = 5
            except (ValueError, TypeError):
                creation_score = 5
            score_details["recent_creation"] = creation_score
            total_score += creation_score

            # Sector match (0-25 points)
            naf = ent.get("naf", ent.get("activite", ""))
            naf_prefix = str(naf)[:2] if naf else ""
            if naf_prefix in TARGET_SECTORS:
                sector_score = 25
            elif naf_prefix in ["58", "59", "60", "61"]:  # Media, telecom
                sector_score = 15
            else:
                sector_score = 5
            score_details["sector_match"] = sector_score
            total_score += sector_score

            # Location (0-15 points)
            commune = ent.get("commune", ent.get("city", ""))
            location_score = 15 if territory.lower() in str(commune).lower() else 8
            score_details["location"] = location_score
            total_score += location_score

            # Web presence placeholder (will be updated during enrichment)
            score_details["web_presence"] = 0

            # Determine tier
            if total_score >= 70:
                tier = "A"
            elif total_score >= 50:
                tier = "B"
            elif total_score >= 30:
                tier = "C"
            else:
                tier = "D"

            lead = Lead(
                siret=ent.get("siret", ""),
                nom=ent.get("nom") or ent.get("name", "N/A"),
                score=total_score,
                tier=tier,
                commune=commune,
                effectif=str(effectif) if effectif else "",
                activite=naf,
                adresse=ent.get("adresse", ""),
                score_details=score_details,
            )
            leads.append(lead)

        # Sort by score and filter by tier
        leads.sort(key=lambda x: x.score, reverse=True)
        tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
        min_tier_idx = tier_order.get(min_tier, 1)
        leads = [l for l in leads if tier_order.get(l.tier, 3) <= min_tier_idx]
        leads = leads[:limit]

        notify(f"[2/4] {len(leads)} leads qualifies (tier >= {min_tier})", 40)

        # Step 3: Enrich contacts
        if enrich and leads:
            notify("[3/4] Enrichissement contacts...", 50)

            from src.infrastructure.mcp.tools.web_search import web_search_impl

            enriched_count = 0
            for i, lead in enumerate(leads[:20]):  # Limit enrichment to top 20
                try:
                    # Search for company website
                    search_query = f"{lead.nom} {lead.commune} site officiel"
                    search_results = await web_search_impl(search_query, max_results=3)

                    if search_results:
                        # Extract website from first result
                        first_result = (
                            search_results[0] if isinstance(search_results, list) else None
                        )
                        if first_result:
                            lead.website = first_result.get("url", first_result.get("link"))
                            lead.description = first_result.get(
                                "snippet", first_result.get("description", "")
                            )[:200]

                            # Update web presence score
                            lead.score_details["web_presence"] = 15
                            lead.score += 15
                            enriched_count += 1

                            # Update tier based on new score
                            if lead.score >= 85:
                                lead.tier = "A"
                            elif lead.score >= 65:
                                lead.tier = "B"

                except Exception as e:
                    logger.debug(f"Enrichment failed for {lead.nom}: {e}")

                if i % 5 == 0:
                    progress = 50 + (30 * i / min(20, len(leads)))
                    notify(f"[3/4] Enrichi {i + 1}/{min(20, len(leads))}...", int(progress))

            notify(f"[3/4] {enriched_count} leads enrichis", 80)
        else:
            notify("[3/4] Enrichissement desactive", 80)

        # Step 4: Generate messages (optional)
        if generate_messages and leads:
            notify("[4/4] Generation messages...", 85)

            try:
                from src.infrastructure.llm import OllamaClient

                client = OllamaClient(model="qwen3.5:27b")

                for lead in leads[:10]:  # Limit to top 10
                    prompt = MESSAGE_PROMPT.format(
                        nom=lead.nom,
                        activite=lead.activite or "Non specifie",
                        effectif=lead.effectif or "Non specifie",
                        commune=lead.commune or "Non specifie",
                        description=lead.description or "Entreprise du secteur",
                        offre=offre,
                        ton="professionnel mais accessible",
                    )

                    response = await client.generate(prompt=prompt, max_tokens=250)
                    lead.message = response.strip()

                notify(f"[4/4] {min(10, len(leads))} messages generes", 95)

            except Exception as e:
                logger.error(f"Message generation failed: {e}")
                notify(f"[4/4] Erreur generation messages: {str(e)[:30]}", 95)
        else:
            notify("[4/4] Generation messages desactivee", 95)

        # Build result
        duration = (datetime.now() - start_time).total_seconds()

        # Statistics
        tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        for lead in leads:
            tier_counts[lead.tier] = tier_counts.get(lead.tier, 0) + 1

        result = {
            "success": True,
            "query": query,
            "territory": territory,
            "leads": [l.to_dict() for l in leads],
            "stats": {
                "total_leads": len(leads),
                "by_tier": tier_counts,
                "avg_score": round(sum(l.score for l in leads) / len(leads), 1) if leads else 0,
                "enriched": sum(1 for l in leads if l.website),
                "with_messages": sum(1 for l in leads if l.message),
            },
            "duration_seconds": duration,
        }

        notify(f"Prospection terminee: {len(leads)} leads ({duration:.1f}s)", 100)

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def tawiza_prospect_export(
        leads_json: str,
        format: Literal["csv", "json", "hubspot"] = "csv",
        ctx: Context = None,
    ) -> str:
        """Exporte les leads au format CRM.

        Args:
            leads_json: JSON des leads (resultat de tawiza_prospect)
            format: Format d'export
                - csv: Format CSV standard
                - json: Format JSON structure
                - hubspot: Format compatible HubSpot import

        Returns:
            Chemin du fichier exporte
        """
        try:
            data = json.loads(leads_json)
            leads = data.get("leads", [])
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "success": False,
                    "error": "JSON invalide",
                },
                ensure_ascii=False,
            )

        if not leads:
            return json.dumps(
                {
                    "success": False,
                    "error": "Aucun lead a exporter",
                },
                ensure_ascii=False,
            )

        # Create export directory
        export_dir = Path.home() / ".tawiza" / "exports" / "prospects"
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "csv":
            filename = f"leads_{timestamp}.csv"
            filepath = export_dir / filename

            fieldnames = [
                "nom",
                "siret",
                "score",
                "tier",
                "commune",
                "effectif",
                "activite",
                "website",
                "email",
                "phone",
                "message",
            ]

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for lead in leads:
                    writer.writerow(lead)

        elif format == "hubspot":
            filename = f"hubspot_leads_{timestamp}.csv"
            filepath = export_dir / filename

            # HubSpot format mapping
            fieldnames = [
                "Company name",
                "Company Domain Name",
                "Phone Number",
                "City",
                "Industry",
                "Number of Employees",
                "Description",
            ]

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for lead in leads:
                    writer.writerow(
                        {
                            "Company name": lead.get("nom"),
                            "Company Domain Name": lead.get("website", ""),
                            "Phone Number": lead.get("phone", ""),
                            "City": lead.get("commune"),
                            "Industry": lead.get("activite"),
                            "Number of Employees": lead.get("effectif"),
                            "Description": lead.get("description", ""),
                        }
                    )

        else:  # json
            filename = f"leads_{timestamp}.json"
            filepath = export_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(leads, f, ensure_ascii=False, indent=2)

        if ctx:
            ctx.info(f"[Export] {len(leads)} leads exportes vers {filepath}")

        return json.dumps(
            {
                "success": True,
                "format": format,
                "path": str(filepath),
                "filename": filename,
                "leads_count": len(leads),
            },
            ensure_ascii=False,
        )

    @mcp.tool()
    async def tawiza_generate_message(
        entreprise: str,
        secteur: str,
        offre: str,
        ton: Literal["formel", "decontracte", "expert"] = "expert",
        ctx: Context = None,
    ) -> str:
        """Genere un message de prospection personnalise.

        Args:
            entreprise: Nom de l'entreprise cible
            secteur: Secteur d'activite
            offre: Votre offre/proposition de valeur
            ton: Ton du message (formel, decontracte, expert)

        Returns:
            Message de prospection personnalise
        """
        try:
            from src.infrastructure.llm import OllamaClient

            client = OllamaClient(model="qwen3.5:27b")

            ton_desc = {
                "formel": "tres professionnel et corporate",
                "decontracte": "amical et accessible, tutoiement possible",
                "expert": "professionnel mais accessible, montrant expertise",
            }

            prompt = f"""Genere un message de prospection B2B.

Entreprise cible: {entreprise}
Secteur: {secteur}
Offre: {offre}
Ton: {ton_desc.get(ton, ton_desc["expert"])}

Contraintes:
- 100-150 mots maximum
- Accroche personnalisee
- Proposition de valeur claire
- Call-to-action
- Pas de "Cher Monsieur/Madame"

Message:"""

            response = await client.generate(prompt=prompt, max_tokens=300)

            if ctx:
                ctx.info(f"[Message] Genere pour {entreprise}")

            return json.dumps(
                {
                    "success": True,
                    "entreprise": entreprise,
                    "message": response.strip(),
                    "ton": ton,
                },
                ensure_ascii=False,
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                },
                ensure_ascii=False,
            )

    @mcp.tool()
    async def tawiza_lead_score(
        siret: str,
        ctx: Context = None,
    ) -> str:
        """Calcule le score detaille d'un lead specifique.

        Args:
            siret: SIRET de l'entreprise a scorer

        Returns:
            Score detaille avec recommandations
        """
        from src.infrastructure.agents.camel.tools.territorial_tools import sirene_get

        if ctx:
            ctx.info(f"[Scoring] Analyse SIRET {siret}...")

        try:
            result = sirene_get(siret=siret)
            if not result.get("success"):
                return json.dumps(
                    {
                        "success": False,
                        "error": "Entreprise non trouvee",
                    },
                    ensure_ascii=False,
                )

            ent = result.get("enterprise", result)

            # Detailed scoring
            scores = {
                "taille": {"score": 0, "max": 25, "detail": ""},
                "anciennete": {"score": 0, "max": 15, "detail": ""},
                "secteur": {"score": 0, "max": 25, "detail": ""},
                "localisation": {"score": 0, "max": 20, "detail": ""},
                "sante_financiere": {"score": 0, "max": 15, "detail": ""},
            }

            # Taille
            effectif = ent.get("effectif", ent.get("trancheEffectifs", ""))
            try:
                eff_val = int(str(effectif).split("-")[0].replace("+", "")) if effectif else 0
            except Exception as e:
                logger.debug(f"Failed to parse effectif '{effectif}': {e}")
                eff_val = 0

            if eff_val >= 50:
                scores["taille"]["score"] = 25
                scores["taille"]["detail"] = f"Grande entreprise ({eff_val}+ salaries)"
            elif eff_val >= 10:
                scores["taille"]["score"] = 20
                scores["taille"]["detail"] = f"PME ({eff_val} salaries)"
            else:
                scores["taille"]["score"] = 10
                scores["taille"]["detail"] = f"TPE ({eff_val} salaries)"

            # Anciennete
            creation = ent.get("dateCreation", "")
            current_year = datetime.now().year
            try:
                year = int(str(creation)[:4]) if creation else 0
                age = current_year - year
                if 2 <= age <= 5:
                    scores["anciennete"]["score"] = 15
                    scores["anciennete"]["detail"] = f"Scale-up ({age} ans)"
                elif age < 2:
                    scores["anciennete"]["score"] = 12
                    scores["anciennete"]["detail"] = f"Startup ({age} ans)"
                else:
                    scores["anciennete"]["score"] = 8
                    scores["anciennete"]["detail"] = f"Entreprise etablie ({age} ans)"
            except Exception as e:
                logger.debug(f"Failed to parse creation date '{creation}': {e}")
                scores["anciennete"]["score"] = 5
                scores["anciennete"]["detail"] = "Age inconnu"

            # Secteur
            naf = ent.get("naf", ent.get("activite", ""))[:2]
            if naf in ["62", "63"]:
                scores["secteur"]["score"] = 25
                scores["secteur"]["detail"] = "Secteur tech (cible principale)"
            elif naf in ["70", "71", "72", "73"]:
                scores["secteur"]["score"] = 20
                scores["secteur"]["detail"] = "Services aux entreprises"
            else:
                scores["secteur"]["score"] = 10
                scores["secteur"]["detail"] = f"Autre secteur ({naf})"

            # Localisation
            commune = ent.get("commune", "")
            if commune:
                scores["localisation"]["score"] = 15
                scores["localisation"]["detail"] = f"Localise a {commune}"
            else:
                scores["localisation"]["score"] = 5
                scores["localisation"]["detail"] = "Localisation inconnue"

            # Sante financiere (via BODACC)
            siren_for_check = siret[:9] if len(siret) >= 9 else None
            if siren_for_check:
                if ctx:
                    ctx.info(f"[Scoring] Vérification santé financière SIREN {siren_for_check}...")
                financial_health = await check_financial_health(siren_for_check)
                scores["sante_financiere"]["score"] = financial_health["score"]
                scores["sante_financiere"]["detail"] = financial_health["detail"]
                # Add risk level and events to response
                scores["sante_financiere"]["risk_level"] = financial_health.get(
                    "risk_level", "unknown"
                )
                if financial_health.get("events"):
                    scores["sante_financiere"]["events"] = financial_health["events"]
            else:
                scores["sante_financiere"]["score"] = 10
                scores["sante_financiere"]["detail"] = "SIRET non disponible pour vérification"

            total_score = sum(s["score"] for s in scores.values())
            max_score = sum(s["max"] for s in scores.values())

            if total_score >= 80:
                tier = "A"
                recommendation = "Lead premium - contacter en priorite"
            elif total_score >= 60:
                tier = "B"
                recommendation = "Bon lead - inclure dans campagne principale"
            elif total_score >= 40:
                tier = "C"
                recommendation = "Lead moyen - campagne secondaire"
            else:
                tier = "D"
                recommendation = "Lead faible - nurturing long terme"

            return json.dumps(
                {
                    "success": True,
                    "siret": siret,
                    "nom": ent.get("nom", ent.get("name", "N/A")),
                    "score": total_score,
                    "max_score": max_score,
                    "percentage": round(total_score / max_score * 100),
                    "tier": tier,
                    "scores_detail": scores,
                    "recommendation": recommendation,
                },
                ensure_ascii=False,
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                },
                ensure_ascii=False,
            )

    @mcp.tool()
    async def tawiza_financial_health(
        siret: str,
        ctx: Context = None,
    ) -> str:
        """Vérifie la santé financière d'une entreprise via BODACC.

        Analyse les annonces légales pour détecter:
        - Procédures collectives (redressement, liquidation)
        - Radiations (fermeture)
        - Modifications récentes (augmentation capital, etc.)

        Args:
            siret: SIRET de l'entreprise (14 chiffres) ou SIREN (9 chiffres)

        Returns:
            JSON avec score santé financière, niveau de risque, événements détectés
        """
        siren = siret[:9] if len(siret) >= 9 else siret

        if ctx:
            ctx.info(f"[Santé Financière] Analyse SIREN {siren}...")

        try:
            result = await check_financial_health(siren)

            # Enrich with company name if possible
            from src.infrastructure.agents.camel.tools.territorial_tools import sirene_get

            try:
                company_data = sirene_get(siret=siret)
                if company_data.get("success"):
                    ent = company_data.get("enterprise", company_data)
                    result["nom"] = ent.get("nom") or ent.get("name", "N/A")
            except Exception:
                pass

            result["success"] = True
            result["siret"] = siret
            result["siren"] = siren

            # Recommendation based on risk level
            risk_recommendations = {
                "low": "✅ Entreprise fiable pour prospection",
                "medium": "⚠️ Surveiller - activité récente importante",
                "critical": "❌ À exclure - risque financier élevé",
                "unknown": "ℹ️ Données insuffisantes - vérification manuelle recommandée",
            }
            result["recommendation"] = risk_recommendations.get(
                result.get("risk_level", "unknown"), risk_recommendations["unknown"]
            )

            if ctx:
                ctx.info(f"[Santé Financière] Score: {result['score']}/15 - {result['risk_level']}")

            return json.dumps(result, ensure_ascii=False, indent=2, default=str)

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "siret": siret,
                    "error": str(e),
                },
                ensure_ascii=False,
            )
