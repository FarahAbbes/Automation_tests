"""
agent_quality.py  -  Agent de qualite complet
==============================================
Remplace Appium Inspector par une pipeline automatique :

  AVANT (manuel) :
    1. Ouvrir Appium Inspector
    2. Connecter le device
    3. Capturer l'UI
    4. Cliquer sur chaque element
    5. Copier les resource-id un par un
    6. Ecrire les tests a la main

  APRES (cet agent) :
    1. Ouvrir l'ecran sur le device
    2. python agent_quality.py
    -> Vrais locators + tests generes automatiquement

Utilise directement les fonctions du MCP Appium Server.
"""

import os
import sys
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Chargement .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parent
    for d in root.iterdir():
        if d.is_dir() and "config" in d.name.lower():
            e = d / ".env"
            if e.exists():
                load_dotenv(e)
                break
    else:
        load_dotenv(root / ".env")
except ImportError:
    pass

import os
APPIUM_URL   = os.getenv("APPIUM_SERVER_URL", "http://localhost:4723")
DEVICE_NAME  = os.getenv("DEVICE_NAME",       "emulator-5554")
PLATFORM_VER = os.getenv("PLATFORM_VERSION",  "12")
APP_PACKAGE  = os.getenv("APP_PACKAGE",        "com.example.mobile_app")
APP_ACTIVITY = os.getenv("APP_ACTIVITY",       ".MainActivity")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY",     "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL",       "gemini-2.5-flash")


# ===========================================================================
# ETAPE 1 : Recuperer le vrai XML depuis le MCP Appium Server
#           C'est exactement ce qu'Appium Inspector te montre
# ===========================================================================

def step1_get_real_xml() -> tuple[str, bool]:
    """
    Appelle get_page_source() du MCP Appium Server.
    Retourne (xml_string, is_simulation).

    C'est le meme XML que tu vois dans Appium Inspector -> Source.
    """
    print("\n" + "="*65)
    print("  ETAPE 1 : Recuperation du XML (equivalent Appium Inspector)")
    print("="*65)

    # Importer les fonctions du MCP Appium Server directement
    try:
        sys.path.insert(0, str(Path(__file__).parent / "mcp_servers"))
        from appium_mcp import get_page_source as mcp_get_page_source
        result = mcp_get_page_source()
        xml    = result.get("xml", "")
        sim    = result.get("simulation", False)

        if sim:
            print("  Mode SIMULATION (Appium non connecte)")
            print("  -> Lance 'npx appium' et connecte ton device pour le mode reel")
        else:
            print(f"  Connecte au device : {DEVICE_NAME}")
            print(f"  XML recupere       : {result.get('size_bytes', 0)} bytes")
            print("  Source             : DEVICE REEL (vrais locators !)")

        return xml, sim

    except ImportError:
        # Fallback : connexion Appium directe
        print("  MCP Server non trouve -> connexion Appium directe...")
        return _direct_appium_connection()


def _direct_appium_connection() -> tuple[str, bool]:
    """Connexion directe a Appium sans passer par le MCP Server."""
    try:
        from appium import webdriver
        from appium.options import AndroidOptions

        options = AndroidOptions()
        options.platform_version       = PLATFORM_VER
        options.device_name            = DEVICE_NAME
        options.app_package            = APP_PACKAGE
        options.app_activity           = APP_ACTIVITY
        options.no_reset               = True
        options.auto_grant_permissions = True

        print(f"  Connexion a {APPIUM_URL}...")
        driver = webdriver.Remote(APPIUM_URL, options=options)
        xml    = driver.page_source
        driver.quit()

        print(f"  XML recupere : {len(xml)} caracteres")
        print("  Source       : DEVICE REEL")
        return xml, False

    except Exception as e:
        print(f"  Appium non disponible ({e})")
        print("  -> Mode simulation avec XML de demo")
        return _get_demo_xml(), True


