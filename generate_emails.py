import json
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Validate OpenAI API key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env file. Add your ChatGPT/OpenAI API key to continue.")

def load_startups(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('data', [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading startups: {str(e)}")
        return []

def load_resume(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading resume: {str(e)}")
        return {}

def load_tracking_data():
    tracking_file = 'email_tracking.json'
    try:
        if os.path.exists(tracking_file):
            with open(tracking_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error loading tracking data: {str(e)}")
    return {'processed_companies': []}

def save_tracking_data(tracking_data):
    with open('email_tracking.json', 'w', encoding='utf-8') as f:
        json.dump(tracking_data, f, indent=2)

def load_generated_emails():
    """Load existing generated emails from JSON file"""
    email_file = 'generated_emails.json'
    try:
        if os.path.exists(email_file):
            with open(email_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error loading email data: {str(e)}")
    return []

def save_generated_emails(email_data):
    """Save generated emails to JSON file"""
    with open('generated_emails.json', 'w', encoding='utf-8') as f:
        json.dump(email_data, f, indent=2, ensure_ascii=False)

class ChatGPTClient:
    def __init__(self, resume_data):
        self.resume_data = resume_data
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL

    def generate_email(self, startup):
        education = self.resume_data.get('education', [])
        current_program = next(
            (edu for edu in education if edu.get('endDate', '') > '2025-06'), 
            {}
        )


        prompt = (
    f"Tu es un expert en rédaction de communication professionnelle et commerciale. "
    f"Ta mission est de rédiger un email complet, clair, professionnel et hautement persuasif destiné à proposer à l’entreprise {startup.get('EntrepriseName', 'votre entreprise')} "
    f"des projets concrets en intelligence artificielle (IA) et systèmes multi-agents. "
    f"L’objectif est de convaincre {startup.get('EntrepriseName', 'votre entreprise')} d’investir dans ces solutions pour améliorer la productivité, "
    f"réduire les coûts, renforcer la compétitivité et optimiser l’expérience client.\n\n"

    f" Contraintes :\n"
    f"- L’email doit contenir toutes les sections demandées ci-dessous, sans rien oublier.\n"
    f"- La première phrase doit être puissante, accrocheuse et créer un sentiment d’urgence et d’opportunité.\n"
    f"- La dernière phrase doit être encore plus percutante et laisser une impression forte qui incite à agir immédiatement.\n"
    f"- Chaque projet doit être présenté avec une phrase d’introduction claire, puis une explication concise de sa valeur ajoutée.\n"
    f"- Le ton doit rester professionnel, clair, positif et orienté business.\n"
    f"- Longueur : entre 100 et 250 mots maximum.\n"
    f"- Format : texte brut uniquement, sans balises HTML ni Markdown.\n\n"

    f" Structure obligatoire de l’email :\n"
    f"1. Objet de l’email : Propositions de solutions IA innovantes pour {startup.get('EntrepriseName', 'votre entreprise')}.\n"
    f"2. Introduction : Commencer par 'Bonjour', puis enchaîner immédiatement avec une phrase d’ouverture forte, par exemple : "
    f"« Aujourd’hui, dans un monde en changement rapide, l’intelligence artificielle est le moteur de la transformation. "
    f"Les entreprises qui prennent le train de l’IA avancent, celles qui hésitent risquent de rester en retard. » "
    f"Ensuite présenter brièvement l’objectif du message (proposer des solutions IA adaptées aux besoins de {startup.get('EntrepriseName', 'votre entreprise')}).\n"
    f"3. Présentation des projets : Introduire la liste en expliquant pourquoi ces projets sont stratégiques. "
    f"Puis détailler au moins 4 projets choisis parmi :\n"
    f"   • Service Client et Communication : chatbots multi-agents 24/7.\n"
    f"   • Ressources Humaines : tri automatique de CV.\n"
    f"   • Gestion Administrative et Opérationnelle : traitement automatisé de factures.\n"
    f"   • Marketing et Ventes : ciblage personnalisé, analyse des tendances marché, automatisation de campagnes publicitaires.\n"
    f"   • Finance et Comptabilité : automatisation des paiements, prédiction des flux financiers, conformité réglementaire automatisée.\n"
    f"   • Automatisation personnalisée : mise en place d’agents intelligents capables de prendre en charge n’importe quelle tâche répétitive selon vos besoins spécifiques.\n"
    f"Chaque projet doit être présenté avec une formulation engageante qui montre son impact direct sur {startup.get('EntrepriseName', 'votre entreprise')}.\n"
    f"4. Valeur ajoutée : Insister sur les bénéfices concrets : gain de temps, réduction des erreurs, efficacité opérationnelle, compétitivité renforcée, innovation continue et retour sur investissement (ROI).\n"
    f"5. Personnalisation : Mettre en avant que chaque projet peut être spécifiquement adapté aux besoins de {startup.get('EntrepriseName', 'votre entreprise')} avec un coût optimisé.\n"
    f"6. Appel à l’action : Inviter à organiser un échange pour discuter d’une solution personnalisée et démontrer la valeur de ces projets.\n"
    f"7. Conclusion : Terminer avec une phrase extrêmement puissante qui crée un déclic, par exemple : "
    f"« Investir dès aujourd’hui dans l’intelligence artificielle, c’est assurer à {startup.get('EntrepriseName', 'votre entreprise')} "
    f"une avance stratégique, une efficacité maximale et un retour sur investissement rapide. "
    f"Chaque projet est conçu pour être flexible, adaptable et optimisé en coût : c’est l’opportunité idéale à saisir avant vos concurrents. »\n"
    f"8. Signature :\n"
    f"   Cordialement,\n"
    f"   Ahmed Hajji\n"
    f"   +212 603251761 | ahmed.hajji.23@ump.ac.ma"
)









#         prompt = (
# f"Rédige un email de demande de stage professionnel à la fois naturel, convaincant et inspirant, en respectant les instructions suivantes :\n\n"

# f"1. POSITION DE L’OBJET (OBLIGATOIRE) :\n"
# f"   L’objet du mail doit toujours apparaître **au tout début de l’email**, avant toute introduction.\n"
# f"   Objet exact à utiliser :\n"
# f"   \"Demande de stage de fin d’études (PFE) – Étudiant en Intelligence Artificielle – Ahmed Hajji\"\n\n"

# f"2. INTRODUCTION PERSONNALISÉE :\n"
# f"   Commencer ensuite par :\n"
# f"   \"Bonjour,\nJe suis Hajji Ahmed, étudiant ingénieur en dernière année à l’École Nationale d’Intelligence Artificielle et du Digital (ENIAD), à Berkane.\"\n\n"

# f"3. PROFIL DU CANDIDAT :\n"
# f"   - Compétences : machine learning, deep learning, NLP, computer vision, data science, cloud computing, systèmes multi-agents, Power BI, SQL, Talend, React, Next.js, Python, C++, Java\n"
# f"   - Outils : Git, Docker, Microsoft Azure, TensorFlow, PyTorch\n"
# f"   - Certifications : IBM, Oracle, Microsoft, Simplilearn\n"
# f"   - Stage souhaité : pour une durée de 4 à 6 mois à partir de février 2026 \n\n"

# f"4. CONTEXTE DE L’ENTREPRISE :\n"
# f"   - Contact : {startup.get('EntrepriseContactName', 'Responsable RH')}\n"
# f"   - Organisation : {startup.get('EntrepriseName', '')} à {startup.get('EntrepriseVille', '')}\n"
# f"   - Domaines : {startup.get('EntrepriseTechnologie', 'technologie')} et {startup.get('EntrepriseSecteurActivite', 'secteur d’activité')}\n\n"

# f"5. STRUCTURE DU CORPS DE L’EMAIL :\n"
# f"   - Introduction : inclure les lignes ci-dessus et exprimer un intérêt sincère pour les défis et les innovations liés aux domaines d'activité de l'entreprise (notamment {startup.get('EntrepriseSecteurActivite', 'secteur d’activité')}).\n"
# f"   - Message principal :\n"
# f"       * Exprimer une passion forte pour l’innovation, l’intelligence artificielle et la résolution de problèmes réels.\n"
# f"       * Souligner la motivation à apprendre au contact de professionnels expérimentés et à contribuer à des projets à fort impact.\n"
# f"       * Mettre en avant les domaines de maîtrise : machine learning, NLP, computer vision, data science, systèmes multi-agents, cloud, etc.\n"
# f"       * Expliquer que l’objectif est de mettre ces compétences au service de l’entreprise afin de créer des solutions innovantes et utiles.\n"
# f"       * Valoriser un état d’esprit proactif : curiosité, esprit d’équipe, adaptabilité, envie de progresser.\n"
# f"   - Appel à l’action : proposer un échange ou un entretien pour discuter d’une éventuelle collaboration.\n"
# f"   - Clôture : formule polie et professionnelle.\n\n"

# f"6. EXIGENCES DE STYLE :\n"
# f"   - Ton : professionnel, fluide, motivé et engageant (langage clair, sans formalisme excessif)\n"
# f"   - Longueur : entre 120 et 150 mots\n"
# f"   - Format : texte brut uniquement (pas de balises ni de mise en forme)\n"
# f"   - L’objet DOIT TOUJOURS apparaître en premier, suivi d’une ligne vide, puis du contenu de l’email.\n\n"

# f"7. ÉLÉMENTS OBLIGATOIRES :\n"
# f"   - Mention claire de la période de stage (février 2026, 4 à 6 mois)\n"
# f"   - Mise en avant de la motivation et de la valeur ajoutée pour l’entreprise\n"
# f"   - Présence d’un appel à un échange ou une rencontre\n"
# f"   - Mention explicite que le CV est joint en pièce jointe\n\n"

# f"8. SIGNATURE (FORMAT EXACT) :\n"
# f"   Cordialement,\n"
# f"   Ahmed Hajji\n"
# f"   Étudiant ingénieur en Intelligence Artificielle – ENIAD\n"
# f"   +212 603251761 | ahmed.hajji.23@ump.ac.ma\n"
# f"   github.com/Hajji-ahmed | linkedin.com/in/ahmed-hajji-219247386"


# )

        

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=500,
        )
        email_text = (response.choices[0].message.content or '').strip()
        return self.parse_email_response(email_text)
    
    def parse_email_response(self, email_text):
        """Parse email response into subject and body components"""
        parts = email_text.split('\n\n', 1)
        if len(parts) >= 2:
            # Extract subject from first line
            subject_line = parts[0].strip()
            if subject_line.startswith('Subject:'):
                subject = subject_line[8:].strip()
            else:
                subject = subject_line
            
            # The rest is the body
            body = parts[1].strip()
        else:
            # Fallback if parsing fails
            subject = "Internship Request"
            body = email_text.strip()
        
        return subject, body


def main():
    # Load data with error handling
    startups = load_startups('startups.json')
    if not startups:
        print("[ERROR] No startup data loaded. Exiting.")
        return

    resume_data = load_resume('resume.json')
    if not resume_data:
        print("[ERROR] No resume data loaded. Exiting.")
        return

    tracking_data = load_tracking_data()
    existing_emails = load_generated_emails()
    processed_companies = {e['company_name'] for e in existing_emails}
    
    # Initialize client with resume data
    client = ChatGPTClient(resume_data)
    
    for s in startups:
        company_name = s.get('EntrepriseName', 'Unknown Company')

        # Skip if already processed
        if company_name in processed_companies or company_name in tracking_data['processed_companies']:
            print(f"[SKIP] {company_name} - already processed.")
            continue

        try:
            print(f"[INFO] Generating email for {company_name}...")
            subject, body = client.generate_email(s)
            
            email_obj = {
                "company_name": company_name,
                "company_location": s.get('EntrepriseVille', ''),
                "company_technology": s.get('EntrepriseTechnologie', ''),
                "company_sector": s.get('EntrepriseSecteurActivite', ''),
                "hr_name": s.get('EntrepriseContactName', ''),
                "hr_email": s.get('EntrepriseContactEmail', ''),
                "email_subject": subject,
                "email_body": body
            }

            # Append and save immediately
            existing_emails.append(email_obj)
            save_generated_emails(existing_emails)

            tracking_data['processed_companies'].append(company_name)
            save_tracking_data(tracking_data)

            print(f"[SUCCESS] Email saved for {company_name}")

        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "quota" in error_str.lower():
                print("\n[QUOTA LIMIT REACHED] API quota limit has been reached.")
                print("Progress has been saved. You can run the script again later to continue.")
                print(f"Processed {len(existing_emails)} companies so far.")
                return  # Exit the script when quota is reached
            else:
                print(f"[ERROR] Failed to generate email for {company_name}: {error_str}")

    print(f"\n[INFO] Email generation completed. Total processed: {len(existing_emails)}")

if __name__ == "__main__":
    main()