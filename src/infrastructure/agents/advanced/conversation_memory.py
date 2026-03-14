#!/usr/bin/env python3
"""
Mémoire Conversationnelle Avancée pour Tawiza-V2
Système de mémoire intelligente avec contexte, apprentissage et personnalisation

Supporte la recherche vectorielle via Qdrant (optionnel) avec fallback SQLite.
"""

import asyncio
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# Import optionnel de Qdrant pour recherche vectorielle
try:
    from src.infrastructure.storage.qdrant.client import QdrantClient, QdrantConfig
    from src.infrastructure.storage.qdrant.embeddings import EmbeddingsConfig, EmbeddingsService

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("Qdrant non disponible - utilisation de la recherche par mots-clés")

# Configuration du logging


@dataclass
class ConversationTurn:
    """Un tour de conversation"""

    id: str
    timestamp: float
    role: str  # user, assistant, system
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embeddings: list[float] | None = None
    importance_score: float = 0.5


@dataclass
class ConversationContext:
    """Contexte d'une conversation"""

    session_id: str
    user_id: str
    agent_type: str
    start_time: float
    last_update: float
    summary: str = ""
    key_topics: list[str] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    conversation_length: int = 0


class ShortTermMemory:
    """Mémoire à court terme - conversations récentes"""

    def __init__(self, max_turns: int = 10, max_age_minutes: int = 30):
        self.max_turns = max_turns
        self.max_age_minutes = max_age_minutes
        self.recent_turns: list[ConversationTurn] = []
        self.current_context: ConversationContext | None = None

    def add_turn(self, turn: ConversationTurn):
        """Ajouter un tour de conversation"""
        self.recent_turns.append(turn)

        # Garder seulement les tours récents
        if len(self.recent_turns) > self.max_turns:
            self.recent_turns.pop(0)

        # Nettoyer les tours trop anciens
        current_time = time.time()
        cutoff_time = current_time - (self.max_age_minutes * 60)
        self.recent_turns = [turn for turn in self.recent_turns if turn.timestamp > cutoff_time]

    def get_recent_context(self, last_n: int = 5) -> list[ConversationTurn]:
        """Obtenir les tours récents"""
        return self.recent_turns[-last_n:] if self.recent_turns else []

    def get_context_summary(self) -> str:
        """Obtenir un résumé du contexte récent"""
        if not self.recent_turns:
            return "Aucune conversation récente"

        # Extraire les points clés
        key_points = []
        for turn in self.recent_turns[-3:]:  # 3 derniers tours
            if turn.role == "user":
                # Extraire l'intention principale
                key_points.append(
                    turn.content[:100] + "..." if len(turn.content) > 100 else turn.content
                )

        return " | ".join(key_points) if key_points else "Conversation en cours"

    def calculate_importance(self, turn: ConversationTurn) -> float:
        """Calculer l'importance d'un tour"""
        importance = 0.5  # Base

        # Facteurs d'importance
        if turn.role == "user":
            importance += 0.2

        # Longueur du message (plus long = potentiellement plus important)
        if len(turn.content) > 200:
            importance += 0.1

        # Mots-clés importants
        important_keywords = ["important", "urgent", "critical", "help", "error", "problem"]
        content_lower = turn.content.lower()
        for keyword in important_keywords:
            if keyword in content_lower:
                importance += 0.05

        return min(importance, 1.0)


