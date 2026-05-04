"""Parse and map uploaded startup files (CSV, JSON) to the app's schema.

Philosophy:
- Be permissive: missing columns are stored as empty strings, not rejected.
- Be forgiving on column names: "Nom" / "Company" / "Entreprise" all map to
  EntrepriseName; accents, spaces, casing and separators are normalized.
"""
import csv
import io
import json
import re
import unicodedata

FIELD_ALIASES = {
    "EntrepriseName": [
        "entreprisename", "name", "nom", "company", "entreprise",
        "societe", "société", "nom_entreprise", "company_name",
    ],
    "EntrepriseContactEmail": [
        "entreprisecontactemail", "email", "mail", "e-mail", "contact_email",
        "contactemail", "adresse_email", "adresseemail",
    ],
    "EntrepriseContactName": [
        "entreprisecontactname", "contact", "contactname", "contact_name",
        "nom_contact", "nomcontact", "responsable", "rh", "recruiter",
    ],
    "EntrepriseVille": [
        "entrepriseville", "ville", "city", "location", "localisation",
    ],
    "EntrepriseSecteurActivite": [
        "entreprisesecteuractivite", "secteur", "sector", "industry",
        "industrie", "activite", "activité", "secteur_activite",
    ],
    "EntrepriseTechnologie": [
        "entreprisetechnologie", "techno", "technology", "tech",
        "technologies", "stack",
    ],
    "EntrepriseContactPhone": [
        "entreprisecontactphone", "phone", "telephone", "téléphone", "tel",
        "numero", "numéro", "contact_phone",
    ],
    "EntrepriseContactSiteWeb": [
        "entreprisecontactsiteweb", "site", "website", "web", "url", "siteweb",
    ],
    "EntrepriseLogo": [
        "entrepriselogo", "logo", "image", "picture",
    ],
    "Activite": [
        "activite", "activity",
    ],
}

SCHEMA_FIELDS = list(FIELD_ALIASES.keys())


def _normalize_key(key: str) -> str:
    """Strip accents, spaces, separators, casing."""
    if not key:
        return ""
    s = unicodedata.normalize("NFD", key)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s\-_]+", "", s).lower()


# Precompute the reverse lookup: normalized alias -> canonical field name
_ALIAS_TO_FIELD = {}
for field, aliases in FIELD_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_FIELD[_normalize_key(alias)] = field


def detect_mapping(headers):
    """Return {original_header: canonical_field} for every matched header."""
    mapping = {}
    for h in headers:
        canonical = _ALIAS_TO_FIELD.get(_normalize_key(h))
        if canonical:
            mapping[h] = canonical
    return mapping


def map_row(row: dict, mapping: dict) -> dict:
    """Apply a detected mapping to a row. Missing fields become empty strings.
    Extra columns are dropped."""
    out = {field: "" for field in SCHEMA_FIELDS}
    for orig_header, canonical in mapping.items():
        value = row.get(orig_header)
        if value is None:
            continue
        value = str(value).strip()
        if value.lower() in ("nan", "none", "null"):
            value = ""
        out[canonical] = value
    return out


def parse_file(filename: str, content_bytes: bytes):
    """Return (list_of_raw_rows, detected_headers).
    Raises ValueError on unsupported format or malformed content.
    """
    name = (filename or "").lower().strip()

    if name.endswith(".json"):
        try:
            data = json.loads(content_bytes.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"JSON invalide : {e}")
        # Accept either {"data": [...]} or a bare list
        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise ValueError("Le JSON doit être une liste d'objets ou un objet {data: [...]}")
        headers = set()
        for row in items:
            if isinstance(row, dict):
                headers.update(row.keys())
        return items, list(headers)

    if name.endswith(".csv") or not name:  # default to CSV if no extension
        try:
            text = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1", errors="replace")
        # Sniff delimiter among comma / semicolon / tab
        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        rows = [r for r in reader]
        headers = reader.fieldnames or []
        return rows, list(headers)

    raise ValueError(f"Format non supporté : {filename}. Utilisez CSV ou JSON.")


