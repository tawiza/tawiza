# Politique de Securite - Tawiza

## Signaler une vulnerabilite

Si vous decouvrez une vulnerabilite de securite dans Tawiza, **merci de ne PAS ouvrir une issue publique**.

### Processus de signalement

1. **Email** : Envoyez un rapport detaille a l'adresse indiquee dans le profil du mainteneur
2. **Delai** : Nous nous engageons a accuser reception sous 48h
3. **Correction** : Nous visons un correctif sous 7 jours pour les vulnerabilites critiques
4. **Disclosure** : Nous coordonnerons la divulgation publique avec vous

### Informations a inclure

- Description de la vulnerabilite
- Etapes pour reproduire
- Impact potentiel
- Suggestion de correction (si applicable)

## Bonnes pratiques de securite

### Pour les contributeurs

- **Jamais** de secrets dans le code (API keys, mots de passe, tokens)
- Utiliser les variables d'environnement via `.env` (gitignore)
- Valider toutes les entrees utilisateur
- Utiliser des requetes parametrees (pas de concatenation SQL)
- Executer `ruff` et `bandit` avant chaque PR

### Pour les utilisateurs

- Changer **tous** les mots de passe par defaut avant deploiement
- Utiliser HTTPS en production
- Configurer un reverse proxy (Caddy, nginx) devant l'application
- Limiter l'acces reseau aux ports necessaires
- Mettre a jour regulierement les dependances

### Outils de securite integres

```bash
# Scanner le code Python pour les vulnerabilites
bandit -r src/ -ll

# Detecter les secrets accidentels
detect-secrets scan --baseline .secrets.baseline

# Linter securite + qualite
ruff check src/
```

## Versions supportees

| Version | Support securite |
|---------|-----------------|
| 0.x     | En cours         |

## Dependances

Nous utilisons Dependabot pour les mises a jour automatiques de securite.
Les PRs de securite sont traitees en priorite.
