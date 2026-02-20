"""
generate_from_real_device.py
============================
Genere des tests Robot Framework depuis l'UI REELLE de ton device Android.

Pipeline :
    1. Appium se connecte au device (config depuis .env)
    2. Recupere la hierarchie UI de l'ecran ACTUELLEMENT affiche
    3. Extrait tous les vrais locators (resource-id reels de l'app)
    4. Envoie a Gemini pour generer le POM + test

Prerequis :
    - Appium Server lance (npx appium)
    - Device connecte (adb devices doit afficher ton device)
    - App MyBiat ouverte sur l'ecran a tester
    - .env configure (APPIUM_SERVER_URL, DEVICE_NAME, APP_PACKAGE...)

Usage :
    # Ouvre l'ecran a tester sur ton telephone, puis lance :
    python generate_from_real_device.py
    python generate_from_real_device.py --screen LoginScreen
    python generate_from_real_device.py --screen TransferScreen --save-xml
"""

import sys
import json
import argparse
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

import os

# Config depuis .env
APPIUM_URL    = os.getenv("APPIUM_SERVER_URL", "http://localhost:4723")
DEVICE_NAME   = os.getenv("DEVICE_NAME", "emulator-5554")
PLATFORM_VER  = os.getenv("PLATFORM_VERSION", "12")
APP_PACKAGE   = os.getenv("APP_PACKAGE", "com.example.mobile_app")
APP_ACTIVITY  = os.getenv("APP_ACTIVITY", ".MainActivity")

# ---------------------------------------------------------------------------
# Etape 1 : Connexion Appium et recuperation de l'UI reelle
# ---------------------------------------------------------------------------

def get_real_ui_elements(save_xml_path=None):
    """
    Se connecte au device, recupere la page source XML et extrait les elements.
    Retourne une liste de dicts compatibles avec TestGeneratorAgent.
    """
    try:
        from appium import webdriver
        from appium.options import AndroidOptions
        import xml.etree.ElementTree as ET
    except ImportError:
        print("Appium Python client manquant : pip install Appium-Python-Client")
        sys.exit(1)

    print(f"\n[1/4] Connexion Appium...")
    print(f"      URL    : {APPIUM_URL}")
    print(f"      Device : {DEVICE_NAME}")
    print(f"      Package: {APP_PACKAGE}")

    options = AndroidOptions()
    options.platform_version       = PLATFORM_VER
    options.device_name            = DEVICE_NAME
    options.app_package            = APP_PACKAGE
    options.app_activity           = APP_ACTIVITY
    options.no_reset               = True
    options.auto_grant_permissions = True

    driver = webdriver.Remote(APPIUM_URL, options=options)
    print("      Connecte !")

    print(f"\n[2/4] Recuperation de la hierarchie UI...")
    page_source = driver.page_source

    # Sauvegarder le XML brut si demande (utile pour debug)
    if save_xml_path:
        Path(save_xml_path).write_text(page_source, encoding="utf-8")
        print(f"      XML sauvegarde : {save_xml_path}")

    driver.quit()
    print(f"      {len(page_source)} caracteres recuperes")

    print(f"\n[3/4] Extraction des elements interactifs...")
    elements = _parse_xml_to_elements(page_source)
    print(f"      {len(elements)} elements trouves")

    return elements, page_source


