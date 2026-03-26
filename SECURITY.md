# Politique de Sécurité  -  Tawiza

## Signaler une vulnérabilité

Si vous découvrez une vulnérabilité de sécurité dans Tawiza, **merci de ne PAS ouvrir une issue publique**.

### Processus de signalement

1. **Email** : Envoyez un rapport détaillé à **tawiza.v0@gmail.com**
2. **Délai** : Nous accusons réception sous 48h
3. **Correction** : Nous visons un correctif sous 7 jours pour les vulnérabilités critiques
4. **Disclosure** : Nous coordonnons la divulgation publique avec vous
5. **Crédit** : Les reporters sont crédités dans le CHANGELOG (sauf demande contraire)

### Informations à inclure

- Description de la vulnérabilité
- Étapes pour reproduire
- Impact potentiel (confidentialité, intégrité, disponibilité)
- Version de Tawiza concernée
- Suggestion de correction (si applicable)

### Sévérité

| Niveau | Exemples | Délai de correction |
|--------|----------|---------------------|
| **Critique** | Exécution de code à distance, contournement auth | 48h |
| **Haute** | Injection SQL, SSRF, escalade de privilèges | 7 jours |
| **Moyenne** | XSS stocké, CSRF, fuite d'information | 14 jours |
| **Basse** | XSS réfléchi, headers manquants | Prochaine release |

## Bonnes pratiques de sécurité

### Pour les contributeurs

- **Jamais** de secrets dans le code (API keys, mots de passe, tokens)
- Utiliser les variables d'environnement via `.env` (gitignore)
- Valider et assainir toutes les entrées utilisateur
- Utiliser des requêtes paramétrées (pas de concaténation SQL)
- Exécuter `ruff` et `bandit` avant chaque PR
- Les hooks pre-commit incluent `gitleaks` (scanning de secrets) et `detect-private-key`

### Pour les utilisateurs

- Changer **tous** les mots de passe par défaut avant déploiement (`SECRET_KEY`, DB password)
- Utiliser HTTPS en production (avec un reverse proxy comme Caddy ou nginx)
- Limiter l'accès réseau aux ports nécessaires
- Mettre à jour régulièrement (Dependabot envoie des PRs de sécurité automatiquement)
- Configurer `TELEMETRY_ENABLED=false` si vous ne souhaitez pas de télémétrie anonyme

### Outils de sécurité intégrés

```bash
# Scanner le code Python pour les vulnérabilités
bandit -r src/ -ll

# Détecter les secrets accidentels (via pre-commit)
gitleaks detect --source .

# Linter sécurité + qualité
ruff check src/
```

### Protection de la branche main

- CI (tests + lint) doit passer avant merge
- Scanning de secrets automatique (gitleaks en pre-commit)
- Dependabot pour les mises à jour de sécurité (pip, npm, Docker, GitHub Actions)

## Versions supportées

| Version | Support sécurité |
|---------|-----------------|
| 0.x (beta) | Oui  -  correctifs de sécurité actifs |

## Dépendances

Nous utilisons [Dependabot](https://docs.github.com/en/code-security/dependabot) pour les mises à jour automatiques de sécurité des dépendances Python (pip), JavaScript (npm), Docker, et GitHub Actions. Les PRs de sécurité sont traitées en priorité.
