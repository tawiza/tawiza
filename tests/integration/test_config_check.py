import httpx
import pytest
from fastapi import status

# URL de base de l'API (assurez-vous que le serveur tourne sur ce port)
BASE_URL = "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_api_health_check():
    """
    Test d'intégration basique pour vérifier que l'API est en ligne.
    Vérifie l'endpoint /health s'il existe (commun), sinon la racine.
    """
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Essai sur /health d'abord car c'est une bonne pratique
        try:
            response = await client.get("/health")
            if response.status_code == 404:
                # Fallback sur la racine
                response = await client.get("/")
        except httpx.RequestError:
            pytest.fail(f"Impossible de contacter l'API sur {BASE_URL}")

        assert response.status_code == status.HTTP_200_OK
        # Vérification optionnelle du contenu
        # data = response.json()
        # assert "status" in data or "message" in data


@pytest.mark.asyncio
async def test_swagger_ui_available():
    """Vérifie que la documentation Swagger est accessible."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "Swagger UI" in response.text
