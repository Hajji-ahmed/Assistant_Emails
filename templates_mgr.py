"""Manage the prompt-template gallery.

Each template is stored as a plain-text file under `prompts/`, plus a metadata
entry in `config["prompts"]["list"]`:
    { "id": "...", "name": "...", "kind": "campaign" | "followup", "file": "prompts/<id>.txt" }

`config["prompts"]["active"]` is the id used by the main "Generate" flow,
`config["prompts"]["active_followup"]` is the id used by follow-up sends.
"""
import re
from pathlib import Path

from config import load_config, save_config

BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
LEGACY_TEMPLATE = BASE_DIR / "prompt_template.txt"

DEFAULT_FOLLOWUP_BODY = """Tu es chargé de rédiger un email de RELANCE suite à un premier email resté sans réponse.

Contraintes strictes :
- L'email doit être court : 80 à 120 mots maximum.
- Ton : poli, respectueux, non insistant.
- Aucune culpabilisation, aucune pression.
- Format : texte brut uniquement.

Structure obligatoire :

1. Objet : Re: Votre intérêt pour nos solutions IA — {EntrepriseName}

2. Introduction (1 phrase) :
"Bonjour, je me permets de revenir vers vous concernant mon précédent message à propos des solutions IA et développement que nous pourrions proposer à {EntrepriseName}."

3. Corps (2 phrases max) :
- Rappeler brièvement en 1 phrase la valeur proposée.
- Préciser qu'un échange rapide (15 minutes) suffirait à répondre à toute question.

4. Appel à l'action (1 phrase) :
Proposer 2 créneaux d'échange ou inviter à répondre simplement « oui » pour organiser un échange.

5. Conclusion (1 phrase) :
Remercier pour le temps accordé et souhaiter une bonne continuation.

6. Signature :
{Signature}
"""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "template"


def ensure_prompts_layout() -> dict:
    """Create the prompts/ folder + seed the default + followup templates if missing.
    Returns the updated config.
    """
    PROMPTS_DIR.mkdir(exist_ok=True)
    cfg = load_config()
    prompts = cfg.setdefault("prompts", {})
    prompts.setdefault("list", [])
    prompts.setdefault("active", "default")
    prompts.setdefault("active_followup", "followup")

    ids = {t["id"] for t in prompts["list"]}

    # Seed "default" from the legacy prompt_template.txt if both missing from config
    if "default" not in ids:
        default_file = PROMPTS_DIR / "default.txt"
        if not default_file.exists():
            # Migrate from the legacy root-level file if present
            if LEGACY_TEMPLATE.exists():
                default_file.write_text(LEGACY_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                default_file.write_text("Tu es un assistant. Rédige un email pour {EntrepriseName}.\n\n{Signature}", encoding="utf-8")
        prompts["list"].append({
            "id": "default",
            "name": "Campagne principale",
            "kind": "campaign",
            "file": "prompts/default.txt",
        })

    # Seed "followup"
    if "followup" not in ids:
        followup_file = PROMPTS_DIR / "followup.txt"
        if not followup_file.exists():
            followup_file.write_text(DEFAULT_FOLLOWUP_BODY, encoding="utf-8")
        prompts["list"].append({
            "id": "followup",
            "name": "Relance 7j",
            "kind": "followup",
            "file": "prompts/followup.txt",
        })

    save_config(cfg)
    return cfg


def list_templates(cfg: dict):
    return cfg.get("prompts", {}).get("list", [])


def get_meta(cfg: dict, template_id: str):
    for t in list_templates(cfg):
        if t["id"] == template_id:
            return t
    return None


def load_body(cfg: dict, template_id: str) -> str:
    meta = get_meta(cfg, template_id)
    if not meta:
        raise KeyError(f"Template introuvable : {template_id}")
    path = BASE_DIR / meta["file"]
    return path.read_text(encoding="utf-8")


def save_body(cfg: dict, template_id: str, body: str) -> None:
    meta = get_meta(cfg, template_id)
    if not meta:
        raise KeyError(f"Template introuvable : {template_id}")
    (BASE_DIR / meta["file"]).write_text(body, encoding="utf-8")


def create_template(cfg: dict, name: str, kind: str = "campaign", body: str = "") -> dict:
    PROMPTS_DIR.mkdir(exist_ok=True)
    base_slug = _slugify(name)
    slug = base_slug
    existing_ids = {t["id"] for t in list_templates(cfg)}
    n = 2
    while slug in existing_ids:
        slug = f"{base_slug}-{n}"
        n += 1
    file_rel = f"prompts/{slug}.txt"
    (BASE_DIR / file_rel).write_text(body or "", encoding="utf-8")
    meta = {"id": slug, "name": name, "kind": kind, "file": file_rel}
    cfg.setdefault("prompts", {}).setdefault("list", []).append(meta)
    save_config(cfg)
    return meta


def delete_template(cfg: dict, template_id: str) -> bool:
    prompts = cfg.setdefault("prompts", {})
    items = prompts.setdefault("list", [])
    for i, t in enumerate(items):
        if t["id"] == template_id:
            path = BASE_DIR / t["file"]
            if path.exists():
                path.unlink()
            items.pop(i)
            # Reset active pointers if they referenced the removed template
            if prompts.get("active") == template_id:
                prompts["active"] = next((x["id"] for x in items if x["kind"] == "campaign"), None)
            if prompts.get("active_followup") == template_id:
                prompts["active_followup"] = next((x["id"] for x in items if x["kind"] == "followup"), None)
            save_config(cfg)
            return True
    return False


def rename_template(cfg: dict, template_id: str, new_name: str) -> bool:
    meta = get_meta(cfg, template_id)
    if not meta:
        return False
    meta["name"] = new_name
    save_config(cfg)
    return True