def _parse_xml_to_elements(xml_source):
    """
    Parse le XML Appium et extrait uniquement les elements utiles.
    Filtre : elements avec resource-id OU texte OU clickable.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_source)
    except ET.ParseError as e:
        print(f"Erreur parsing XML : {e}")
        return []

    elements = []

    def walk(node):
        attrib     = node.attrib
        resource_id = attrib.get("resource-id", "")
        text        = attrib.get("text", "")
        content_desc= attrib.get("content-desc", "")
        clickable   = attrib.get("clickable", "false") == "true"
        enabled     = attrib.get("enabled", "true") == "true"
        cls         = attrib.get("class", "")

        # Garder seulement les elements utiles (avec ID, texte court, ou cliquables)
        if (resource_id or clickable or (text and len(text) < 80)):
            elements.append({
                "resource_id":  resource_id,
                "text":         text,
                "content_desc": content_desc,
                "class":        cls,
                "clickable":    clickable,
                "enabled":      enabled,
                "bounds":       attrib.get("bounds", ""),
            })

        for child in node:
            walk(child)

    walk(root)

    # Deduplication sur resource_id
    seen = set()
    unique = []
    for elem in elements:
        key = elem["resource_id"] or f"{elem['class']}_{elem['text'][:20]}"
        if key not in seen:
            seen.add(key)
            unique.append(elem)

    return unique


# ---------------------------------------------------------------------------
# Etape 2 : Affichage des elements trouves
# ---------------------------------------------------------------------------

def display_elements(elements):
    """Affiche un tableau lisible des elements detectes."""
    print(f"\n{'='*70}")
    print(f"  ELEMENTS UI DETECTES ({len(elements)} total)")
    print(f"{'='*70}")
    print(f"  {'#':3} {'Class':25} {'Resource ID':35} {'Text':20}")
    print(f"  {'-'*3} {'-'*25} {'-'*35} {'-'*20}")

    for i, elem in enumerate(elements, 1):
        cls     = elem.get("class", "").split(".")[-1][:24]
        rid     = elem.get("resource_id", "")
        # Afficher juste l'ID court (sans le package)
        rid_short = rid.split("/")[-1] if "/" in rid else (rid.split(":")[-1] if ":" in rid else rid)
        rid_short = rid_short[:34]
        text    = elem.get("text", "")[:19]
        click   = "C" if elem.get("clickable") else " "
        print(f"  {i:3} {cls:25} {rid_short:35} {text:20} {click}")

    print(f"\n  C = cliquable")
    print(f"{'='*70}")


# ---------------------------------------------------------------------------
# Etape 3 : Generation avec le Test Generator Agent
# ---------------------------------------------------------------------------

def generate_tests(elements, screen_name, output_dir="generated_tests"):
    """Lance la generation via Gemini."""
    try:
        from agents.test_generator_agent import TestGeneratorAgent, GEMINI_API_KEY
    except ImportError:
        # Si lance depuis la racine du projet
        sys.path.insert(0, str(Path(__file__).parent))
        from test_generator_agent import TestGeneratorAgent, GEMINI_API_KEY

    if not GEMINI_API_KEY:
        print("\nGEMINI_API_KEY manquant dans .env")
        sys.exit(1)

    print(f"\n[4/4] Generation des tests avec Gemini (gemini-2.5-flash)...")
    print(f"      Ecran       : {screen_name}")
    print(f"      Elements    : {len(elements)}")
    print(f"      Output dir  : {output_dir}/")

    agent  = TestGeneratorAgent()
    result = agent.generate_from_ui_elements(elements, screen_name)

    # Sauvegarder
    saved = agent.save_generated_test(result, output_base_dir=output_dir)

    print(f"\n{'='*70}")
    print(f"  GENERATION TERMINEE")
    print(f"{'='*70}")
    print(f"  POM  sauvegarde : {saved['page_object_saved']}")
    print(f"  Test sauvegarde : {saved['test_saved']}")
    print(f"\n  Notes Gemini :")
    for line in result.generation_notes[:400].split("\n"):
        print(f"    {line}")

    print(f"\n--- APERCU PAGE OBJECT (15 premieres lignes) ---")
    for line in result.page_object_file.split("\n")[:15]:
        print(f"  {line}")

    print(f"\n--- APERCU TEST FILE (15 premieres lignes) ---")
    for line in result.test_file.split("\n")[:15]:
        print(f"  {line}")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Genere des tests Robot Framework depuis ton device Android reel"
    )
    parser.add_argument(
        "--screen",
        default=None,
        help="Nom de l'ecran (ex: LoginScreen). Auto-detecte si non fourni."
    )
    parser.add_argument(
        "--save-xml",
        action="store_true",
        help="Sauvegarde le XML brut de la page dans debug_ui.xml"
    )
    parser.add_argument(
        "--output-dir",
        default="generated_tests",
        help="Dossier de sortie (defaut: generated_tests)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les elements detectes sans appeler Gemini"
    )
    args = parser.parse_args()

    print("\n" + "="*70)
    print("  GENERATION DEPUIS DEVICE REEL")
    print("="*70)
    print(f"  Appium URL : {APPIUM_URL}")
    print(f"  Device     : {DEVICE_NAME}  (Android {PLATFORM_VER})")
    print(f"  Package    : {APP_PACKAGE}")
    print(f"\n  Assure-toi que :")
    print(f"    1. Appium Server est lance  (npx appium)")
    print(f"    2. Ton device est connecte (adb devices)")
    print(f"    3. L'ecran a tester est AFFICHE sur le device")
    print()

    # Recuperer l'UI reelle
    xml_path = "debug_ui.xml" if args.save_xml else None
    elements, _ = get_real_ui_elements(save_xml_path=xml_path)

    # Afficher les elements trouves
    display_elements(elements)

    if args.dry_run:
        print("\nMode --dry-run : generation annulee")
        print("Relancez sans --dry-run pour generer les tests")
        return

    # Auto-detecter le nom de l'ecran si non fourni
    screen_name = args.screen
    if not screen_name:
        # Chercher dans les textes/IDs
        for elem in elements:
            rid = elem.get("resource_id", "")
            txt = elem.get("text", "")
            for kw, name in [
                ("login",    "LoginScreen"),
                ("transfer", "TransferScreen"),
                ("payment",  "PaymentScreen"),
                ("account",  "AccountScreen"),
                ("home",     "HomeScreen"),
                ("dashboard","DashboardScreen"),
            ]:
                if kw in rid.lower() or kw in txt.lower():
                    screen_name = name
                    break
            if screen_name:
                break
        if not screen_name:
            screen_name = input("\nNom de l'ecran (ex: LoginScreen) : ").strip() or "UnknownScreen"

    print(f"\n  Ecran detecte / fourni : {screen_name}")

    # Generer
    generate_tests(elements, screen_name, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
