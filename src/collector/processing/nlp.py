"""NLP processing for French text - entity extraction with spaCy."""

from loguru import logger


class FrenchNLP:
    """French NLP pipeline using spaCy for NER.

    Extracts:
    - LOC: Locations (communes, departments, regions)
    - ORG: Organizations (companies, institutions)
    - PER: Persons
    - MISC: Other entities
    """

    def __init__(self, model: str = "fr_core_news_lg") -> None:
        self._model_name = model
        self._nlp = None

    def _load(self) -> None:
        """Lazy-load spaCy model."""
        if self._nlp is not None:
            return

        try:
            import spacy

            self._nlp = spacy.load(self._model_name)
            logger.info(f"[nlp] Loaded spaCy model: {self._model_name}")
        except OSError:
            logger.warning(
                f"[nlp] Model {self._model_name} not found. "
                f"Install with: python -m spacy download {self._model_name}"
            )
            # Fallback to small model
            try:
                import spacy

                self._nlp = spacy.load("fr_core_news_sm")
                logger.info("[nlp] Fallback to fr_core_news_sm")
            except OSError:
                logger.error("[nlp] No French spaCy model available")
                self._nlp = None

    def extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extract named entities from French text.

        Returns:
            Dict with entity types as keys and lists of entity texts.
        """
        self._load()
        if self._nlp is None:
            return {}

        doc = self._nlp(text[:10000])  # Limit text length

        entities: dict[str, list[str]] = {}
        for ent in doc.ents:
            label = ent.label_
            if label not in entities:
                entities[label] = []
            if ent.text not in entities[label]:
                entities[label].append(ent.text)

        return entities

    def extract_locations(self, text: str) -> list[str]:
        """Extract location names from text."""
        entities = self.extract_entities(text)
        return entities.get("LOC", []) + entities.get("GPE", [])

    def extract_organizations(self, text: str) -> list[str]:
        """Extract organization names from text."""
        entities = self.extract_entities(text)
        return entities.get("ORG", [])
