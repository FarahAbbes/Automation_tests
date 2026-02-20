"""
check_gemini_models.py  -  VERSION CORRIGEE (nouveau SDK google-genai)
=======================================================================
Utilise le nouveau SDK : google-genai  (remplace google-generativeai)

Installation :
    pip uninstall google-generativeai -y
    pip install google-genai python-dotenv

Usage :
    python check_gemini_models.py
"""

import os
from pathlib import Path

# Charger le .env
try:
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parent
    for d in root.iterdir():
        if d.is_dir() and "config" in d.name.lower():
            env = d / ".env"
            if env.exists():
                load_dotenv(env)
                break
    else:
        load_dotenv(root / ".env")
except ImportError:
    pass

# Nouveau SDK
try:
    from google import genai
except ImportError:
    print("SDK manquant. Lancez :")
    print("   pip uninstall google-generativeai -y")
    print("   pip install google-genai")
    exit(1)

API_KEY = os.getenv("GEMINI_API_KEY", "")

if not API_KEY:
    print("GEMINI_API_KEY manquant dans config/.env")
    exit(1)

client = genai.Client(api_key=API_KEY)

print("\n" + "=" * 60)
print("  MODELES GEMINI DISPONIBLES AVEC VOTRE CLE")
print("=" * 60)

text_models = []
for m in client.models.list():
    name = m.name.replace("models/", "")
    if "gemini" in name:
        text_models.append(name)

for name in sorted(text_models, reverse=True):
    tag = ""
    if   "2.5-pro"        in name: tag = "MEILLEUR - generation complexe"
    elif "2.5-flash"      in name and "lite" not in name: tag = "Recommande pour PFE"
    elif "2.5-flash-lite" in name: tag = "Leger et rapide"
    elif "2.0-flash"      in name: tag = "Stable - valeur sure"
    elif "1.5-pro"        in name: tag = "Ancienne gen"
    elif "1.5-flash"      in name: tag = "Ancienne gen"
    print(f"  {name:50} {tag}")

print()
print("=" * 60)
print("  TEST DE CONNEXION")
print("=" * 60)

candidates = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-1.5-flash",
]

available = set(text_models)
chosen = next((c for c in candidates if c in available), None)
if not chosen and text_models:
    chosen = sorted(text_models, reverse=True)[0]

if chosen:
    try:
        response = client.models.generate_content(
            model=chosen,
            contents="Reponds juste OK"
        )
        print(f"\n  Connexion reussie !")
        print(f"  Modele teste : {chosen}")
        print(f"  Reponse      : {response.text.strip()}")
        print()
        print("  Mettez dans config/.env :")
        print(f"     GEMINI_API_KEY={API_KEY[:15]}...{API_KEY[-4:]}")
        print(f"     GEMINI_MODEL={chosen}")
    except Exception as e:
        print(f"\n  Erreur avec {chosen} : {e}")

print("=" * 60)
print()
print("LIMITES GRATUITES (Free Tier) :")
print()
print("  Modele                   Req/min   Req/jour")
print("  " + "-" * 45)
print("  gemini-2.5-pro              5         25")
print("  gemini-2.5-flash           10        250")
print("  gemini-2.0-flash           15        200")
print("  gemini-1.5-flash           15       1500")
print()
print("  Pour un PFE : gemini-2.5-flash ou gemini-2.0-flash")
print()