def _get_demo_xml() -> str:
    """XML de demo representant l'ecran Login de MyBiat."""
    pkg = APP_PACKAGE
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <android.widget.FrameLayout resource-id="android:id/content">
    <android.widget.LinearLayout>
      <android.widget.TextView
        resource-id="{pkg}:id/tv_title"
        text="MyBiat - Connexion"
        clickable="false" enabled="true"/>
      <android.widget.EditText
        resource-id="{pkg}:id/edit_username"
        text="" content-desc="Identifiant"
        clickable="true" enabled="true"/>
      <android.widget.EditText
        resource-id="{pkg}:id/edit_password"
        text="" content-desc="Mot de passe"
        clickable="true" enabled="true"/>
      <android.widget.CheckBox
        resource-id="{pkg}:id/cb_remember_me"
        text="Se souvenir de moi"
        clickable="true" enabled="true"/>
      <android.widget.Button
        resource-id="{pkg}:id/btn_login"
        text="Se connecter"
        clickable="true" enabled="true"/>
      <android.widget.TextView
        resource-id="{pkg}:id/tv_forgot_password"
        text="Mot de passe oublie ?"
        clickable="true" enabled="true"/>
    </android.widget.LinearLayout>
  </android.widget.FrameLayout>
</hierarchy>"""


# ===========================================================================
# ETAPE 2 : Parser le XML -> extraire les elements
#           Equivalent : cliquer sur chaque element dans Appium Inspector
# ===========================================================================

def step2_extract_elements(xml: str) -> list[dict]:
    """
    Extrait tous les elements interactifs du XML.

    C'est l'equivalent de ce qu'Appium Inspector te montre dans le panneau
    de droite quand tu cliques sur un element : resource-id, text, etc.
    """
    print("\n" + "="*65)
    print("  ETAPE 2 : Extraction des elements (equivalent clic Appium Inspector)")
    print("="*65)

    try:
        root_node = ET.fromstring(xml)
    except ET.ParseError as e:
        print(f"  Erreur parsing XML : {e}")
        return []

    elements = []
    seen     = set()

    def walk(node):
        a   = node.attrib
        rid = a.get("resource-id", "")
        txt = a.get("text", "")
        dsc = a.get("content-desc", "")
        clk = a.get("clickable", "false") == "true"
        ena = a.get("enabled",   "true")  == "true"
        cls = a.get("class", "")

        useful = rid or clk or (txt and len(txt) < 80)
        if useful:
            key = rid or f"{cls}::{txt[:20]}"
            if key not in seen:
                seen.add(key)
                elements.append({
                    "resource_id":  rid,
                    "text":         txt,
                    "content_desc": dsc,
                    "class":        cls,
                    "clickable":    clk,
                    "enabled":      ena,
                    "bounds":       a.get("bounds", ""),
                })
        for child in node:
            walk(child)

    walk(root_node)

    # Afficher comme Appium Inspector - tableau des elements
    print(f"\n  {'#':>3}  {'Type':24}  {'Resource ID':38}  {'Text':22}  Clk")
    print(f"  {'-'*3}  {'-'*24}  {'-'*38}  {'-'*22}  {'-'*3}")
    for i, e in enumerate(elements, 1):
        cls_s = e["class"].split(".")[-1][:23]
        rid_s = (e["resource_id"].split("/")[-1] if "/" in e["resource_id"]
                 else e["resource_id"])[:37]
        txt_s = e["text"][:21]
        clk_s = "Yes" if e["clickable"] else "No"
        print(f"  {i:>3}  {cls_s:24}  {rid_s:38}  {txt_s:22}  {clk_s}")

    print(f"\n  Total : {len(elements)} elements detectes")
    return elements


# ===========================================================================
# ETAPE 3 : Gemini identifie l'ecran depuis le XML
#           Equivalent : toi qui comprends visuellement l'ecran
# ===========================================================================

def step3_identify_screen(xml: str, elements: list[dict]) -> str:
    """
    Gemini analyse le XML et identifie l'ecran.

    Contrairement a Appium Inspector (visuel), Gemini raisonne sur :
    - Les resource-id (indices semantiques)
    - Les textes visibles
    - Les types de widgets
    """
    print("\n" + "="*65)
    print("  ETAPE 3 : Identification de l'ecran par Gemini")
    print("="*65)

    if not GEMINI_KEY:
        screen = input("  GEMINI_API_KEY manquant. Nom de l'ecran ? : ").strip()
        return screen or "UnknownScreen"

    try:
        from google import genai
        from google.genai import types as gt
    except ImportError:
        print("  pip install google-genai")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_KEY)

    # Construire le resume des elements pour Gemini
    # (meme info que le panneau Appium Inspector)
    summary_lines = []
    for e in elements[:35]:
        cls = e["class"].split(".")[-1]
        rid = e["resource_id"]
        txt = e["text"]
        dsc = e["content_desc"]
        clk = "cliquable" if e["clickable"] else ""
        if rid or txt:
            summary_lines.append(f"  [{cls}] id={rid!r} text={txt!r} desc={dsc!r} {clk}")

    prompt = f"""
