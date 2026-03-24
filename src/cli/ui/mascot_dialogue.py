# src/cli/ui/mascot_dialogue.py
"""Système de dialogues contextuels pour la mascotte."""

import random
from enum import StrEnum


class DialogueContext(StrEnum):
    GREETING = "greeting"
    FAREWELL = "farewell"
    WAITING = "waiting"
    WORKING = "working"
    SUCCESS = "success"
    ERROR = "error"
    TIP = "tip"
    GPU_STATUS = "gpu_status"
    MODEL_LOADING = "model_loading"


DIALOGUE_TEMPLATES = {
    DialogueContext.GREETING: [
        "Salut! Prêt à coder ensemble? 💻",
        "Hey! Qu'est-ce qu'on construit aujourd'hui?",
        "Bienvenue! Je suis là pour t'aider!",
        "Miaou! Nouvelle aventure en vue? 🐱",
    ],
    DialogueContext.WAITING: [
        "Un instant, je réfléchis...",
        "Hmm, laisse-moi regarder ça...",
        "Je cherche la meilleure solution...",
        "Patience, la magie opère... ✨",
    ],
    DialogueContext.WORKING: [
        "Je travaille dessus! ⚙️",
        "En cours de traitement...",
        "Mes petites pattes s'activent! 🐾",
        "Calcul en cours...",
    ],
    DialogueContext.SUCCESS: [
        "Parfait! {task} terminé avec succès! ✨",
        "Bravo! C'est fait! 🎉",
        "Super! {task} complété!",
        "Mission accomplie! 🏆",
    ],
    DialogueContext.ERROR: [
        "Oops! Une erreur s'est produite: {error}",
        "Aïe! Problème détecté: {error}",
        "Hmm, quelque chose ne va pas: {error}",
        "Désolé, erreur rencontrée: {error}",
    ],
    DialogueContext.GPU_STATUS: [
        "GPU: {status} | Mémoire: {memory}",
        "🎮 GPU {status} - {memory} utilisé",
        "Carte graphique: {status} ({memory})",
    ],
    DialogueContext.MODEL_LOADING: [
        "Chargement du modèle {model}...",
        "Je prépare {model} pour toi...",
        "Initialisation de {model}... 🧠",
    ],
    DialogueContext.TIP: [
        "💡 Astuce: Utilise --help pour voir les options!",
        "💡 Tu savais? 'tawiza mascot-demo all' montre toutes les animations!",
        "💡 Essaie 'tawiza system status' pour voir l'état du système!",
    ],
}


class MascotDialogue:
    """Gestionnaire de dialogues contextuels."""

    def get_message(self, context: DialogueContext, **kwargs) -> str:
        """Retourne un message aléatoire pour le contexte donné."""
        templates = DIALOGUE_TEMPLATES.get(context, ["..."])
        template = random.choice(templates)
        return template.format(**kwargs) if kwargs else template

    def get_tip(self) -> str:
        """Retourne une astuce aléatoire."""
        return self.get_message(DialogueContext.TIP)
