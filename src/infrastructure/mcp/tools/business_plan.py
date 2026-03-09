"""MCP Tools for Business Plan Generation.

Generates professional business plans based on territorial market analysis.
Uses LLM to create structured, sector-specific business plans.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP

# Business Plan Templates by sector
BP_TEMPLATES = {
    "tech": {
        "name": "Startup Tech / SaaS",
        "sections": [
            "executive_summary",
            "problem_solution",
            "market_analysis",
            "business_model",
            "go_to_market",
            "tech_stack",
            "team",
            "financials",
            "roadmap",
            "funding_ask",
        ],
        "focus": ["scalabilité", "MRR/ARR", "TAM/SAM/SOM", "churn", "CAC/LTV"],
    },
    "industrie": {
        "name": "Entreprise Industrielle",
        "sections": [
            "executive_summary",
            "presentation",
            "market_analysis",
            "production",
            "commercial",
            "organisation",
            "financials",
            "investissements",
            "risques",
        ],
        "focus": ["capacité production", "supply chain", "certifications", "BFR"],
    },
    "services": {
        "name": "Société de Services",
        "sections": [
            "executive_summary",
            "offre_services",
            "market_analysis",
            "positionnement",
            "commercial",
            "organisation",
            "financials",
            "developpement",
        ],
        "focus": ["TJM", "taux occupation", "fidélisation", "références"],
    },
    "commerce": {
        "name": "Commerce / Retail",
        "sections": [
            "executive_summary",
            "concept",
            "market_analysis",
            "emplacement",
            "offre_produits",
            "commercial",
            "financials",
            "operations",
        ],
        "focus": ["panier moyen", "fréquentation", "marge", "stock"],
    },
    "generic": {
        "name": "Business Plan Générique",
        "sections": [
            "executive_summary",
            "presentation",
            "market_analysis",
            "strategie",
            "organisation",
            "financials",
            "annexes",
        ],
        "focus": ["différenciation", "avantages concurrentiels", "croissance"],
    },
}


SECTION_PROMPTS = {
    "executive_summary": """Rédige un Executive Summary professionnel pour ce business plan.

**Contexte entreprise**: {company_context}
**Marché cible**: {market_context}
**Secteur**: {sector}

L'executive summary doit inclure:
- Vision et mission (2-3 phrases)
- Problème résolu et solution proposée
- Marché cible et opportunité
- Modèle économique en 1 phrase
- Équipe clé (si fournie)
- Besoins de financement (si applicable)
- Objectifs à 3 ans

Format: Markdown structuré, 300-400 mots, ton professionnel.""",

    "market_analysis": """Rédige l'analyse de marché pour ce business plan.

**Données marché collectées**:
{market_data}

**Territoire**: {territory}
**Secteur**: {sector}

L'analyse doit inclure:
- Taille du marché (TAM/SAM/SOM si tech)
- Tendances principales
- Analyse concurrentielle (forces/faiblesses)
- Segmentation clients
- Barrières à l'entrée
- Opportunités identifiées

Format: Markdown avec tableaux et bullet points, 400-500 mots.""",

    "business_model": """Rédige la section Modèle Économique.

**Contexte**: {company_context}
**Secteur**: {sector}
**Focus secteur**: {sector_focus}

Détaille:
- Sources de revenus
- Structure de prix
- Canaux de distribution
- Partenaires clés
- Ressources clés
- Structure de coûts
- Métriques clés ({sector_focus})

Format: Markdown, inclure un canvas simplifié si pertinent.""",

    "financials": """Rédige les projections financières.

**Contexte**: {company_context}
**Données marché**: {market_data}
**Secteur**: {sector}

Inclure:
- Hypothèses clés
- Compte de résultat prévisionnel (3 ans)
- Plan de trésorerie simplifié
- Point mort / Break-even
- Besoins de financement
- Indicateurs clés: {sector_focus}

Format: Markdown avec tableaux pour les chiffres.""",

    "go_to_market": """Rédige la stratégie Go-to-Market.

**Contexte**: {company_context}
**Marché**: {market_context}
**Territoire**: {territory}

Détaille:
- Cibles prioritaires
- Canaux d'acquisition
- Stratégie de lancement
- Partenariats stratégiques
- KPIs de lancement
- Timeline

Format: Markdown structuré.""",

    "team": """Rédige la section Équipe.

**Contexte**: {company_context}

