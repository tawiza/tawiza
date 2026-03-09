#!/usr/bin/env python3
"""
Async Runner Helper pour Tawiza-V2 CLI
Gère les event loops de manière efficace pour éviter les multiples asyncio.run()
"""

import asyncio
from collections.abc import Coroutine
from functools import wraps
from typing import Any, TypeVar

T = TypeVar('T')

# Event loop réutilisable
_event_loop = None


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Obtenir ou créer un event loop réutilisable.

    Returns:
        asyncio.AbstractEventLoop: Event loop actif
    """
    global _event_loop

    try:
        # Essayer d'obtenir l'event loop actif
        loop = asyncio.get_running_loop()
        return loop
    except RuntimeError:
        # Pas d'event loop en cours, en créer ou réutiliser un
        if _event_loop is None or _event_loop.is_closed():
            _event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_event_loop)
        return _event_loop


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """
    Exécuter une coroutine de manière efficace.

    Utilise l'event loop existant si disponible, sinon en crée un réutilisable.
    C'est plus efficace que asyncio.run() qui crée un nouveau loop à chaque fois.

    Args:
        coro: Coroutine à exécuter

    Returns:
        T: Résultat de la coroutine

    Example:
        >>> async def fetch_data():
        ...     return "data"
        >>> result = run_async(fetch_data())
        >>> print(result)
        data
    """
    try:
        # Si on est déjà dans un event loop, utiliser asyncio.run()
        # (sinon on aurait une erreur)
        loop = asyncio.get_running_loop()
        # On est déjà dans un event loop, créer une task
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(coro)
    except RuntimeError:
        # Pas d'event loop en cours, utiliser notre loop réutilisable
        loop = get_or_create_event_loop()
        return loop.run_until_complete(coro)


def async_command(func):
    """
    Décorateur pour transformer une fonction async en commande Typer synchrone.

    Gère automatiquement l'event loop de manière efficace.

    Example:
        >>> @app.command()
        ... @async_command
        ... async def my_command():
        ...     await some_async_operation()
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return run_async(func(*args, **kwargs))
    return wrapper


def cleanup_event_loop():
    """
    Nettoyer l'event loop réutilisable.

    À appeler à la fin du programme si nécessaire.
    """
    global _event_loop
    if _event_loop and not _event_loop.is_closed():
        _event_loop.close()
        _event_loop = None
