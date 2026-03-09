# Tawiza-V2 Test Suite

Suite complète de tests d'intégration pour le pipeline ML Tawiza-V2.

## Architecture de Tests

```
tests/
├── conftest.py                           # Configuration pytest et fixtures partagées
├── integration/                          # Tests d'intégration
│   ├── test_model_storage_pipeline.py   # Pipeline de stockage MinIO
│   ├── test_fine_tuning_complete.py     # Pipeline de fine-tuning complet
│   ├── test_active_learning.py          # Système d'active learning
│   └── test_ml_pipeline_complete.py     # Pipeline ML end-to-end
├── performance/                          # Tests de performance
│   └── test_api_performance.py          # Latence, throughput, memory
└── security/                             # Tests de sécurité
    └── test_api_security.py             # Validation, injection, XSS
```

## Prérequis

### Services Requis

Les tests d'intégration nécessitent les services suivants:

```bash
# MinIO (S3-compatible storage)
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# PostgreSQL (optional - pour tests DB)
docker run -d \
  -p 5432:5432 \
  --name postgres \
  -e POSTGRES_USER=tawiza \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=tawiza \
  postgres:15

# Redis (optional - pour tests cache)
docker run -d \
  -p 6379:6379 \
  --name redis \
  redis:7-alpine

# MLflow (optional - pour tests tracking)
docker run -d \
  -p 5000:5000 \
  --name mlflow \
  ghcr.io/mlflow/mlflow:latest \
  mlflow server --host 0.0.0.0

# Ollama (optional - pour tests fine-tuning)
docker run -d \
  -p 11434:11434 \
  --name ollama \
  ollama/ollama
```

### Dépendances Python

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov httpx psutil
```

## Exécution des Tests

### Tous les Tests

```bash
# Exécuter tous les tests avec coverage
pytest -v --cov=src --cov-report=html

# Avec output détaillé
pytest -v -s --cov=src
```

### Tests par Catégorie

```bash
# Tests d'intégration uniquement
pytest tests/integration/ -v

# Tests de performance
pytest tests/performance/ -v -m performance

# Tests de sécurité
pytest tests/security/ -v -m security
```

### Tests par Marker

```bash
# Tests nécessitant MinIO
pytest -v -m minio

# Tests nécessitant Ollama
pytest -v -m ollama

# Tests nécessitant MLflow
pytest -v -m mlflow

# Tests lents (skip par défaut)
pytest -v -m "not slow"

# Tests rapides uniquement
pytest -v -m "not slow and not integration"
```

### Tests Spécifiques

```bash
# Test storage pipeline
pytest tests/integration/test_model_storage_pipeline.py -v

# Test fine-tuning pipeline
pytest tests/integration/test_fine_tuning_complete.py -v

# Test active learning
pytest tests/integration/test_active_learning.py -v

# Test de performance API
pytest tests/performance/test_api_performance.py -v

# Test de sécurité
pytest tests/security/test_api_security.py -v
```

### Mode Debug

```bash
# Arrêter au premier échec
pytest -v -x

# Verbose avec print statements
pytest -v -s

# Avec pdb au premier échec
pytest --pdb

# Trace complète des erreurs
pytest --tb=long
```

## Configuration

### Variables d'Environnement

Créer un fichier `.env.test`:

```bash
# Application
APP_ENV=testing
DEBUG=true

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=test-models

# Database (optional)
DATABASE_URL=postgresql+asyncpg://tawiza:password@localhost:5432/tawiza_test

# Redis (optional)
REDIS_URL=redis://localhost:6379/1

# MLflow (optional)
MLFLOW_TRACKING_URI=http://localhost:5000

# Ollama (optional)
OLLAMA_URL=http://localhost:11434
```

### pytest.ini

Le fichier `pytest.ini` à la racine configure:
- Test discovery patterns
- Coverage options
- Markers personnalisés
- Asyncio mode
- Logging

## Fixtures Disponibles

### Client & Services

- `client`: Async HTTP client pour tester l'API FastAPI
- `settings`: Configuration de test
- `storage_adapter`: Adapter MinIO avec bucket de test
- `versioning_service`: Service de versioning
- `minio_client`: Client MinIO brut

### Données de Test

- `sample_modelfile`: Modelfile Ollama d'exemple
- `sample_annotations`: Annotations Label Studio
- `sample_training_metadata`: Métadonnées d'entraînement
- `test_model_name`: Nom de modèle unique pour tests

## Coverage

### Objectif de Coverage

- **Minimum**: 80% (fail_under dans .coveragerc)
- **Cible**: 90%+
- **Code critique**: 95%+

### Générer le Rapport

```bash
# HTML report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov=src --cov-report=term-missing