Inclure:
- Équipe fondatrice (profils types si non fournis)
- Compétences clés
- Organisation cible
- Recrutements prioritaires
- Advisors / mentors

Format: Markdown.""",

    "roadmap": """Rédige la Roadmap produit/développement.

**Contexte**: {company_context}
**Secteur**: {sector}

Détaille:
- Phase 1: MVP / Lancement (0-6 mois)
- Phase 2: Croissance (6-18 mois)
- Phase 3: Scale (18-36 mois)
- Jalons clés
- Métriques de succès

Format: Markdown avec timeline.""",
}


BP_GENERATION_PROMPT = """Tu es un expert en rédaction de business plans professionnels.

{section_prompt}

IMPORTANT:
- Ton professionnel et convaincant
- Données chiffrées quand possible
- Structure claire avec titres
- Pas de phrases vides ou génériques
- Adapté au contexte français

Réponds directement en Markdown formaté."""


def register_business_plan_tools(mcp: FastMCP) -> None:
    """Register business plan tools on the MCP server."""

    @mcp.tool()
    async def tawiza_generate_bp(
        company_name: str,
        company_description: str,
        territory: str,
        sector: str = "tech",
        market_data: str | None = None,
        funding_ask: str | None = None,
        team_info: str | None = None,
        output_dir: str = "./outputs/business_plans",
        ctx: Context = None,
    ) -> str:
        """Génère un business plan professionnel basé sur l'analyse de marché.

        Utilise les données territoriales collectées pour créer un BP
        structuré et adapté au secteur.

        Args:
            company_name: Nom de l'entreprise/projet
            company_description: Description de l'activité et de la proposition de valeur
            territory: Territoire cible (ex: "Lille", "Hauts-de-France")
            sector: Type de business plan:
                - tech: Startup Tech / SaaS
                - industrie: Entreprise Industrielle
                - services: Société de Services
                - commerce: Commerce / Retail
                - generic: Business Plan Générique
            market_data: Données de marché (JSON ou texte) - optionnel, peut être
                        récupéré automatiquement via tawiza_workforce_analyze
            funding_ask: Montant et utilisation du financement recherché
            team_info: Informations sur l'équipe fondatrice
            output_dir: Répertoire de sortie pour le BP

        Returns:
            Business plan complet en Markdown + métadonnées
        """
        def notify(msg: str, progress: int = None):
            if ctx:
                try:
                    ctx.info(msg)
                    if progress is not None:
                        ctx.report_progress(progress, 100, msg)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        notify(f"[BP] Génération pour {company_name}", 0)

        # Validate sector
        if sector not in BP_TEMPLATES:
            return json.dumps({
                "success": False,
                "error": f"Secteur inconnu: {sector}. Disponibles: {list(BP_TEMPLATES.keys())}",
            }, ensure_ascii=False)

        template = BP_TEMPLATES[sector]
        notify(f"[BP] Template: {template['name']}", 5)

        # Build company context
        company_context = f"""
Entreprise: {company_name}
Description: {company_description}
Territoire: {territory}
Secteur: {template['name']}
"""
        if funding_ask:
            company_context += f"Financement recherché: {funding_ask}\n"
        if team_info:
            company_context += f"Équipe: {team_info}\n"

        # Get market data if not provided
        market_context = market_data or ""
        if not market_data:
            notify("[BP] Récupération données marché...", 10)
            try:
                from src.infrastructure.agents.camel.tools.territorial_tools import sirene_search
                result = sirene_search(query=f"{sector} {territory}", limite=30)
                if result.get("success"):
                    enterprises = result.get("enterprises", [])
                    market_context = f"""
Entreprises similaires sur {territory}: {len(enterprises)}
Secteurs NAF présents: {', '.join({e.get('naf', '')[:2] for e in enterprises[:20] if e.get('naf')})}
Effectif total estimé: {sum(e.get('effectif', 0) for e in enterprises if isinstance(e.get('effectif'), int))}
"""
            except Exception as e:
                logger.warning(f"Could not fetch market data: {e}")
                market_context = f"Territoire: {territory}, Secteur: {sector}"

        notify("[BP] Contexte marché préparé", 15)

        # Generate each section with LLM
        sections_content = {}
        sections_to_generate = template["sections"]

        try:
            from src.infrastructure.llm import OllamaClient
            client = OllamaClient(model="qwen3.5:27b")

            for i, section_name in enumerate(sections_to_generate):
                progress = 20 + int((i / len(sections_to_generate)) * 60)
                notify(f"[BP] Génération: {section_name}", progress)

                # Get section prompt or use generic
                if section_name in SECTION_PROMPTS:
                    section_prompt = SECTION_PROMPTS[section_name].format(
                        company_context=company_context,
                        market_context=market_context,
                        market_data=market_context,
                        territory=territory,
                        sector=template["name"],
                        sector_focus=", ".join(template["focus"]),
                    )
                else:
                    # Generic section prompt
                    section_prompt = f"""Rédige la section "{section_name}" pour un business plan.

