#!/usr/bin/env python3
"""
Helpers asynchrones pour Tawiza-V2 CLI
"""

import asyncio
import functools
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def run_async(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Décorateur pour exécuter une fonction asynchrone dans un contexte synchrone

    Args:
        func: Fonction asynchrone à exécuter

    Returns:
        Fonction qui exécute la fonction asynchrone
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Si une boucle d'événements existe déjà, l'utiliser
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Créer une nouvelle tâche si la boucle tourne déjà
                return asyncio.create_task(func(*args, **kwargs))
            else:
                # Exécuter la fonction async
                return loop.run_until_complete(func(*args, **kwargs))
        except RuntimeError:
            # Aucune boucle d'événements n'existe, en créer une nouvelle
            return asyncio.run(func(*args, **kwargs))

    return wrapper


async def run_sync_in_async[T](func: Callable[..., T], *args, **kwargs) -> T:
    """
    Exécuter une fonction synchrone dans un contexte asynchrone

    Args:
        func: Fonction synchrone à exécuter
        *args: Arguments positionnels
        **kwargs: Arguments nommés

    Returns:
        Résultat de la fonction
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
