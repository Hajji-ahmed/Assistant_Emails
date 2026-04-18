# Internship Email Campaign Manager

Outil personnel pour gérer une campagne d'emails de recherche de stage : génération automatique via **OpenAI**, envoi via **Gmail SMTP**, détection des réponses via **IMAP**, pipeline CRM, relances automatiques, le tout dans une interface web Flask.

---

## Sommaire

1. [Vue d'ensemble](#vue-densemble)
2. [Installation et lancement](#installation-et-lancement)
3. [Configuration](#configuration)
4. [Fonctionnalités](#fonctionnalités)
5. [Workflow typique](#workflow-typique)
6. [Architecture](#architecture)
7. [Structure du projet](#structure-du-projet)
8. [API interne](#api-interne)
9. [Stockage et données](#stockage-et-données)
10. [Dépannage](#dépannage)

---

## Vue d'ensemble

**Quoi ?** Tu charges une liste d'entreprises → l'app rédige un email personnalisé pour chacune via OpenAI → envoie via ton compte Gmail → détecte les réponses → tu suis l'avancement dans un pipeline CRM.

**Pour qui ?** Un usage **personnel local** (campagne de recherche de stage, prospection commerciale individuelle). Pas multi-utilisateur, pas destiné à être exposé sur internet.

**Stack** : Python 3.11+, Flask, OpenAI, Gmail SMTP + IMAP, stockage JSON.

---

## Installation et lancement

### Prérequis
- Python 3.11+
- Un compte Gmail avec **double authentification** activée
- Un mot de passe d'application Gmail ([https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords))
- Une clé API OpenAI ([https://platform.openai.com/api-keys](https://platform.openai.com/api-keys))

### Mise en place

```powershell
# 1. Créer l'environnement virtuel
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Premier bootstrap (optionnel) : copier .env.example → .env et remplir
cp .env.example .env
```

### Lancer l'app

```powershell
python app.py
```

Ouvre `http://localhost:8000` dans le navigateur.

Si le port 8000 est bloqué (Hyper-V / WSL réservent parfois des plages), définir un autre port :

```powershell
$env:PORT=5555 ; python app.py
```

### Dépendances

```
flask>=3.0.0
openai>=1.40.0
python-dotenv>=0.19.0
requests>=2.31.0
```

---

## Configuration

### Source de vérité : `config.json`

Au **premier lancement**, l'app lit `.env` et génère `config.json` avec les valeurs initiales. Ensuite, **`config.json` devient la seule source** — tu édites via la page `/config` de l'UI, plus par le fichier `.env` (qui est ignoré après le bootstrap).

Un warning apparaît sur `/config` si tu modifies `.env` manuellement et que les valeurs divergent de `config.json`.

### Sections de `config.json`

```json
{
  "openai": {
    "api_key": "sk-...",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
    "max_tokens": 500
  },
  "smtp": {
    "user": "you@gmail.com",
    "password": "xxxx xxxx xxxx xxxx",
    "server": "smtp.gmail.com",
    "port": 465
  },
  "imap": {
    "server": "imap.gmail.com",
    "port": 993,
    "lookback_days": 60
  },
  "sending": {
    "send_delay_seconds": 2,
    "daily_limit": 100
  },
  "followups": {
    "delay_days": 7
  },
  "profile": {
    "sender_display_name": "Hajji Ahmed",
    "resume_link": "https://drive.google.com/...",
    "phone": "+212 ...",
    "linkedin": "https://linkedin.com/...",
    "github": "https://github.com/...",
    "signature": "Cordialement,\nAhmed Hajji\n..."
  },
  "prompts": {
    "active": "default",
    "active_followup": "followup",
    "list": [
      {"id": "default", "name": "Campagne principale", "kind": "campaign", "file": "prompts/default.txt"},
      {"id": "followup", "name": "Relance 7j", "kind": "followup", "file": "prompts/followup.txt"}
    ]
  },
  "files": {
    "startups": "startups.json",
    "resume": "resume.json",
    "generated_emails": "generated_emails.json",
    "tracking": "email_tracking.json",
    "prompt_template": "prompt_template.txt"
  }
}
```

### Gmail — activer IMAP

Pour que la détection des réponses fonctionne, IMAP doit être activé dans ton compte Gmail :
[https://mail.google.com/mail/u/0/#settings/fwdandpop](https://mail.google.com/mail/u/0/#settings/fwdandpop) → onglet "Transfert et POP/IMAP" → activer IMAP.

---

## Fonctionnalités

### 1. Génération d'emails personnalisés

Chaque startup de `startups.json` reçoit un email généré par OpenAI à partir d'un **template avec variables** (`{EntrepriseName}`, `{EntrepriseVille}`, `{Signature}`, etc.).

- Page `/prompt` : éditeur de template avec liste des variables disponibles et preview
- Plusieurs templates possibles (gallery) — voir [Templates multiples](#templates-multiples-gallery)
- Skip automatique des entreprises déjà générées
- Arrêt propre si quota OpenAI atteint

### 2. Envoi SMTP avec rate limiting

- Configuration **rate limit** (délai entre envois, défaut 2s)
- **Cap quotidien** configurable (défaut 100 emails/jour, 0 = illimité)
- Retries automatiques (3 tentatives avec backoff)
- Compteur d'envoi quotidien (reset à minuit)
- **Annulation en cours de batch** sans attendre la fin

### 3. Détection des réponses via IMAP

Bouton "Vérifier les réponses" sur le dashboard :
- Connecte à ta boîte Gmail en IMAP
- Pour chaque email envoyé sans réponse connue, cherche dans INBOX une réponse de l'adresse du contact (FROM + SINCE 60 jours)
- Extrait sujet, auteur, date, aperçu du corps (nettoyé des citations)
- Affiche un badge **"Répondu"** bleu sur l'email concerné
- Carte stats "Réponses" sur le dashboard avec taux de réponse

### 4. Pipeline CRM à 7 statuts

Chaque email a un statut :
- **Brouillon** (auto) — généré mais pas envoyé
- **Envoyé** (auto) — dans `sent_emails`
- **Répondu** (auto) — réponse détectée par IMAP
- **Entretien** (manuel)
- **Offre** (manuel)
- **Refus** (manuel)
- **Abandonné** (manuel)

- Dropdown coloré sur chaque email pour changer le statut
- Filtre par statut (tabs en haut de `/emails`)
- Carte "Pipeline par statut" sur le dashboard avec barre proportionnelle

### 5. Templates multiples (gallery)

Sur `/prompt` :
- Sidebar avec liste de tous les templates, badge `Campagne` ou `Relance`
- Créer un nouveau template, l'éditer, le supprimer
- Activer un template comme "actif" pour son kind
- Le template actif "campaign" est utilisé par "Générer", le "followup" par les relances

### 6. Relances automatiques

- Pour chaque email envoyé il y a plus de N jours (défaut 7) sans réponse, une relance peut être envoyée
- Bouton "Envoyer relances (N)" sur le dashboard — N = nombre de relances dues
- Utilise le template `followup` actif (différent du template campagne principal)
- Même rate limit + cap quotidien que l'envoi normal
- Une entreprise n'est relancée qu'**une seule fois** (pas de re-relance automatique)

### 7. Test → moi avant d'envoyer

Bouton "Test → moi" sur chaque email → envoie l'email à ta propre adresse (avec le préfixe `[TEST]` dans le sujet) **sans** marquer comme envoyé. Utile pour vérifier le rendu final avant d'envoyer au vrai destinataire.

### 8. Test des credentials

- Bouton "Tester OpenAI" sur `/config` → émet une requête minimale (1 token)
- Bouton "Tester SMTP" sur `/config` → login + logout sans envoyer d'email
- Permet de vérifier les clés avant de lancer une campagne

### 9. Reset granulaire

Sur `/emails`, possibilité de :
- Cocher des emails → "Retirer des envois" ou "Retirer du suivi génération"
- Sur un email envoyé, bouton individuel "Marquer non envoyé"
- Les boutons dashboard font la version "tout d'un coup"

### 10. Journal en temps réel

Tout job long (générer, envoyer, relances, vérification IMAP) s'affiche dans un journal live (SSE) avec :
- Horodatage de chaque événement
- Log clair des actions
- Bouton "Annuler" à tout moment
- Log persiste après redémarrage du job (buffer en mémoire par job)

---

## Workflow typique

### Campagne initiale

1. **[/config]** — Renseigner OpenAI key, Gmail, signature. Tester les deux.
2. **[/startups]** — Importer ou éditer la liste des entreprises cibles. Sauvegarder.
3. **[/prompt]** — Ajuster le template actif "Campagne principale". Prévisualiser.
4. **[Dashboard]** — Clic "Générer les emails" → journal live → tous les emails dans `/emails`.
5. **[/emails]** — Relire, éditer, supprimer les mauvais. Test → moi sur quelques-uns.
6. **[Dashboard]** — Clic "Envoyer (tous)" → journal live → cap quotidien respecté.

### Suivi quotidien

7. **[Dashboard]** — Clic "Vérifier les réponses" (1 fois par jour suffit).
8. **[/emails]** — Filtrer "Répondu" → lire les aperçus.
9. Pour les emails méritant un statut : changer le pill (ex: "Entretien").

### Relances automatiques

10. **[Dashboard]** — Au bout de 7 jours, la carte "Relances dues" passe en orange → clic "Envoyer relances (N)".

---

## Architecture

```
┌──────────────────────────────────────────┐
│          Flask app (app.py)              │
│  ┌─────────────────────────────────────┐ │
│  │  Routes HTML + API JSON             │ │
│  └───────────┬─────────────────────────┘ │
│              │                            │
│  ┌───────────▼──────────┐   ┌──────────┐ │
│  │  JobManager (jobs.py)│   │  Config  │ │
│  │  - 1 slot actif      │   │  (JSON)  │ │
│  │  - SSE streaming     │   └──────────┘ │
│  │  - Cancel event      │                 │
│  └───────────┬──────────┘                 │
└──────────────┼────────────────────────────┘
               │ target_fn(on_progress, should_stop)
     ┌─────────┼─────────┬──────────────┬──────────────┐
     ▼         ▼         ▼              ▼              ▼
┌─────────┐ ┌────────┐ ┌──────────┐ ┌───────────┐ ┌────────────┐
│generate │ │ send   │ │check_    │ │send_      │ │templates_  │
│_emails  │ │_emails │ │replies   │ │followups  │ │mgr         │
│(OpenAI) │ │(SMTP)  │ │(IMAP)    │ │(OpenAI+   │ │(prompts/)  │
│         │ │        │ │          │ │ SMTP)     │ │            │
└─────────┘ └────────┘ └──────────┘ └───────────┘ └────────────┘
```

### Choix d'architecture

- **Un seul job à la fois** : simplifie la cohérence des JSON (pas de race condition sur `email_tracking.json`).
- **Fichiers JSON au lieu de SQLite** : simple pour un usage perso, editable à la main si besoin, auto-versionnable. À migrer vers SQLite si > 1000 emails.
- **SSE au lieu de WebSocket** : unidirectionnel (serveur → client), suffisant pour un journal, plus simple à implémenter sous Flask dev.
- **`should_stop` callback** passé aux jobs long-running : annulation propre au prochain checkpoint sans `kill`.

---

## Structure du projet

```
internship/
├── app.py                     # Flask entrypoint — toutes les routes
├── config.py                  # load_config / save_config / detect_env_drift
├── jobs.py                    # JobManager single-slot avec cancel + SSE
├── generate_emails.py         # Génération via OpenAI (mode CLI + fonction importable)
├── send_emails.py             # Envoi SMTP (mode CLI + fonction importable)
├── send_followups.py          # Moteur de relances
├── check_replies.py           # Détection réponses via IMAP
├── templates_mgr.py           # Gallery de prompts (CRUD + active)
│
├── config.json                # ⛔ gitignored — secrets, runtime state
├── .env                       # ⛔ gitignored — seulement pour le bootstrap initial
├── .env.example               # template du .env
│
├── startups.json              # ⛔ gitignored — liste des entreprises cibles
├── resume.json                # ⛔ gitignored — ton CV
├── generated_emails.json      # ⛔ gitignored — emails générés (persistés)
├── email_tracking.json        # ⛔ gitignored — état runtime (sent, replies, etc.)
│
├── prompts/                   # Templates de prompts (gallery)
│   ├── default.txt            #   Template campagne principal
│   └── followup.txt           #   Template relance
│
├── templates/                 # Jinja HTML
│   ├── base.html              #   Layout (navbar + flash + blocks)
│   ├── dashboard.html         #   / — stats + actions + pipeline
│   ├── config.html            #   /config
│   ├── prompt.html            #   /prompt — gallery + éditeur
│   ├── startups.html          #   /startups — tableau éditable + pager
│   └── emails.html            #   /emails — liste + statuts + filtres
│
├── static/
│   ├── css/main.css           #   Styles (design sobre, palette neutre)
│   └── js/
│       ├── main.js            #   Toggle password, flash auto-dismiss
│       └── jobs.js            #   Client SSE réutilisable
│
├── requirements.txt
└── README.md                  # ← ce fichier
```

---

## API interne

Toutes les routes JSON renvoient `{ok: true}` ou `{ok: false, error: "..."}` sur les mutations.

### Pages HTML
| Route | Description |
|---|---|
| `GET /` | Dashboard |
| `GET /config` · `POST /config` | Configuration (lecture + enregistrement) |
| `GET /prompt` · `GET /prompt/<id>` | Gallery + éditeur de templates |
| `GET /startups` | Tableau éditable avec search/pager |
| `GET /emails` | Liste des emails avec statuts et filtres |

### Jobs (background + SSE)
| Endpoint | Effet |
|---|---|
| `POST /api/generate` | Lance la génération. Body `{template_id?: string}` |
| `POST /api/send` | Lance l'envoi. Body `{only?: string[]}` |
| `POST /api/check-replies` | Lance la vérification IMAP |
| `POST /api/send-followups` | Lance les relances automatiques |
| `GET /api/jobs/current` | Status du job courant (polling fallback) |
| `GET /api/jobs/<id>/stream` | Flux SSE des événements |
| `POST /api/jobs/<id>/cancel` | Signal d'annulation |

### Emails
| Endpoint | Effet |
|---|---|
| `PUT /api/emails/<index>` | Éditer sujet/corps/destinataire |
| `DELETE /api/emails/<index>` | Supprimer |
| `POST /api/emails/<index>/test-self` | Envoyer à soi-même |
| `POST /api/emails/clear` | Vider tous les emails (zone dangereuse) |

### Statuts CRM
| Endpoint | Effet |
|---|---|
| `PUT /api/status/<company>` | Body `{status: "interview"\|"offer"\|...}` |
| `DELETE /api/status/<company>` | Retire l'override manuel (retour à auto) |

### Startups
| Endpoint | Effet |
|---|---|
| `PUT /api/startups` | Remplace la liste complète (bulk save) |

### Tracking
| Endpoint | Effet |
|---|---|
| `POST /api/tracking/reset` | `{scope: "sent"\|"processed"\|"all", companies?: string[]}` |
| `DELETE /api/replies/<company>` | Retire une réponse stockée |

### Templates
| Endpoint | Effet |
|---|---|
| `GET /api/templates` | Liste |
| `POST /api/templates` | Créer `{name, kind, body}` |
| `PUT /api/templates/<id>` | Éditer `{body?, name?}` |
| `DELETE /api/templates/<id>` | Supprimer |
| `POST /api/templates/<id>/activate` | Marquer comme actif pour son kind |

### Tests de credentials
| Endpoint | Effet |
|---|---|
| `POST /api/test/openai` | `{api_key?, model?}` — 1 token vers OpenAI |
| `POST /api/test/smtp` | `{user?, password?, server?, port?}` — login + logout |

---

## Stockage et données

### `startups.json`

Format attendu (liste à plat dans `data`) :

```json
{
  "data": [
    {
      "Id": null,
      "EntrepriseName": "ACME",
      "EntrepriseVille": "Rabat",
      "EntrepriseTechnologie": "AI;FINTECH",
      "EntrepriseSecteurActivite": "BANQUE",
      "EntrepriseContactName": "Alice RH",
      "EntrepriseContactEmail": "alice@acme.ma",
      "EntrepriseContactPhone": "...",
      "EntrepriseContactSiteWeb": "https://acme.ma",
      "EntrepriseLogo": "..."
    }
  ]
}
```

### `generated_emails.json`

Liste plate d'emails :

```json
[
  {
    "company_name": "ACME",
    "company_location": "Rabat",
    "company_sector": "FinTech",
    "hr_name": "Alice RH",
    "hr_email": "alice@acme.ma",
    "email_subject": "Propositions IA & développement pour ACME",
    "email_body": "Bonjour,\n\nAujourd'hui...",
    "template_id": "default"
  }
]
```

### `email_tracking.json` — état runtime

```json
{
  "processed_companies": ["ACME"],
  "sent_emails": ["ACME"],
  "sent_dates": {"ACME": "2026-04-18T10:30:00+00:00"},
  "daily_counters": {"2026-04-18": 42},
  "replies": {
    "ACME": {
      "reply_date": "2026-04-19T14:32:00+00:00",
      "reply_subject": "Re: Propositions...",
      "reply_preview": "Bonjour Ahmed, merci...",
      "from": "alice@acme.ma"
    }
  },
  "followups_sent": {
    "ACME": {
      "sent_date": "2026-04-25T09:15:00+00:00",
      "subject": "Re: Votre intérêt...",
      "body_preview": "Bonjour, je me permets...",
      "template_id": "followup"
    }
  },
  "statuses": {"ACME": "interview"}
}
```

### Variables du template

Toute clé présente dans l'objet startup + `{Signature}` est accessible dans le prompt avec la syntaxe `{EntrepriseName}`. Les variables manquantes se résolvent en chaîne vide (fallback sûr).

---

## Dépannage

### "Port already in use" / WinError 10013
Windows (Hyper-V/WSL) réserve certaines plages. Change de port :
```powershell
$env:PORT=5555 ; python app.py
```
Voir les plages réservées :
```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```

### "Authentication failed" au test SMTP
- Vérifier que la **2FA est activée** sur le compte Google
- Générer un **mot de passe d'application** (pas le mot de passe Gmail)
- L'adresse dans `smtp.user` doit être le compte qui a généré le password

### IMAP ne trouve aucune réponse
- Vérifier qu'IMAP est activé dans les paramètres Gmail
- Vérifier que les réponses sont bien dans INBOX (pas filtrées dans un label)
- Essayer d'augmenter `imap.lookback_days` si les emails sont anciens

### "Aucun template de relance actif"
Sur `/prompt`, sélectionner un template de type "Relance" → cliquer "Activer ce template".

### Quota OpenAI atteint
L'app s'arrête proprement. Attendre le reset du quota (généralement 1 minute ou le renouvellement du plan) puis relancer "Générer" — les emails déjà générés sont skippés.

### config.json ne se met pas à jour
Les valeurs de `.env` ne sont lues qu'au **premier lancement** (quand `config.json` n'existe pas). Pour modifier, utiliser **la page `/config`** de l'UI.

---

## Ligne de commande (fallback)

Les modules restent utilisables sans UI :

```powershell
python generate_emails.py    # Génère avec le template actif
python send_emails.py        # Envoie tous les emails non envoyés
python check_replies.py      # Vérifie les réponses
python send_followups.py     # Envoie les relances dues
```

Utile pour automation (cron/tâches planifiées) ou debugging.

---

## Licence

Usage personnel. Pas de garantie.
