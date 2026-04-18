---
name: jobzyn-style
description: Design system local au projet Internship Email Manager, inspiré de jobzyn.com/fr/companies. Utilise ce skill quand l'user demande de refaire/améliorer le design d'une page du frontend Flask (templates/*.html + static/css/main.css) pour ressembler à Jobzyn.
---

# Skill : Style Jobzyn — local au projet

Ce skill s'applique **uniquement** au projet `internship` (email campaign manager Flask). Il transpose l'esthétique de [jobzyn.com/fr/companies](https://www.jobzyn.com/fr/companies) sur les pages existantes.

## Contexte technique du projet

- Stack : Flask + Jinja + vanilla CSS (pas Tailwind, pas React)
- Fichiers à toucher : `templates/*.html`, `static/css/main.css`
- Le design actuel est déjà **sobre et clair** (navbar blanche, palette neutre + accents). Ne pas tout refaire — **étendre** vers le style Jobzyn.
- Les variables CSS `--st-bg` / `--st-fg` / `--st-dot` sont déjà utilisées pour le pipeline CRM. Garder cette approche.

## Identité visuelle Jobzyn à reproduire

### Palette (à ajouter en tête de main.css comme custom properties)

```css
:root {
    --jz-bg: #f8fafc;              /* Fond de page (gris-bleu très clair) */
    --jz-surface: #ffffff;          /* Cartes et navbar */
    --jz-border: #e2e8f0;           /* Bordures discrètes */
    --jz-text: #0f172a;             /* Texte principal, très foncé */
    --jz-text-muted: #64748b;       /* Texte secondaire */
    --jz-primary: #1e40af;          /* Bleu profond Jobzyn-like */
    --jz-primary-hover: #1e3a8a;
    --jz-accent: #f97316;           /* Orange pour offres/badges d'action */
    --jz-accent-bg: #fff7ed;
    --jz-success: #059669;
    --jz-radius: 12px;              /* Jobzyn utilise du rounded généreux */
    --jz-radius-pill: 999px;
    --jz-shadow-card: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
    --jz-shadow-hover: 0 4px 12px rgba(15, 23, 42, 0.08);
}
```

### Typographie
- `font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;`
- Titre de page : `28px` bold, `letter-spacing: -0.02em`
- Tagline hero : `18px` regular, `color: var(--jz-text-muted)`
- Carte — nom d'entreprise : `16px` semibold
- Carte — description : `14px` regular, `line-height: 1.5`
- Meta (ville, secteur) : `13px` regular, `var(--jz-text-muted)`

### Layout général
- Page = `background: var(--jz-bg)` (pas blanc pur, toujours un gris-bleu très léger)
- Navbar blanche déjà en place → garder
- Hero section en haut de `/` et `/startups` : titre centré + tagline + barre de filtres
- Contenu en `max-width: 1280px` centré (déjà en place dans `.content`)

## Composants à produire

### 1. Hero section (à ajouter sur le Dashboard et `/startups`)

```html
<section class="hero">
    <h1 class="hero-title">Votre prochaine opportunité<br>est à un clic.</h1>
    <p class="hero-subtitle">Gérez votre campagne de candidatures de bout en bout.</p>
    <!-- optionnel: une search bar ici -->
</section>
```

```css
.hero {
    text-align: center;
    padding: 48px 24px 32px;
    margin-bottom: 32px;
}
.hero-title {
    font-size: 28px; font-weight: 700; color: var(--jz-text);
    letter-spacing: -0.02em; line-height: 1.2;
}
.hero-subtitle {
    font-size: 18px; color: var(--jz-text-muted); margin-top: 12px;
}
```

### 2. Grille de cartes (remplacer les tableaux/listes par des cards sur `/startups` et `/emails`)

**Signature d'une carte** (utiliser pour les startups ET pour les emails générés) :

```html
<article class="jz-card">
    <header class="jz-card-header">
        <div class="jz-avatar">AC</div>  <!-- initiales ou logo -->
        <div class="jz-card-titles">
            <h3 class="jz-card-title">ACME Maroc</h3>
            <p class="jz-card-meta">
                <span class="jz-meta-item">📍 Casablanca</span>
                <span class="jz-meta-item">FinTech</span>
            </p>
        </div>
    </header>
    <p class="jz-card-desc">Première description en ~100 caractères max…</p>
    <footer class="jz-card-footer">
        <span class="jz-badge jz-badge-primary">26 offres</span>
        <a href="#" class="jz-link">Voir plus →</a>
    </footer>