Application bancaire mobile Android. Package : {APP_PACKAGE}

Elements UI de l'ecran courant :
{chr(10).join(summary_lines)}

Reponds UNIQUEMENT en JSON :
{{
  "screen_name": "NomDeLEcran (PascalCase, suffixe Screen, ex: LoginScreen)",
  "screen_purpose": "une phrase",
  "confidence": "high | medium | low",
  "reasoning": "indices utilises pour identifier (2-3 mots-cles)"
}}
"""

    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=gt.GenerateContentConfig(temperature=0.1, max_output_tokens=256),
    )
    raw = re.sub(r"```json|```", "", resp.text).strip()

    try:
        data        = json.loads(raw)
        screen_name = data.get("screen_name", "UnknownScreen")
        confidence  = data.get("confidence", "?")
        purpose     = data.get("screen_purpose", "")
        reasoning   = data.get("reasoning", "")

        print(f"\n  Ecran detecte  : {screen_name}")
        print(f"  Confiance      : {confidence}")
        print(f"  Fonctionnalite : {purpose}")
        print(f"  Indices        : {reasoning}")

    except json.JSONDecodeError:
        screen_name = "UnknownScreen"
        print(f"  Impossible de parser : {raw[:100]}")

    # Confirmer avec l'utilisateur
    confirm = input(f"\n  Confirmer '{screen_name}' ? [Entree=oui / nouveau nom] : ").strip()
    if confirm:
        screen_name = confirm
        print(f"  Corrige -> {screen_name}")

    return screen_name


# ===========================================================================
# ETAPE 4 : Gemini genere le POM + tests avec les VRAIS locators
#           Equivalent : toi qui ecris les tests avec les IDs copies
# ===========================================================================

def step4_generate_tests(elements: list[dict], screen_name: str, output_dir: str) -> dict:
    """
    Appelle TestGeneratorAgent avec les vrais elements.

    La difference avec avant :
    AVANT : elements = mock hardcode dans le script
    MAINTENANT : elements = vrais resource-id extraits du device
    """
    print("\n" + "="*65)
    print("  ETAPE 4 : Generation Robot Framework (POM)")
    print("="*65)
    print(f"  Ecran    : {screen_name}")
    print(f"  Elements : {len(elements)} (vrais locators depuis le device)")
    print(f"  Output   : {output_dir}/")

    sys.path.insert(0, str(Path(__file__).parent))
    from test_generator_agent import TestGeneratorAgent

    agent  = TestGeneratorAgent()
    result = agent.generate_from_ui_elements(elements, screen_name)
    saved  = agent.save_generated_test(result, output_base_dir=output_dir)

    return {"result": result, "saved": saved}


# ===========================================================================
# ETAPE 5 : Rapport de qualite
# ===========================================================================

def step5_quality_report(elements: list, result, saved: dict, is_simulation: bool):
    """Affiche un rapport de qualite sur la generation."""

    page_obj  = result.page_object_file
    test_file = result.test_file

    # Compter les locators generes
    locators_count = page_obj.count("${LOCATOR_")
    keywords_count = page_obj.count("[Documentation]")
    testcases_count= test_file.count("\nTC_")

    # Verifier la qualite des locators
    real_ids = [e["resource_id"] for e in elements if e["resource_id"]]
    locators_real = sum(1 for rid in real_ids if rid in page_obj)

    print("\n" + "="*65)
    print("  RAPPORT DE QUALITE")
    print("="*65)
    print(f"  Source des locators  : {'SIMULATION (pas fiables)' if is_simulation else 'DEVICE REEL (fiables)'}")
    print(f"  Elements detectes    : {len(elements)}")
    print(f"  Locators dans POM    : {locators_count}")
    print(f"  Vrais IDs utilises   : {locators_real}/{len(real_ids)}")
    print(f"  Keywords documentes  : {keywords_count}")
    print(f"  Cas de test generes  : {testcases_count}")
    print()
    print(f"  POM  sauvegarde : {saved.get('page_object_saved', 'N/A')}")
    print(f"  Test sauvegarde : {saved.get('test_saved', 'N/A')}")

    if is_simulation:
        print()
        print("  !! ATTENTION : locators issus de la simulation !!")
        print("     Lance Appium + connecte ton device pour obtenir")
        print("     les vrais resource-id de MyBiat.")
    else:
        print()
        print("  Locators extraits directement du device.")
        print("  Les tests peuvent etre executes immediatement :")
        print(f"    robot --outputdir results {saved.get('test_saved', '')}")

    print("="*65)


# ===========================================================================
# Pipeline principal
# ===========================================================================

def run_pipeline(output_dir: str = "generated_tests", save_xml: bool = False):
    """
    Execute le pipeline complet :
    XML reel -> elements -> identification ecran -> generation tests
    """
    print("\n" + "="*65)
    print("  AGENT QUALITE - PIPELINE COMPLET")
    print("  Equivalent Appium Inspector + ecriture tests (automatise)")
    print("="*65)
    print(f"  Package : {APP_PACKAGE}")
    print(f"  Device  : {DEVICE_NAME}  (Android {PLATFORM_VER})")
    print(f"  Appium  : {APPIUM_URL}")

    # Etape 1 : XML reel
    xml, is_sim = step1_get_real_xml()

    if save_xml:
        Path("debug_ui.xml").write_text(xml, encoding="utf-8")
        print(f"\n  XML brut sauvegarde -> debug_ui.xml")
        print(f"  Ouvre ce fichier pour voir ce qu'Appium voit exactement")

    # Etape 2 : Extraire les elements
    elements = step2_extract_elements(xml)
    if not elements:
        print("  Aucun element trouve.")
        return

    # Etape 3 : Identifier l'ecran
    screen_name = step3_identify_screen(xml, elements)

    # Etape 4 : Generer les tests
    gen    = step4_generate_tests(elements, screen_name, output_dir)
    result = gen["result"]
    saved  = gen["saved"]

    # Etape 5 : Rapport qualite
    step5_quality_report(elements, result, saved, is_sim)

    # Copier dans outputs pour telechargement
    try:
        out = Path("/mnt/user-data/outputs")
        out.mkdir(parents=True, exist_ok=True)
        sn = screen_name.lower().replace("screen","")
        (out / f"{screen_name}Page.robot").write_text(result.page_object_file, encoding="utf-8")
        (out / f"test_{sn}.robot").write_text(result.test_file, encoding="utf-8")
    except Exception:
        pass


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent qualite : genere des tests depuis l'UI reelle du device"
    )
    parser.add_argument("--output-dir", default="generated_tests")
    parser.add_argument("--save-xml",   action="store_true",
                        help="Sauvegarde le XML brut dans debug_ui.xml")
    args = parser.parse_args()

    run_pipeline(output_dir=args.output_dir, save_xml=args.save_xml)