# XML report (pour CI/CD)
pytest --cov=src --cov-report=xml
```

### Coverage par Module

```bash
# Coverage d'un module spécifique
pytest --cov=src.infrastructure.storage --cov-report=term-missing

# Coverage de plusieurs modules
pytest --cov=src.infrastructure.ml --cov=src.infrastructure.storage
```

## Tests de Performance

### Métriques Surveillées

1. **Latence API**
   - Health endpoint: <100ms avg
   - Feedback endpoint: <200ms avg
   - P95: <200ms, P99: <500ms

2. **Throughput**
   - >50 req/s avec connection pooling
   - >80% success rate en concurrent

3. **Mémoire**
   - <50% d'augmentation sur 1000 requêtes
   - Pas de memory leaks détectés

4. **Storage**
   - Upload/Download MinIO: <5s
   - Data preparation: >100 annotations/s

### Exécution des Benchmarks

```bash
# Performance tests complets
pytest tests/performance/ -v --durations=10

# Avec profiling
pytest tests/performance/ -v --profile

# Memory profiling
pytest tests/performance/ -v --memray
```

## Tests de Sécurité

### Vulnérabilités Testées

1. **Injection**
   - SQL injection
   - Command injection
   - Path traversal
   - XSS

2. **Validation**
   - Input sanitization
   - Type validation
   - Payload size limits
   - JSON parsing

3. **Headers de Sécurité**
   - CORS
   - CSP (Content Security Policy)
   - X-Frame-Options
   - X-Content-Type-Options

4. **Authentication**
   - API key validation
   - JWT token validation
   - Rate limiting

### Scan de Sécurité

```bash
# Tests de sécurité complets
pytest tests/security/ -v

# Avec report détaillé
pytest tests/security/ -v --html=security-report.html
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      minio:
        image: minio/minio
        ports:
          - 9000:9000
        env:
          MINIO_ROOT_USER: minioadmin
          MINIO_ROOT_PASSWORD: minioadmin

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          pytest -v --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Troubleshooting

### Tests qui Échouent

```bash
# Verbose debugging
pytest -vv -s --tb=long

# Voir les logs
pytest -v --log-cli-level=DEBUG

# Isoler un test
pytest tests/integration/test_model_storage_pipeline.py::TestModelStoragePipeline::test_bucket_initialization -v
```

### Services Non Disponibles

```bash
# Skip tests nécessitant MinIO
pytest -v -m "not minio"

# Skip tests d'intégration
pytest -v -m "not integration"

# Tests unitaires seulement
pytest -v -m unit
```

### Timeout

```bash
# Augmenter le timeout
pytest -v --timeout=300

# Désactiver le timeout
pytest -v --timeout=0
```

### Cleanup

```bash
# Nettoyer les buckets MinIO de test
python -c "
from minio import Minio
client = Minio('localhost:9000', 'minioadmin', 'minioadmin', secure=False)
for bucket in client.list_buckets():
    if bucket.name.startswith('test-'):
        objects = client.list_objects(bucket.name, recursive=True)
        for obj in objects:
            client.remove_object(bucket.name, obj.object_name)
        client.remove_bucket(bucket.name)
"
```

## Best Practices

### Écriture de Tests

1. **Isolation**: Chaque test doit être indépendant
2. **Fixtures**: Utiliser les fixtures pour le setup/teardown
3. **Nommage**: Noms descriptifs (`test_storage_operation_with_invalid_version`)
4. **Assertions**: Assertions claires avec messages
5. **Mocking**: Mock les services externes quand approprié

### Organisation

1. **Par Feature**: Tests groupés par fonctionnalité
2. **Par Layer**: Integration vs Unit vs E2E
3. **Markers**: Utiliser les markers pour filtrage
4. **Documentation**: Docstrings pour tests complexes

### Performance

1. **Fast Tests**: Tests rapides par défaut
2. **Slow Tests**: Marker `@pytest.mark.slow`
3. **Parallel**: Utiliser pytest-xdist pour parallélisation
4. **Fixtures Scope**: Session/module scope pour fixtures coûteuses

## Ressources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [MinIO Python SDK](https://min.io/docs/minio/linux/developers/python/minio-py.html)

## Support

Pour questions ou problèmes:
1. Vérifier les logs: `pytest -v -s --log-cli-level=DEBUG`
2. Vérifier la configuration: `.env.test`, `pytest.ini`
3. Vérifier les services: `docker ps`, test de connectivité
4. Consulter la documentation des fixtures dans `conftest.py`