</article>
```

**Important** : ne pas remplacer `.icon 📍` par un emoji dans le rendu final. Utiliser un SVG inline ou une entité Unicode sobre (`◉`, `◆`) OU un pseudo-élément `::before` avec un SVG en `background-image` (pattern Jobzyn).

```css
.jz-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 20px;
}
.jz-card {
    background: var(--jz-surface);
    border: 1px solid var(--jz-border);
    border-radius: var(--jz-radius);
    padding: 20px;
    box-shadow: var(--jz-shadow-card);
    transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
    display: flex; flex-direction: column; gap: 12px;
}
.jz-card:hover {
    box-shadow: var(--jz-shadow-hover);
    transform: translateY(-2px);
    border-color: #cbd5e1;
}
.jz-card-header { display: flex; gap: 12px; align-items: flex-start; }
.jz-avatar {
    width: 44px; height: 44px; border-radius: 10px;
    background: linear-gradient(135deg, #dbeafe, #bfdbfe);
    color: var(--jz-primary);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 15px; flex-shrink: 0;
}
.jz-card-title {
    font-size: 16px; font-weight: 600; color: var(--jz-text);
    margin-bottom: 4px;
}
.jz-card-meta {
    display: flex; gap: 12px; flex-wrap: wrap;
    font-size: 13px; color: var(--jz-text-muted);
}
.jz-card-desc {
    font-size: 14px; color: var(--jz-text); line-height: 1.5;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden;
}
.jz-card-footer {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: auto; padding-top: 12px;
    border-top: 1px solid var(--jz-border);
}
```

### 3. Badges (pour secteurs, compteurs, statuts)

```css
.jz-badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: var(--jz-radius-pill);
    font-size: 12px; font-weight: 500;
    background: var(--jz-border); color: var(--jz-text-muted);
}
.jz-badge-primary { background: #dbeafe; color: var(--jz-primary); }
.jz-badge-accent  { background: var(--jz-accent-bg); color: var(--jz-accent); }
.jz-badge-success { background: #d1fae5; color: var(--jz-success); }
```

**Mapping avec l'existant** : les statuts CRM actuels (`.status-sent`, `.status-replied`, etc.) peuvent devenir des `.jz-badge` sans casser la logique — juste updater les tokens de couleur.

### 4. Barre de filtres horizontale (remplacer les `.status-filter` sur `/emails`)

```html
<div class="jz-filterbar">
    <button class="jz-chip active">Tous (169)</button>
    <button class="jz-chip">Envoyé (142)</button>
    <button class="jz-chip">Répondu (12)</button>
    ...
</div>
```

```css
.jz-filterbar {
    display: flex; flex-wrap: wrap; gap: 8px;
    margin-bottom: 24px; padding: 8px;
    background: var(--jz-surface);
    border: 1px solid var(--jz-border);
    border-radius: var(--jz-radius);
}
.jz-chip {
    padding: 8px 16px; border-radius: var(--jz-radius-pill);
    border: 1px solid transparent; background: transparent;
    font-size: 13px; font-weight: 500; color: var(--jz-text-muted);
    cursor: pointer; font-family: inherit;
}
.jz-chip:hover { background: var(--jz-bg); color: var(--jz-text); }
.jz-chip.active {
    background: var(--jz-primary); color: #fff;
}
```

### 5. Boutons (override des `.btn` existants)

Les boutons actuels (`.btn`, `.btn-primary`) sont déjà OK mais peuvent être densifiés :

```css
.btn-primary {
    background: var(--jz-primary);
    border-color: var(--jz-primary);
    font-weight: 600;
}
.btn-primary:hover {
    background: var(--jz-primary-hover);
    border-color: var(--jz-primary-hover);
}
.btn {
    font-weight: 500;
}
```

### 6. Bouton "Charger plus" (pattern Jobzyn pour pagination infinie)

```html
<button class="btn jz-load-more">Charger plus</button>
```

```css
.jz-load-more {
    display: block; margin: 32px auto 0;
    padding: 12px 32px; border-radius: var(--jz-radius-pill);
    font-weight: 600;
}
```

## Mapping page par page

### `/` (Dashboard)
- Ajouter `<section class="hero">` avant les stat cards
- Les stat cards existantes deviennent des `.jz-card` (padding + shadow + avatar optionnel avec l'icône du stat)
- Le pipeline bar reste, mais border-radius → `var(--jz-radius)`

### `/startups`
- Remplacer **le tableau** par une **grille de cartes** `.jz-grid` avec `.jz-card`
- L'avatar affiche les 2 premières lettres d'`EntrepriseName`
- La description est `EntrepriseSecteurActivite`
- La meta : ville + techno
- Le footer : badge avec le nombre d'emails générés pour cette entreprise, ou "Aucun email" si pas généré
- Le search + pager existants restent en haut
- Bouton "+ Ajouter" → ouvre une modale (ou reste une ligne éditable, au choix)

### `/emails`
- Remplacer la **liste d'accordéons** par une grille de cartes
- Cliquer sur une carte → ouvre une modale ou redirige vers `/emails/<index>` avec la vue détail
- Badge statut CRM en haut à droite de chaque carte
- Aperçu des 2 premières lignes du corps
- Meta : entreprise + date envoi + template utilisé

### `/config` et `/prompt`
- Forment des "dossiers" → garder les `.form-card` mais avec `border-radius: var(--jz-radius)` (12px au lieu de 8px)
- Ajouter un hero léger en haut : titre + une phrase explicative

## Règles strictes

1. **Pas de Tailwind** — tout en CSS custom dans `main.css` (le projet utilise des classes nommées).
2. **Préfixer les nouvelles classes `.jz-`** pour les isoler des classes legacy (`.btn`, `.stat-card`, etc.) et permettre un rollback.
3. **Responsive obligatoire** : toutes les grilles en `repeat(auto-fill, minmax(280px, 1fr))` pour que ça stack tout seul en mobile.
4. **Pas d'emoji dans le rendu final** — Jobzyn utilise des icônes SVG. Pour rester simple sans lib d'icônes, utiliser des pseudo-éléments avec SVG en `background-image` encodé URL.
5. **Conserver l'accessibilité acquise** : `:focus-visible`, `aria-label`, association `label[for]/input[id]`.
6. **Garder le JobManager, les endpoints API, la logique métier** — ce skill concerne UNIQUEMENT la couche visuelle.

## Ordre d'implémentation recommandé

1. **Tokens** : ajouter `:root` avec les variables Jobzyn en tête de `main.css`
2. **Hero** : composant partagé à inclure dans `base.html` via un block Jinja
3. **Cards** : classes `.jz-card`, `.jz-grid`, `.jz-avatar`, etc.
4. **Refactor `/startups`** : tableau → grille (incrémental, possibilité de garder le mode tableau derrière un toggle)
5. **Refactor `/emails`** : liste → grille + modal de détail
6. **Tune** : badges, filterbar, boutons

## Ne PAS faire

- ❌ Changer la navbar (elle est déjà propre et light → cohérent avec Jobzyn)
- ❌ Remplacer le CSS existant en bloc — faire des additions pour permettre rollback
- ❌ Ajouter de dépendances frontend (lucide-react, daisyUI, etc.) — rester vanilla
- ❌ Toucher au backend (Flask, jobs, API) dans le cadre de ce skill
- ❌ Sur-colorier — Jobzyn reste très neutre, le bleu est réservé aux CTAs et compteurs primaires