Contexte: {company_context}
Marché: {market_context}
Focus: {', '.join(template['focus'])}

Format: Markdown professionnel, 200-300 mots."""

                prompt = BP_GENERATION_PROMPT.format(section_prompt=section_prompt)

                try:
                    response = await client.generate(prompt=prompt, max_tokens=600)
                    sections_content[section_name] = response.strip()
                except Exception as e:
                    logger.error(f"Failed to generate section {section_name}: {e}")
                    sections_content[section_name] = f"*Section à compléter: {section_name}*"

                # Small delay to avoid overwhelming Ollama
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to placeholder sections
            for section_name in sections_to_generate:
                sections_content[section_name] = f"*Section {section_name} à rédiger*"

        notify("[BP] Assemblage du document...", 85)

        # Assemble the business plan
        bp_md = f"""# Business Plan - {company_name}

**Document généré le {datetime.now().strftime('%d/%m/%Y')}**

**Secteur**: {template['name']}
**Territoire**: {territory}

---

## Table des matières

"""
        # TOC
        for i, section in enumerate(sections_to_generate, 1):
            section_title = section.replace("_", " ").title()
            bp_md += f"{i}. [{section_title}](#{section.replace('_', '-')})\n"

        bp_md += "\n---\n\n"

        # Sections
        for section_name in sections_to_generate:
            section_title = section_name.replace("_", " ").title()
            bp_md += f"## {section_title}\n\n"
            bp_md += sections_content.get(section_name, "*À compléter*")
            bp_md += "\n\n---\n\n"

        # Footer
        bp_md += f"""
## Annexes

### Métriques clés à suivre
{chr(10).join(f'- {m}' for m in template['focus'])}

### Sources de données
- Analyse territoriale Tawiza
- Base SIRENE (INSEE)
- Données sectorielles

---