class LongTermMemory:
    """Mémoire à long terme - conversations historiques avec recherche vectorielle."""

    COLLECTION_NAME = "conversation_memory"

    def __init__(
        self,
        db_path: str = "memory.db",
        enable_vector_search: bool = True,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedding_model: str = "nomic-embed-text",
    ):
        self.db_path = db_path
        self.enable_vector_search = enable_vector_search and QDRANT_AVAILABLE
        self._qdrant: QdrantClient | None = None
        self._embeddings: EmbeddingsService | None = None
        self._vector_initialized = False

        # Configuration Qdrant
        self._qdrant_config = {
            "host": qdrant_host,
            "port": qdrant_port,
            "embedding_model": embedding_model,
        }

        self._init_database()

        if self.enable_vector_search:
            self._init_vector_search()

    def _init_database(self):
        """Initialiser la base de données SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table des conversations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                user_id TEXT,
                agent_type TEXT,
                start_time REAL,
                last_update REAL,
                summary TEXT,
                key_topics TEXT,
                user_preferences TEXT,
                conversation_length INTEGER
            )
        """)

        # Table des tours de conversation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                timestamp REAL,
                role TEXT,
                content TEXT,
                metadata TEXT,
                embeddings TEXT,
                importance_score REAL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)

        # Table des patterns d'apprentissage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_patterns (
                id TEXT PRIMARY KEY,
                pattern_type TEXT,
                pattern_data TEXT,
                frequency INTEGER,
                last_seen REAL,
                success_rate REAL
            )
        """)

        conn.commit()
        conn.close()

    def _init_vector_search(self) -> None:
        """Initialiser les services de recherche vectorielle."""
        if not QDRANT_AVAILABLE:
            logger.warning("Qdrant non disponible - recherche vectorielle désactivée")
            return

        try:
            # Initialiser le client Qdrant
            qdrant_config = QdrantConfig(
                host=self._qdrant_config["host"],
                port=self._qdrant_config["port"],
                collection_name=self.COLLECTION_NAME,
                vector_size=1024,  # mxbai-embed-large dimension
            )
            self._qdrant = QdrantClient(config=qdrant_config)

            # Initialiser le service d'embeddings
            embeddings_config = EmbeddingsConfig(model=self._qdrant_config["embedding_model"])
            self._embeddings = EmbeddingsService(config=embeddings_config)

            # Créer la collection si nécessaire (async dans une boucle sync)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._qdrant.ensure_collection())
            else:
                asyncio.create_task(self._qdrant.ensure_collection())

            self._vector_initialized = True
            logger.info(f"✅ Recherche vectorielle initialisée: {self.COLLECTION_NAME}")

        except Exception as e:
            logger.warning(f"⚠️ Échec initialisation vector search: {e}")
            self._vector_initialized = False

    async def _generate_conversation_embedding(
        self, turns: list[ConversationTurn]
    ) -> list[float] | None:
        """Générer un embedding pour une conversation complète."""
        if not self._vector_initialized or not self._embeddings:
            return None

        try:
            # Concaténer les contenus des tours pour un embedding global
            content_parts = []
            for turn in turns:
                prefix = "User: " if turn.role == "user" else "Assistant: "
                content_parts.append(f"{prefix}{turn.content[:500]}")  # Limiter la longueur

            combined_text = "\n".join(content_parts[-10:])  # 10 derniers tours max
            embedding = await self._embeddings.embed(combined_text)
            return embedding

        except Exception as e:
            logger.warning(f"⚠️ Échec génération embedding: {e}")
            return None

    async def _index_conversation_vector(
        self, session_id: str, context: ConversationContext, turns: list[ConversationTurn]
    ) -> bool:
        """Indexer une conversation dans Qdrant."""
        if not self._vector_initialized or not self._qdrant:
            return False

        try:
            embedding = await self._generate_conversation_embedding(turns)
            if not embedding:
                return False

            # Payload avec métadonnées pour filtrage
            payload = {
                "session_id": session_id,
                "user_id": context.user_id,
                "agent_type": context.agent_type,
                "summary": context.summary,
                "key_topics": context.key_topics,
                "start_time": context.start_time,
                "last_update": context.last_update,
                "conversation_length": context.conversation_length,
            }

            await self._qdrant.upsert(id=session_id, vector=embedding, payload=payload)
            logger.debug(f"📊 Conversation indexée: {session_id}")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Échec indexation vector: {e}")
            return False

    def store_conversation(self, context: ConversationContext, turns: list[ConversationTurn]):
        """Stocker une conversation complète"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Stocker le contexte
            cursor.execute(
                """
                INSERT OR REPLACE INTO conversations (
                    id, session_id, user_id, agent_type, start_time, last_update,
                    summary, key_topics, user_preferences, conversation_length
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    context.session_id,
                    context.session_id,
                    context.user_id,
                    context.agent_type,
                    context.start_time,
                    context.last_update,
                    context.summary,
                    json.dumps(context.key_topics),
                    json.dumps(context.user_preferences),
                    context.conversation_length,
                ),
            )

            # Stocker les tours
            for turn in turns:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO conversation_turns (
                        id, conversation_id, timestamp, role, content,
                        metadata, embeddings, importance_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        turn.id,
                        context.session_id,
                        turn.timestamp,
                        turn.role,
                        turn.content,
                        json.dumps(turn.metadata),
                        json.dumps(turn.embeddings) if turn.embeddings else None,
                        turn.importance_score,
                    ),
                )

            conn.commit()
            logger.info(f"💾 Conversation stockée: {context.session_id}")

            # Indexer dans Qdrant pour recherche vectorielle (async)
            if self._vector_initialized:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        self._index_conversation_vector(context.session_id, context, turns)
                    )
                else:
                    asyncio.create_task(
                        self._index_conversation_vector(context.session_id, context, turns)
                    )

        except Exception as e:
            logger.error(f"❌ Erreur lors du stockage: {str(e)}")
            conn.rollback()
        finally:
            conn.close()

    async def retrieve_similar_conversations_async(
        self, query: str, limit: int = 5
    ) -> list[tuple[ConversationContext, list[ConversationTurn]]]:
        """Récupérer des conversations similaires avec recherche vectorielle (async)."""
        # Essayer d'abord la recherche vectorielle
        if self._vector_initialized and self._qdrant and self._embeddings:
            try:
                # Générer l'embedding de la requête
                query_embedding = await self._embeddings.embed(query)

                # Rechercher les conversations similaires
                results = await self._qdrant.search(query_vector=query_embedding, limit=limit)

                if results:
                    conversations = []
                    for result in results:
                        payload = result.get("payload", {})
                        session_id = payload.get("session_id")
                        if session_id:
                            # Récupérer les détails depuis SQLite
                            conv = self._get_conversation_from_db(session_id)
                            if conv:
                                conversations.append(conv)

                    if conversations:
                        logger.info(f"🔍 Recherche vectorielle: {len(conversations)} résultats")
                        return conversations

            except Exception as e:
                logger.warning(f"⚠️ Recherche vectorielle échouée, fallback SQLite: {e}")

        # Fallback: recherche par mots-clés
        return self._keyword_search_conversations(query, limit)

    def _get_conversation_from_db(
        self, session_id: str
    ) -> tuple[ConversationContext, list[ConversationTurn]] | None:
        """Récupérer une conversation depuis SQLite par ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM conversations WHERE id = ?
            """,
                (session_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            context = ConversationContext(
                session_id=row[0],
                user_id=row[2],
                agent_type=row[3],
                start_time=row[4],
                last_update=row[5],
                summary=row[6],
                key_topics=json.loads(row[7]) if row[7] else [],
                user_preferences=json.loads(row[8]) if row[8] else {},
                conversation_length=row[9],
            )

            # Récupérer les tours
            cursor.execute(
                """
                SELECT * FROM conversation_turns
                WHERE conversation_id = ?
                ORDER BY timestamp
            """,
                (session_id,),
            )

            turns = []
            for turn_row in cursor.fetchall():
                turn = ConversationTurn(
                    id=turn_row[0],
                    timestamp=turn_row[2],
                    role=turn_row[3],
                    content=turn_row[4],
                    metadata=json.loads(turn_row[5]) if turn_row[5] else {},
                    embeddings=json.loads(turn_row[6]) if turn_row[6] else None,
                    importance_score=turn_row[7],
                )
                turns.append(turn)

            return (context, turns)

        except Exception as e:
            logger.error(f"❌ Erreur récupération conversation {session_id}: {e}")
            return None
        finally:
            conn.close()

    def _keyword_search_conversations(
        self, query: str, limit: int
    ) -> list[tuple[ConversationContext, list[ConversationTurn]]]:
        """Recherche par mots-clés (fallback SQLite)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT DISTINCT c.*, GROUP_CONCAT(ct.content, '|') as contents
                FROM conversations c
                JOIN conversation_turns ct ON c.id = ct.conversation_id
                WHERE c.summary LIKE ? OR ct.content LIKE ?
                GROUP BY c.id
                ORDER BY ct.importance_score DESC
                LIMIT ?
            """,
                (f"%{query}%", f"%{query}%", limit),
            )

            results = []
            for row in cursor.fetchall():
                context = ConversationContext(
                    session_id=row[0],
                    user_id=row[2],
                    agent_type=row[3],
                    start_time=row[4],
                    last_update=row[5],
                    summary=row[6],
                    key_topics=json.loads(row[7]) if row[7] else [],
                    user_preferences=json.loads(row[8]) if row[8] else {},
                    conversation_length=row[9],
                )

                # Récupérer les tours
                cursor.execute(
                    """
                    SELECT * FROM conversation_turns
                    WHERE conversation_id = ?
                    ORDER BY timestamp
                """,
                    (context.session_id,),
                )

                turns = []
                for turn_row in cursor.fetchall():
                    turn = ConversationTurn(
                        id=turn_row[0],
                        timestamp=turn_row[2],
                        role=turn_row[3],
                        content=turn_row[4],
                        metadata=json.loads(turn_row[5]) if turn_row[5] else {},
                        embeddings=json.loads(turn_row[6]) if turn_row[6] else None,
                        importance_score=turn_row[7],
                    )
                    turns.append(turn)

                results.append((context, turns))

            return results

        except Exception as e:
            logger.error(f"❌ Erreur recherche mots-clés: {e}")
            return []
        finally:
            conn.close()

    def retrieve_similar_conversations(
        self, query: str, limit: int = 5
    ) -> list[tuple[ConversationContext, list[ConversationTurn]]]:
        """Récupérer des conversations similaires (sync wrapper).

        Utilise la recherche vectorielle Qdrant si disponible,
        avec fallback automatique sur recherche par mots-clés SQLite.
        """
        # Si recherche vectorielle disponible, utiliser la version async
        if self._vector_initialized:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(
                    self.retrieve_similar_conversations_async(query, limit)
                )
            else:
                # Si déjà dans une boucle async, exécuter sync fallback
                return self._keyword_search_conversations(query, limit)

        # Fallback direct: recherche par mots-clés
        return self._keyword_search_conversations(query, limit)

    def extract_learning_patterns(self) -> dict[str, Any]:
        """Extraire des patterns d'apprentissage depuis les conversations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            patterns = {}

            # Patterns de succès
            cursor.execute("""
                SELECT pattern_type, COUNT(*) as frequency, AVG(success_rate) as avg_success
                FROM learning_patterns
                GROUP BY pattern_type
                ORDER BY frequency DESC
            """)

            success_patterns = []
            for row in cursor.fetchall():
                success_patterns.append(
                    {"type": row[0], "frequency": row[1], "avg_success_rate": row[2]}
                )

            patterns["success_patterns"] = success_patterns

            # Patterns utilisateur
            cursor.execute("""
                SELECT user_preferences, COUNT(*) as frequency
                FROM conversations
                WHERE user_preferences != '{}'
                GROUP BY user_preferences
                ORDER BY frequency DESC
                LIMIT 10
            """)

            user_patterns = []
            for row in cursor.fetchall():
                prefs = json.loads(row[0]) if row[0] else {}
                user_patterns.append({"preferences": prefs, "frequency": row[1]})

            patterns["user_patterns"] = user_patterns

            return patterns

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction des patterns: {str(e)}")
            return {}


class ContextManager:
    """Gestionnaire de contexte intelligent"""

    def __init__(self, short_term_memory: ShortTermMemory, long_term_memory: LongTermMemory):
        self.short_term = short_term_memory
        self.long_term = long_term_memory
        self.current_context: ConversationContext | None = None

    def start_new_conversation(self, user_id: str, agent_type: str) -> ConversationContext:
        """Démarrer une nouvelle conversation"""
        self.current_context = ConversationContext(
            session_id=self._generate_session_id(),
            user_id=user_id,
            agent_type=agent_type,
            start_time=time.time(),
            last_update=time.time(),
        )

        self.short_term.current_context = self.current_context
        logger.info(f"🌅 Nouvelle conversation démarrée: {self.current_context.session_id}")

        return self.current_context

    def update_context(self, turn: ConversationTurn):
        """Mettre à jour le contexte actuel"""
        if not self.current_context:
            return

        self.current_context.last_update = time.time()
        self.current_context.conversation_length += 1

        # Mettre à jour les topics clés
        if turn.role == "user":
            # Extraire les topics (simplifié)
            words = turn.content.lower().split()
            for word in words[:5]:  # Top 5 mots
                if word not in self.current_context.key_topics:
                    self.current_context.key_topics.append(word)

        # Mettre à jour l'importance
        importance = self.short_term.calculate_importance(turn)
        turn.importance_score = importance

        # Générer un résumé si nécessaire
        if self.current_context.conversation_length % 10 == 0:  # Tous les 10 tours
            self._update_summary()

    def _update_summary(self):
        """Mettre à jour le résumé de la conversation"""
        if not self.current_context:
            return

        recent_turns = self.short_term.get_recent_context(5)
        if recent_turns:
            # Générer un résumé simple
            user_turns = [t for t in recent_turns if t.role == "user"]
            if user_turns:
                last_user = user_turns[-1]
                self.current_context.summary = f"Dernier échange: {last_user.content[:100]}..."

    def _generate_session_id(self) -> str:
        """Générer un ID de session unique"""
        timestamp = str(int(time.time() * 1000))
        random_hash = hashlib.md5(f"{timestamp}{time.time()}".encode()).hexdigest()[:8]
        return f"session_{timestamp}_{random_hash}"

    def get_personalized_response(
        self, user_input: str, agent_context: dict[str, Any]
    ) -> dict[str, Any]:
        """Obtenir une réponse personnalisée basée sur le contexte"""
        if not self.current_context:
            return {"response": user_input, "personalized": False}

        # Récupérer les préférences utilisateur
        preferences = self.current_context.user_preferences

        # Récupérer les conversations similaires
        similar_conversations = self.long_term.retrieve_similar_conversations(user_input, limit=3)

        # Construire la réponse personnalisée
        personalized_response = {
            "original_input": user_input,
            "user_preferences": preferences,
            "similar_contexts": similar_conversations,
            "personalized": True,
            "suggestions": self._generate_suggestions(user_input, preferences),
        }

        return personalized_response

    def _generate_suggestions(self, user_input: str, preferences: dict[str, Any]) -> list[str]:
        """Générer des suggestions basées sur le contexte"""
        suggestions = []

        # Suggestions basées sur les préférences
        if preferences.get("preferred_model_type") == "fast":
            suggestions.append("Essayez avec un modèle plus rapide pour de meilleures performances")

        if preferences.get("detailed_analysis"):
            suggestions.append("Activez l'analyse détaillée pour plus d'informations")

        # Suggestions basées sur l'input
        if "gpu" in user_input.lower():
            suggestions.append("Vérifiez la température GPU pour optimiser les performances")

        if "training" in user_input.lower():
            suggestions.append("Utilisez le monitoring en temps réel pour suivre le progrès")

        return suggestions[:3]  # Maximum 3 suggestions


class PersonalizationEngine:
    """Moteur de personnalisation intelligente"""

    def __init__(self):
        self.user_profiles: dict[str, dict[str, Any]] = {}
        self.learning_patterns: dict[str, float] = {}

    def learn_from_interaction(self, user_id: str, interaction_data: dict[str, Any]):
        """Apprendre des interactions utilisateur"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                "preferences": {},
                "behavior_patterns": {},
                "success_rate": 0.0,
                "interaction_count": 0,
            }

        profile = self.user_profiles[user_id]
        profile["interaction_count"] += 1

        # Extraire les préférences
        if "preferred_model_type" in interaction_data:
            profile["preferences"]["preferred_model_type"] = interaction_data[
                "preferred_model_type"
            ]

        if "detailed_analysis" in interaction_data:
            profile["preferences"]["detailed_analysis"] = interaction_data["detailed_analysis"]

        # Mettre à jour le taux de réussite
        if "success" in interaction_data:
            current_success = profile["success_rate"]
            new_success = 1.0 if interaction_data["success"] else 0.0
            # Moyenne mobile
            profile["success_rate"] = (
                current_success * (profile["interaction_count"] - 1) + new_success
            ) / profile["interaction_count"]

        logger.info(
            f"🎯 Apprentissage pour utilisateur {user_id}: {len(interaction_data)} patterns mis à jour"
        )

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        """Obtenir le profil utilisateur complet"""
        return self.user_profiles.get(
            user_id,
            {
                "preferences": {},
                "behavior_patterns": {},
                "success_rate": 0.0,
                "interaction_count": 0,
            },
        )

    def predict_user_preference(self, user_id: str, context: dict[str, Any]) -> dict[str, Any]:
        """Prédire les préférences utilisateur basées sur le contexte"""
        profile = self.get_user_profile(user_id)

        predictions = {
            "confidence": 0.5,  # Base confidence
            "suggested_actions": [],
            "preferred_approach": "standard",
        }

        # Prédiction basée sur l'historique
        if profile["success_rate"] > 0.8:
            predictions["confidence"] = 0.9
            predictions["suggested_actions"] = [
                "Utiliser l'approche précédente",
                "Activer l'analyse détaillée",
            ]
            predictions["preferred_approach"] = "detailed"
        elif profile["success_rate"] > 0.6:
            predictions["confidence"] = 0.7
            predictions["suggested_actions"] = [
                "Suivre les recommandations",
                "Vérifier les paramètres",
            ]
            predictions["preferred_approach"] = "guided"
        else:
            predictions["confidence"] = 0.3
            predictions["suggested_actions"] = ["Commencer simple", "Suivre le guide"]
            predictions["preferred_approach"] = "simple"

        return predictions


class AdvancedConversationMemory:
    """Mémoire conversationnelle avancée complète"""

    def __init__(self, db_path: str = "memory.db"):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(db_path)
        self.context_manager = ContextManager(self.short_term, self.long_term)
        self.personalization = PersonalizationEngine()

    def start_conversation(self, user_id: str, agent_type: str) -> ConversationContext:
        """Démarrer une nouvelle conversation avec mémoire avancée"""
        return self.context_manager.start_new_conversation(user_id, agent_type)

    def process_interaction(
        self, user_input: str, current_context: ConversationContext
    ) -> dict[str, Any]:
        """Traiter une interaction complète avec mémoire et personnalisation"""
        # Créer le tour de conversation
        turn = ConversationTurn(
            id=f"turn_{int(time.time() * 1000)}",
            timestamp=time.time(),
            role="user",
            content=user_input,
            importance_score=self.short_term.calculate_importance(user_input),
        )

        # Mettre à jour le contexte
        self.context_manager.update_context(turn)

        # Obtenir la réponse personnalisée
        personalized_response = self.context_manager.get_personalized_response(user_input, {})

        return personalized_response

    def get_conversation_summary(self, session_id: str) -> dict[str, Any]:
        """Obtenir un résumé complet d'une conversation"""
        context = self.context_manager.current_context
        if not context or context.session_id != session_id:
            return {"error": "Conversation non trouvée"}

        turns = self.short_term.get_recent_context(context.conversation_length)
        self.long_term.store_conversation(context, turns)

        return {"success": True, "message": "Conversation stockée avec succès"}
