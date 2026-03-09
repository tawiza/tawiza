# Politique de Securite — Tawiza

## Signaler une vulnerabilite

Si vous decouvrez une vulnerabilite de securite dans Tawiza, **merci de ne PAS ouvrir une issue publique**.

### Processus de signalement

1. **Email** : Envoyez un rapport detaille a **security@tawiza.fr** (ou via le profil GitHub du mainteneur)
2. **Delai** : Nous accusons reception sous 48h
3. **Correction** : Nous visons un correctif sous 7 jours pour les vulnerabilites critiques
4. **Disclosure** : Nous coordonnons la divulgation publique avec vous
5. **Credit** : Les reporters sont credites dans le CHANGELOG (sauf demande contraire)

### Informations a inclure

- Description de la vulnerabilite
- Etapes pour reproduire
- Impact potentiel (confidentialite, integrite, disponibilite)
- Version de Tawiza concernee
- Suggestion de correction (si applicable)

### Severite

| Niveau | Exemples | Delai de correction |
|--------|----------|---------------------|
| **Critique** | Execution de code a distance, contournement auth | 48h |
| **Haute** | Injection SQL, SSRF, escalade de privileges | 7 jours |
| **Moyenne** | XSS stocke, CSRF, fuite d'information | 14 jours |
| **Basse** | XSS reflechi, headers manquants | Prochaine release |

## Bonnes pratiques de securite

### Pour les contributeurs

- **Jamais** de secrets dans le code (API keys, mots de passe, tokens)
- Utiliser les variables d'environnement via `.env` (gitignore)
- Valider et assainir toutes les entrees utilisateur
- Utiliser des requetes parametrees (pas de concatenation SQL)
- Executer `ruff` et `bandit` avant chaque PR
- Les hooks pre-commit incluent `gitleaks` (scanning de secrets) et `detect-private-key`

### Pour les utilisateurs

- Changer **tous** les mots de passe par defaut avant deploiement (`SECRET_KEY`, DB password)
- Utiliser HTTPS en production (avec un reverse proxy comme Caddy ou nginx)
- Limiter l'acces reseau aux ports necessaires
- Mettre a jour regulierement (Dependabot envoie des PRs de securite automatiquement)
- Configurer `TELEMETRY_ENABLED=false` si vous ne souhaitez pas de telemetrie anonyme

### Outils de securite integres

```bash
# Scanner le code Python pour les vulnerabilites
bandit -r src/ -ll

# Detecter les secrets accidentels (via pre-commit)
gitleaks detect --source .

# Linter securite + qualite
ruff check src/
```

### Protection de la branche main

- Reviews obligatoires sur toutes les PRs
- CI (tests + lint) doit passer avant merge
- Scanning de secrets automatique (gitleaks en pre-commit)
- Dependabot pour les mises a jour de securite (pip, npm, Docker, GitHub Actions)

## Versions supportees

| Version | Support securite |
|---------|-----------------|
| 0.x (beta) | Oui — correctifs de securite actifs |

## Dependances

Nous utilisons [Dependabot](https://docs.github.com/en/code-security/dependabot) pour les mises a jour automatiques de securite des dependances Python (pip), JavaScript (npm), Docker, et GitHub Actions. Les PRs de securite sont traitees en priorite.
