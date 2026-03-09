"""Google Trends collector - Search interest signals by region."""

import asyncio
from datetime import date, timedelta
from typing import Any

from loguru import logger
from pytrends.request import TrendReq

from ..base import BaseCollector, CollectedSignal, CollectorConfig


class GoogleTrendsCollector(BaseCollector):
    """Collect search trends data from Google Trends.
    
    Monitors search interest for economic keywords across French regions,
    providing early indicators of economic sentiment and job market stress.
    """

    # Keywords to monitor with their signal implications
    KEYWORDS = [
        "liquidation judiciaire",  # Business liquidation (negative)
        "pôle emploi",            # Job center (negative/neutral)
        "RSA",                    # Social assistance (negative)  
        "chômage partiel",        # Partial unemployment (negative)
        "plan social"             # Social plan/layoffs (negative)
    ]

    # Google Trends region codes to French departments mapping
    REGION_TO_DEPT = {
        "FR-ARA": ["01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"],  # Auvergne-Rhône-Alpes
        "FR-BFC": ["21", "25", "39", "58", "70", "71", "89", "90"],  # Bourgogne-Franche-Comté
        "FR-BRE": ["22", "29", "35", "56"],  # Bretagne
        "FR-CVL": ["18", "28", "36", "37", "41", "45"],  # Centre-Val de Loire
        "FR-COR": ["2A", "2B"],  # Corse
        "FR-GES": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],  # Grand Est
        "FR-HDF": ["02", "59", "60", "62", "80"],  # Hauts-de-France
        "FR-IDF": ["75", "77", "78", "91", "92", "93", "94", "95"],  # Île-de-France
        "FR-NOR": ["14", "27", "50", "61", "76"],  # Normandie
        "FR-NAQ": ["16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"],  # Nouvelle-Aquitaine
        "FR-OCC": ["09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"],  # Occitanie
        "FR-PDL": ["44", "49", "53", "72", "85"],  # Pays de la Loire
        "FR-PAC": ["04", "05", "06", "13", "83", "84"]  # Provence-Alpes-Côte d'Azur
    }

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="google_trends",
                source_type="api",
                rate_limit=0.5,  # 2 second delays between requests
                timeout=30,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect Google Trends data for economic keywords."""
        if since is None:
            since = date.today() - timedelta(days=7)

        signals = []
        
        # Create pytrends instance
        try:
            pytrends = TrendReq(hl='fr-FR', tz=360)
        except Exception as e:
            logger.error(f"[google_trends] Failed to initialize pytrends: {e}")
            return []

        for keyword in self.KEYWORDS:
            logger.info(f"[google_trends] Fetching data for '{keyword}'")
            
            try:
                # Get interest by region for France
                pytrends.build_payload(
                    kw_list=[keyword],
                    cat=0,
                    timeframe='now 7-d',
                    geo='FR'
                )
                
                # Get regional data
                interest_data = pytrends.interest_by_region(
                    resolution='REGION',
                    inc_low_vol=True,
                    inc_geo_code=False
                )
                
                if interest_data.empty:
                    logger.warning(f"[google_trends] No data for '{keyword}'")
                    await asyncio.sleep(2)
                    continue
                
                # Process each region's data
                for region_name, interest_value in interest_data[keyword].items():
                    if interest_value == 0:
                        continue
                        
                    # Map region to departments
                    departments = self._map_region_to_departments(region_name)
                    
                    for dept_code in departments:
                        if code_dept and dept_code != code_dept:
                            continue
                            
                        signal = CollectedSignal(
                            source="google_trends",
                            source_url=f"trends:FR:{keyword}:{region_name}",
                            event_date=date.today(),
                            code_dept=dept_code,
                            metric_name=f"search_interest_{keyword.replace(' ', '_')}",
                            metric_value=float(interest_value),
                            signal_type=self._get_signal_type(keyword, interest_value),
                            confidence=0.4,  # Trends data is noisy
                            raw_data={
                                "keyword": keyword,
                                "region": region_name,
                                "interest_value": interest_value,
                                "timeframe": "7d"
                            }
                        )
                        signals.append(signal)
                
                logger.info(f"[google_trends] Processed '{keyword}': {len([s for s in signals if s.raw_data.get('keyword') == keyword])} signals")
                
            except Exception as e:
                logger.warning(f"[google_trends] Error fetching '{keyword}': {e}")
                
            # Rate limit to avoid 429 errors
            await asyncio.sleep(2)
        
        logger.info(f"[google_trends] Collected {len(signals)} total signals")
        return signals

    def _map_region_to_departments(self, region_name: str) -> list[str]:
        """Map a Google Trends region name to department codes."""
        # Try to find exact match first
        for code, depts in self.REGION_TO_DEPT.items():
            region_short = code.split('-')[1]  # Extract ARA, BFC, etc.
            if region_short.lower() in region_name.lower():
                return depts
        
        # Fallback: try to match by region name
        region_mapping = {
            "auvergne": self.REGION_TO_DEPT["FR-ARA"],
            "rhône": self.REGION_TO_DEPT["FR-ARA"],
            "bourgogne": self.REGION_TO_DEPT["FR-BFC"],
            "franche": self.REGION_TO_DEPT["FR-BFC"],
            "bretagne": self.REGION_TO_DEPT["FR-BRE"],
            "centre": self.REGION_TO_DEPT["FR-CVL"],
            "corse": self.REGION_TO_DEPT["FR-COR"],
            "grand est": self.REGION_TO_DEPT["FR-GES"],
            "hauts": self.REGION_TO_DEPT["FR-HDF"],
            "île": self.REGION_TO_DEPT["FR-IDF"],
            "paris": self.REGION_TO_DEPT["FR-IDF"],
            "normandie": self.REGION_TO_DEPT["FR-NOR"],
            "aquitaine": self.REGION_TO_DEPT["FR-NAQ"],
            "occitanie": self.REGION_TO_DEPT["FR-OCC"],
            "pays": self.REGION_TO_DEPT["FR-PDL"],
            "loire": self.REGION_TO_DEPT["FR-PDL"],
            "provence": self.REGION_TO_DEPT["FR-PAC"],
            "côte": self.REGION_TO_DEPT["FR-PAC"]
        }
        
        for name_part, depts in region_mapping.items():
            if name_part.lower() in region_name.lower():
                return depts
        
        # If no match found, log and return empty list
        logger.debug(f"[google_trends] Could not map region '{region_name}' to departments")
        return []

    def _get_signal_type(self, keyword: str, interest_value: float) -> str:
        """Determine signal type based on keyword and interest level."""
        negative_keywords = ["liquidation", "chômage", "plan social"]
        neutral_keywords = ["pôle emploi"]
        
        for neg_kw in negative_keywords:
            if neg_kw in keyword.lower():
                return "negatif" if interest_value > 50 else "neutre"
        
        for neut_kw in neutral_keywords:
            if neut_kw in keyword.lower():
                return "neutre"
                
        # Default for other keywords like RSA
        return "negatif" if interest_value > 70 else "neutre"