*Business Plan généré par Tawiza - Intelligence Territoriale*
*{datetime.now().strftime('%d/%m/%Y %H:%M')}*
"""

        # Save to file
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = company_name.lower().replace(" ", "_")[:30]
        filename = f"bp_{safe_name}_{timestamp}.md"
        filepath = output_path / filename

        filepath.write_text(bp_md, encoding="utf-8")
        notify(f"[BP] Sauvegardé: {filepath}", 95)

        notify(f"[BP] Business Plan généré ({len(sections_to_generate)} sections)", 100)

        return json.dumps({
            "success": True,
            "company": company_name,
            "sector": template["name"],
            "territory": territory,
            "sections_count": len(sections_to_generate),
            "sections": list(sections_content.keys()),
            "output_file": str(filepath),
            "business_plan_md": bp_md,
            "metadata": {
                "template": sector,
                "focus_metrics": template["focus"],
                "generated_at": datetime.now().isoformat(),
            },
        }, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def tawiza_bp_templates(ctx: Context = None) -> str:
        """Liste les templates de business plan disponibles.

        Returns:
            Liste des templates avec leurs sections et focus
        """
        templates_list = []
        for key, tmpl in BP_TEMPLATES.items():
            templates_list.append({
                "id": key,
                "name": tmpl["name"],
                "sections": tmpl["sections"],
                "focus": tmpl["focus"],
                "sections_count": len(tmpl["sections"]),
            })

        return json.dumps({
            "success": True,
            "templates": templates_list,
            "usage": "tawiza_generate_bp(company_name='...', company_description='...', territory='...', sector='tech')",
        }, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def tawiza_bp_section(
        section: str,
        company_context: str,
        market_context: str = "",
        sector: str = "tech",
        ctx: Context = None,
    ) -> str:
        """Génère une section spécifique de business plan.

        Utile pour régénérer ou personnaliser une section particulière.

        Args:
            section: Nom de la section (executive_summary, market_analysis, etc.)
            company_context: Contexte de l'entreprise (description, équipe, etc.)
            market_context: Données de marché disponibles
            sector: Type de template (tech, industrie, services, commerce, generic)

        Returns:
            Section générée en Markdown
        """
        if ctx:
            ctx.info(f"[BP Section] Génération: {section}")

        if sector not in BP_TEMPLATES:
            return json.dumps({
                "success": False,
                "error": f"Secteur inconnu: {sector}",
            }, ensure_ascii=False)

        template = BP_TEMPLATES[sector]

        if section not in SECTION_PROMPTS:
            return json.dumps({
                "success": False,
                "error": f"Section inconnue: {section}. Disponibles: {list(SECTION_PROMPTS.keys())}",
            }, ensure_ascii=False)

        try:
            from src.infrastructure.llm import OllamaClient
            client = OllamaClient(model="qwen3.5:27b")

            section_prompt = SECTION_PROMPTS[section].format(
                company_context=company_context,
                market_context=market_context,
                market_data=market_context,
                territory="France",
                sector=template["name"],
                sector_focus=", ".join(template["focus"]),
            )

            prompt = BP_GENERATION_PROMPT.format(section_prompt=section_prompt)
            response = await client.generate(prompt=prompt, max_tokens=600)

            return json.dumps({
                "success": True,
                "section": section,
                "content": response.strip(),
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            }, ensure_ascii=False)

    @mcp.tool()
    async def tawiza_bp_from_analysis(
        analysis_dir: str,
        company_name: str,
        company_description: str,
        sector: str = "tech",
        funding_ask: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Génère un business plan à partir d'une analyse Tawiza existante.

        Charge les données d'une analyse workforce précédente et génère
        un business plan basé sur ces données réelles.

        Args:
            analysis_dir: Chemin vers le répertoire d'analyse (contient rapport.md, entreprises.csv)
            company_name: Nom de l'entreprise/projet
            company_description: Description de l'activité
            sector: Type de template
            funding_ask: Financement recherché

        Returns:
            Business plan basé sur l'analyse
        """
        if ctx:
            ctx.info(f"[BP] Chargement analyse: {analysis_dir}")

        analysis_path = Path(analysis_dir)

        # Load existing analysis data
        market_data = ""
        territory = "France"

        # Try to load rapport.md
        rapport_file = analysis_path / "rapport.md"
        if rapport_file.exists():
            rapport_content = rapport_file.read_text(encoding="utf-8")
            market_data += f"### Rapport d'analyse\n{rapport_content[:2000]}\n\n"
            # Extract territory from rapport if possible
            if "Territoire:" in rapport_content:
                try:
                    territory = rapport_content.split("Territoire:")[1].split("\n")[0].strip()
                except Exception as e:
                    logger.debug(f"Failed to extract territory from rapport: {e}")
                    pass

        # Try to load metadata.json
        metadata_file = analysis_path / "metadata.json"
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
                market_data += "### Métadonnées\n"
                market_data += f"- Entreprises analysées: {metadata.get('enterprises_count', 'N/A')}\n"
                market_data += f"- Requête: {metadata.get('query', 'N/A')}\n"
                if metadata.get("territory"):
                    territory = metadata["territory"]
            except Exception as e:
                logger.debug(f"Failed to load metadata: {e}")
                pass

        # Try to load entreprises.csv summary
        csv_file = analysis_path / "entreprises.csv"
        if csv_file.exists():
            try:
                import csv
                with open(csv_file, encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    market_data += "### Données entreprises\n"
                    market_data += f"- Total entreprises: {len(rows)}\n"
                    # Aggregate some stats
                    sectors = {}
                    for row in rows:
                        naf = row.get("naf", "")[:2]
                        if naf:
                            sectors[naf] = sectors.get(naf, 0) + 1
                    market_data += f"- Secteurs NAF: {dict(list(sectors.items())[:5])}\n"
            except Exception as e:
                logger.debug(f"Failed to load CSV data: {e}")
                pass

        if not market_data:
            return json.dumps({
                "success": False,
                "error": f"Aucune donnée d'analyse trouvée dans {analysis_dir}",
            }, ensure_ascii=False)

        if ctx:
            ctx.info("[BP] Données chargées, génération du BP...")

        # Call the main generation function
        result = await tawiza_generate_bp(
            company_name=company_name,
            company_description=company_description,
            territory=territory,
            sector=sector,
            market_data=market_data,
            funding_ask=funding_ask,
            output_dir=str(analysis_path / "business_plan"),
            ctx=ctx,
        )

        return result
