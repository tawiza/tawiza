---
title: "CI failure on main"
labels: ci-failure, bug
---

Un workflow CI a échoué sur `main`.

## Run en échec

- **Workflow** : {{ env.WORKFLOW }}
- **Run** : [#{{ env.RUN_NUMBER }}]({{ env.RUN_URL }})
- **Commit** : [`{{ env.SHORT_SHA }}`]({{ env.COMMIT_URL }}) par @{{ env.ACTOR }}
- **Date** : {{ env.DATE }}

## Jobs en échec

```
{{ env.FAILED_JOBS }}
```

## Actions

1. Ouvrir le run via le lien ci-dessus
2. Identifier le job rouge et la première erreur
3. Soit fixer sur `main` (si trivial), soit ouvrir une PR de fix
4. Fermer cette issue une fois le prochain run vert

> Cette issue est créée et mise à jour automatiquement par `.github/workflows/ci.yml`.
> Si elle reste ouverte alors que la CI est verte depuis 24h, fermez-la manuellement.
