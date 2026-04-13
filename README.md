# Internship Email Campaign Manager

This project provides both a **modern web interface** and **command-line tools** to automatically generate and send personalized internship request emails to startups using AI (Google Gemini).

## 🌟 Features

### Web Interface
- 📊 **Dashboard** - Vue d'ensemble de votre campagne avec statistiques
- 📝 **Gestion du CV** - Éditez vos informations personnelles, formation, compétences et expériences
- 🏢 **Gestion des Startups** - Ajoutez, modifiez et supprimez des entreprises cibles
- ✉️ **Génération d'Emails** - Générez automatiquement des emails personnalisés avec Gemini AI
- 📧 **Envoi d'Emails** - Envoyez vos emails individuellement ou en lot
- 📈 **Suivi** - Suivez l'historique de vos envois et candidatures

### Command Line
- Scripts Python autonomes pour la génération et l'envoi d'emails
- Parfait pour l'automatisation et les tâches planifiées

## 🚀 Installation Rapide

### 1. Python Setup
```powershell
# Créer l'environnement virtuel Python
python -m venv .venv

# Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# Installer les dépendances Python
pip install -r requirements.txt
```

### 2. Node.js Setup (pour l'interface web)
```powershell
# Installer les dépendances Node.js
npm install
```

### 3. Configuration
Créez un fichier `.env` avec vos credentials :
```env
# Google Gemini API
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-pro

# Gmail Configuration (pour l'envoi)
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password

# Server Configuration
PORT=3000
PYTHON_PATH=.\.venv\Scripts\python.exe
```

## 🎯 Utilisation

### Option 1: Interface Web (Recommandé)

1. **Démarrer le serveur**
```powershell
npm start
```

2. **Accéder à l'interface**
Ouvrez votre navigateur et allez sur `http://localhost:3000`

3. **Workflow**
   - Éditez votre CV dans la section "CV"
   - Ajoutez des startups cibles dans la section "Startups"
   - Générez les emails dans la section "Emails"
   - Sélectionnez et envoyez les emails

### Option 2: Ligne de Commande

1. **Générer les emails**
```powershell
python generate_emails.py
```

2. **Envoyer les emails**
```powershell
python send_emails.py
```

## 📁 Structure du Projet

```
internship/
├── public/                    # Interface web
│   ├── index.html            # Page principale
│   ├── app.js                # Logique frontend
│   └── styles.css            # Styles CSS
├── server.js                 # Serveur Express API
├── package.json              # Dépendances Node.js
├── generate_emails.py        # Script de génération d'emails
├── send_emails.py            # Script d'envoi d'emails
├── resume.json              # Vos données de CV
├── startups.json            # Liste des startups cibles
├── generated_emails.json    # Emails générés
├── email_tracking.json      # Suivi des envois
├── requirements.txt         # Dépendances Python
└── .env                     # Variables d'environnement
```

## 🔧 API Endpoints

Le serveur Express expose les endpoints suivants :

- `GET /api/stats` - Statistiques du dashboard
- `GET /api/resume` - Récupérer le CV
- `PUT /api/resume` - Mettre à jour le CV
- `GET /api/startups` - Liste des startups
- `POST /api/startups` - Ajouter une startup
- `PUT /api/startups/:id` - Modifier une startup
- `DELETE /api/startups/:id` - Supprimer une startup
- `GET /api/emails` - Liste des emails générés
- `PUT /api/emails/:index` - Modifier un email
- `POST /api/generate-emails` - Générer des emails
- `POST /api/send-emails` - Envoyer des emails
- `GET /api/tracking` - Historique des envois

## 🔐 Configuration Gmail

Pour envoyer des emails via Gmail :

1. Activez la validation en deux étapes sur votre compte Google
2. Générez un mot de passe d'application : https://myaccount.google.com/apppasswords
3. Utilisez ce mot de passe dans `GMAIL_APP_PASSWORD`

## 📝 Format des Données

### resume.json
```json
{
  "name": "Votre Nom",
  "email": "votre@email.com",
  "phone": "+33612345678",
  "linkedin": "https://linkedin.com/in/yourprofile",
  "skills": ["Python", "JavaScript", "React"],
  "education": [
    {
      "degree": "Master Informatique",
      "institution": "Université",
      "year": "2024"
    }
  ],
  "experience": [
    {
      "title": "Développeur",
      "company": "Entreprise",
      "period": "2023-2024",
      "description": "Description"
    }
  ]
}
```

### startups.json
```json
{
  "data": [
    {
      "id": 1,
      "name": "Startup Name",
      "email": "contact@startup.com",
      "domain": "FinTech",
      "website": "https://startup.com",
      "description": "Description de la startup"
    }
  ]
}
```

## 🛠️ Technologies Utilisées

**Frontend:**
- HTML5, CSS3, JavaScript (Vanilla)
- Tailwind CSS
- Font Awesome

**Backend:**
- Node.js + Express
- Python 3.x

**AI & Services:**
- Google Gemini API
- Gmail SMTP

## 📊 Développement

Mode développement avec auto-reload :
```powershell
npm run dev
```

## 🤝 Contribution

N'hésitez pas à contribuer au projet en ouvrant des issues ou pull requests !

## 📄 Licence

ISC