def merge_at_top(existing_items: list, new_rows: list) -> dict:
    """Prepend new rows to the beginning of existing_items.

    Required field: EntrepriseContactEmail. Rows without a valid email are
    counted as invalid. Duplicates are detected by email (case-insensitive).
    Mutates existing_items in place.
    """
    existing_emails = {
        (s.get("EntrepriseContactEmail") or "").strip().lower()
        for s in existing_items
        if s.get("EntrepriseContactEmail")
    }

    counts = {
        "imported": 0,
        "skipped_duplicates": 0,
        "skipped_invalid": 0,
        "total_seen": len(new_rows),
    }

    to_prepend = []
    for row in new_rows:
        email = (row.get("EntrepriseContactEmail") or "").strip()
        if not email or "@" not in email:
            counts["skipped_invalid"] += 1
            continue
        if email.lower() in existing_emails:
            counts["skipped_duplicates"] += 1
            continue
        to_prepend.append(row)
        existing_emails.add(email.lower())
        counts["imported"] += 1

    # Insert at the top so the user sees the new entries first
    existing_items[:0] = to_prepend
    return counts


# --------------------------------------------------------------------------- #
# Extraction from the email itself — no AI, no guessing.
# Only fills what can be deterministically inferred from the address.
# --------------------------------------------------------------------------- #

# Local-parts that are clearly generic mailboxes (no real person)
GENERIC_LOCAL_PARTS = {
    "hr", "rh", "contact", "contacts", "info", "infos", "admin", "support",
    "jobs", "careers", "career", "recrutement", "recruiting", "recruitment",
    "recrute", "talent", "talents", "hello", "hey", "team", "office",
    "mail", "mailer", "no-reply", "noreply", "help", "service",
}

# Common TLDs and second-level domains we want to drop when building the name
_TLD_PATTERN = re.compile(
    r"\.(com|org|net|io|co|ai|ma|fr|uk|de|es|it|eu|info|tech|app|dev|biz)(\.[a-z]{2})?$",
    re.IGNORECASE,
)


def _company_from_domain(domain: str) -> str:
    """acme-labs.co.uk → "Acme Labs". Returns an empty string if unusable.

    Strategy: strip the TLD, then take the rightmost remaining segment —
    this correctly handles both "pwc.ma" → "pwc" and "mail.acme.com" → "acme".
    """
    if not domain:
        return ""
    base = _TLD_PATTERN.sub("", domain.lower()).strip(".")
    if not base:
        return ""
    core = base.rsplit(".", 1)[-1]  # last segment is the brand
    tokens = [t for t in re.split(r"[-_]+", core) if t]
    return " ".join(t.capitalize() for t in tokens)


def _person_from_local_part(local: str) -> str:
    """john.doe → "John Doe". Returns "" for generic mailboxes or non-human patterns."""
    if not local:
        return ""
    key = local.lower().split("+", 1)[0]  # strip gmail tags
    if key in GENERIC_LOCAL_PARTS:
        return ""
    # Require at least one separator so we don't turn "admin" into "Admin"
    if not re.search(r"[._-]", key):
        return ""
    parts = [p for p in re.split(r"[._\-]+", key) if p and p.isalpha()]
    if len(parts) < 2:
        return ""
    # Reject numeric parts entirely — likely not a real name
    return " ".join(p.capitalize() for p in parts)


def extract_from_email(rows: list) -> None:
    """Fill EntrepriseName and EntrepriseContactName ONLY when they can be
    derived from the email itself. Never overwrites existing values.
    Other fields (city, sector, technology, website) are left untouched —
    we don't guess.
    """
    for row in rows:
        email = (row.get("EntrepriseContactEmail") or "").strip()
        if "@" not in email:
            continue
        local, _, domain = email.partition("@")

        if not (row.get("EntrepriseName") or "").strip():
            company = _company_from_domain(domain)
            if company:
                row["EntrepriseName"] = company

        if not (row.get("EntrepriseContactName") or "").strip():
            person = _person_from_local_part(local)
            if person:
                row["EntrepriseContactName"] = person
