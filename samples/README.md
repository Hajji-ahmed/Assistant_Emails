# Samples d'import

Fichiers d'exemple pour tester l'import sur `/startups`.

> Règle : **l'email est le seul champ obligatoire**. Les autres champs sont auto-complétés via OpenAI à partir du domaine. Les nouvelles startups sont ajoutées **en haut** du fichier.

| Fichier | Format | Nb lignes | Test |
|---|---|---|---|
| `exemple-emails-seulement.csv` | CSV (1 colonne email) | 6 | **Import minimal : uniquement des emails, tout le reste est inféré par l'IA** |
| `exemple-startups-simple.csv` | CSV (colonnes FR) | 8 dont 1 sans email | Mapping flexible FR + skip des lignes sans email |
| `exemple-startups-anglais.csv` | CSV (colonnes EN) | 5 | Mapping `company/city/email/sector/phone` |
| `exemple-startups.json` | JSON `{data: [...]}` | 4 dont 1 doublon | Import JSON + dedup par email |

## Scénario de test recommandé

1. **Importer `exemple-startups-simple.csv`** → attend `7 importées · 1 ignorée (pas de nom)`
2. **Réimporter le même fichier** → attend `0 importées · 7 doublons`
3. **Importer `exemple-startups-anglais.csv`** → attend `5 importées`
4. **Importer `exemple-startups.json`** → attend `3 importées · 1 doublon` (Datawise Morocco)
5. **Renommer un `.docx` en `.xlsx` et uploader** → attend erreur "Format non supporté"

## Nettoyage

Après tests, pour retirer les startups ajoutées, tu peux soit :
- Éditer manuellement `startups.json` et supprimer les lignes
- Utiliser "Reset génération" sur le dashboard si tu as généré des emails pour elles
