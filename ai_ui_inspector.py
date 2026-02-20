"""
AI UI Inspector — MyBiat Test Automation
=========================================
Flux complet : Appium (device réel) → Extraction UI → Gemini API → Tests Robot

Usage:
    python ai_ui_inspector.py                    # Inspection unique
    python ai_ui_inspector.py --watch            # Mode surveillance continue
    python ai_ui_inspector.py --save-tests       # Sauvegarde les tests générés
"""

import os
import re
import json
import time
import base64
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Optional

# ============================================================================
# CHARGEMENT .ENV
# ============================================================================
try:
    from dotenv import load_dotenv
    # Cherche le .env dans plusieurs emplacements possibles
    _loaded = False
    _candidates = [
        Path(__file__).parent / ".env",                    # même dossier que le script
        Path(__file__).parent / "config" / ".env",         # sous-dossier config/
        Path(__file__).parent.parent / ".env",             # dossier parent
        Path(__file__).parent.parent / "config" / ".env",  # parent/config/
        Path.cwd() / ".env",                               # répertoire courant
        Path.cwd() / "config" / ".env",
    ]
    for _env_path in _candidates:
        if _env_path.exists():
            load_dotenv(_env_path, override=True)
            print(f"✅ .env chargé : {_env_path}")
            _loaded = True
            break
    if not _loaded:
        # Dernier recours : cherche un dossier contenant "config" (gère l'espace caché)
        _root = Path(__file__).parent
        for _item in _root.iterdir():
            if _item.is_dir() and "config" in _item.name.lower():
                _env = _item / ".env"
                if _env.exists():
                    load_dotenv(_env, override=True)
                    print(f"✅ .env trouvé (espace caché) : {_env}")
                    _loaded = True
                    break
    if not _loaded:
        print("⚠️  Aucun .env trouvé, chemins testés :")
        for _p in _candidates:
            print(f"   - {_p}")
        load_dotenv()
except ImportError:
    print("⚠️  python-dotenv absent — variables d'env depuis le système")

# ============================================================================
# IMPORTS APPIUM
# ============================================================================
try:
    from appium import webdriver
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    APPIUM_OK = True
    print("✅ Appium SDK chargé")
except ImportError as e:
    APPIUM_OK = False
    print(f"❌ Appium import échoué : {e}")

# ============================================================================
# IMPORTS GEMINI (nouveau SDK google-genai)
# ============================================================================
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_OK = True
    GEMINI_SDK = "new"
except ImportError:
    try:
        # Fallback vers l'ancien SDK (déprécié)
        import google.generativeai as genai_old
        GEMINI_OK = True
        GEMINI_SDK = "old"
    except ImportError:
        GEMINI_OK = False
        GEMINI_SDK = None
        print("❌ Gemini non installé : pip install google-genai")

# ============================================================================
# CONFIG DEPUIS .ENV
# ============================================================================
APPIUM_URL           = os.getenv("APPIUM_SERVER_URL", "http://localhost:4723")
DEVICE_NAME          = os.getenv("DEVICE_NAME", "82403e660602")
PLATFORM_VERSION     = os.getenv("PLATFORM_VERSION", "12")
APP_PACKAGE          = os.getenv("APP_PACKAGE", "com.example.mobile_app")
APP_ACTIVITY         = os.getenv("APP_ACTIVITY", ".MainActivity")
APP_PATH             = os.getenv("APP_PATH", "")
ELEMENT_TIMEOUT      = int(os.getenv("ELEMENT_TIMEOUT", "10"))
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
# Si vide, réessayer avec le dossier config à espace caché
if not GEMINI_API_KEY:
    try:
        from dotenv import load_dotenv as _ldenv
        for _item in Path(__file__).parent.iterdir():
            if _item.is_dir() and "config" in _item.name.lower():
                _e = _item / ".env"
                if _e.exists():
                    _ldenv(_e, override=True)
                    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
                    break
    except Exception:
        pass
GEMINI_MODEL         = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SCREENSHOTS_DIR      = os.getenv("SCREENSHOTS_DIR", "screenshots")

# Debug : afficher la config chargée au démarrage
print("\n📋 CONFIG CHARGÉE :")
print(f"   APPIUM_URL      : {APPIUM_URL}")
print(f"   DEVICE_NAME     : {DEVICE_NAME}")
print(f"   PLATFORM_VERSION: {PLATFORM_VERSION}")
print(f"   APP_PACKAGE     : {APP_PACKAGE}")
print(f"   APP_ACTIVITY    : {APP_ACTIVITY}")
print(f"   GEMINI_MODEL    : {GEMINI_MODEL}")
print(f"   GEMINI_API_KEY  : {'✅ défini' if GEMINI_API_KEY else '❌ MANQUANT'}\n")

# Pages connues de MyBiat (détection par heuristiques)
KNOWN_PAGES = {
    "login":        ["login", "connexion", "username", "password", "mot_de_passe",
                     "edit_username", "edit_password", "btn_login", "se_connecter"],
    "dashboard":    ["dashboard", "accueil", "home", "solde", "compte", "balance"],
    "transfer":     ["transfer", "virement", "beneficiaire", "montant", "amount"],
    "accounts":     ["accounts", "comptes", "liste_comptes", "account_list"],
    "profile":      ["profile", "profil", "settings", "parametres", "mon_compte"],
    "cards":        ["card", "carte", "visa", "mastercard", "carte_bancaire"],
    "notifications":["notification", "alerte", "bell", "notif"],
    "otp":          ["otp", "code_sms", "verification", "sms_code", "pin"],
}


# ============================================================================
# CONNEXION APPIUM
# ============================================================================

def connect_appium() -> Optional[object]:
    """Crée une session Appium vers le device réel."""
    if not APPIUM_OK:
        return None

    print(f"\n📱 Connexion Appium → {APPIUM_URL}")
    print(f"   Device  : {DEVICE_NAME}")
    print(f"   Android : {PLATFORM_VERSION}")
    print(f"   Package : {APP_PACKAGE}")

    # Capabilities universelles (compatibles toutes versions Appium-Python-Client)
    caps = {
        "platformName":           "Android",
        "appium:platformVersion":  PLATFORM_VERSION,
        "appium:deviceName":       DEVICE_NAME,
        "appium:appPackage":       APP_PACKAGE,
        "appium:appActivity":      APP_ACTIVITY,
        "appium:automationName":   "UiAutomator2",
        "appium:noReset":          True,
        "appium:autoGrantPermissions": True,
        "appium:newCommandTimeout":          120,
        # Android 12+ device réel : ignore hidden_api_policy SecurityException
        "appium:ignoreHiddenApiPolicyError":  True,
        "appium:skipDeviceInitialization":    False,
        "appium:disableWindowAnimation":      True,
        "appium:skipUnlock":                  True,
    }
    if APP_PATH and Path(APP_PATH).exists():
        caps["appium:app"] = APP_PATH

    try:
        from selenium.webdriver.common.options import ArgOptions

        class _AppiumCaps(ArgOptions):
            def __init__(self, caps):
                super().__init__()
                self._caps = caps
            def to_capabilities(self):
                return self._caps

        driver = webdriver.Remote(
            command_executor=APPIUM_URL,
            options=_AppiumCaps(caps)
        )
        print("✅ Connexion Appium établie !")
        return driver
    except Exception as e:
        print(f"❌ Connexion Appium échouée : {e}")
        return None


# ============================================================================
# EXTRACTION UI
# ============================================================================

def get_full_ui(driver) -> dict:
    """
    Récupère la hiérarchie UI complète + screenshot.
    Retourne un dict structuré avec tous les éléments et une capture d'écran.
    """
    result = {
        "timestamp":   datetime.now().isoformat(),
        "page_source": "",
        "screenshot":  None,
        "elements":    [],
        "page_name":   "unknown",
    }

    try:
        # Page source XML
        result["page_source"] = driver.page_source

        # Screenshot en base64
        result["screenshot"] = driver.get_screenshot_as_base64()

        # Parser le XML
        root = ET.fromstring(result["page_source"])
        result["elements"] = _extract_all_elements(root)

        # Détection de la page courante
        result["page_name"] = _detect_page(result["elements"])

        print(f"📄 Page détectée : '{result['page_name']}' "
              f"({len(result['elements'])} éléments)")

    except Exception as e:
        print(f"⚠️  Erreur extraction UI : {e}")

    return result


def _extract_all_elements(node: ET.Element, depth: int = 0) -> list:
    """Parcourt récursivement le XML et extrait tous les éléments pertinents."""
    elements = []
    attrib   = node.attrib

    resource_id  = attrib.get("resource-id", "")
    text         = attrib.get("text", "")
    content_desc = attrib.get("content-desc", "")
    cls          = attrib.get("class", "").split(".")[-1]  # Nom court
    clickable    = attrib.get("clickable", "false") == "true"
    enabled      = attrib.get("enabled", "true") == "true"
    bounds       = attrib.get("bounds", "")

    # Garde uniquement les éléments utiles
    if resource_id or (text and len(text) < 120) or content_desc or clickable:
        short_id = resource_id.split("/")[-1] if "/" in resource_id else resource_id

        # Type sémantique de l'élément
        elem_type = _classify_element(cls, short_id, text, content_desc, clickable)

        elements.append({
            "type":         elem_type,
            "class":        cls,
            "resource_id":  resource_id,
            "short_id":     short_id,
            "text":         text,
            "content_desc": content_desc,
            "bounds":       bounds,
            "clickable":    clickable,
            "enabled":      enabled,
            "depth":        depth,
            # Locators Robot Framework prêts à l'emploi
            "locators": _build_locators(resource_id, short_id, text, content_desc, cls),
        })

    for child in node:
        elements.extend(_extract_all_elements(child, depth + 1))

    return elements


def _classify_element(cls: str, rid: str, text: str, desc: str, clickable: bool) -> str:
    """Détermine le type sémantique d'un élément UI."""
    combined = f"{cls} {rid} {text} {desc}".lower()

    if "edittext" in cls.lower():
        if any(k in combined for k in ["password", "mot_de_passe", "mdp", "pwd"]):
            return "password_field"
        if any(k in combined for k in ["username", "login", "email", "identifiant", "user"]):
            return "username_field"
        if any(k in combined for k in ["montant", "amount"]):
            return "amount_field"
        if any(k in combined for k in ["otp", "code", "pin", "sms"]):
            return "otp_field"
        return "input_field"

    if "button" in cls.lower() or (clickable and "btn" in combined):
        if any(k in combined for k in ["login", "connexion", "connect", "se_connect"]):
            return "login_button"
        if any(k in combined for k in ["submit", "valider", "confirm", "ok"]):
            return "submit_button"
        if any(k in combined for k in ["cancel", "annuler", "retour", "back"]):
            return "cancel_button"
        if any(k in combined for k in ["forgot", "oublie", "reset"]):
            return "forgot_password_link"
        return "button"

    if "textview" in cls.lower() and not clickable:
        if any(k in combined for k in ["title", "titre", "header"]):
            return "title"
        return "label"

    if "checkbox" in cls.lower():
        return "checkbox"

    if "imageview" in cls.lower():
        return "image"

    if clickable:
        return "clickable_element"

    return "element"


def _build_locators(resource_id: str, short_id: str, text: str,
                    content_desc: str, cls: str) -> dict:
    """Construit tous les locators possibles pour un élément."""
    locators = {}

    if resource_id:
        locators["by_id"]       = f"id:{resource_id}"
        locators["robot_id"]    = f"id={resource_id}"

    if text and len(text) < 60:
        locators["by_text"]     = f"xpath=//*[@text='{text}']"
        locators["by_text_contains"] = f"xpath=//*[contains(@text,'{text[:20]}')]"

    if content_desc:
        locators["by_desc"]     = f"accessibility id={content_desc}"

    if cls and text:
        short_cls = cls.split(".")[-1]
        locators["by_class_text"] = f"xpath=//{short_cls}[@text='{text}']"

    return locators


def _detect_page(elements: list) -> str:
    """Détecte la page courante par heuristique sur les resource_id."""
    ids_and_texts = " ".join(
        f"{e.get('short_id','')} {e.get('text','')} {e.get('content_desc','')}"
        for e in elements
    ).lower()

    scores = {}
    for page_name, keywords in KNOWN_PAGES.items():
        score = sum(1 for kw in keywords if kw in ids_and_texts)
        if score > 0:
            scores[page_name] = score

    if scores:
        return max(scores, key=scores.get)
    return "unknown"


# ============================================================================
# PROMPT GEMINI
# ============================================================================

def build_gemini_prompt(ui_data: dict) -> str:
    """
    Construit le prompt optimisé pour Gemini en fonction de la page détectée.
    """
    page      = ui_data["page_name"]
    elements  = ui_data["elements"]
    timestamp = ui_data["timestamp"]

    # Filtrer les éléments les plus utiles (interactifs)
    interactive = [
        e for e in elements
        if e["clickable"] or "field" in e["type"] or "button" in e["type"]
    ]

    # Sérialiser les locators disponibles
    locators_json = json.dumps([
        {
            "type":        e["type"],
            "short_id":    e["short_id"],
            "resource_id": e["resource_id"],
            "text":        e["text"],
            "content_desc": e["content_desc"],
            "enabled":     e["enabled"],
            "locators":    e["locators"],
        }
        for e in interactive
    ], indent=2, ensure_ascii=False)

    # Prompt structuré
    prompt = f"""Tu es un expert en automatisation de tests mobiles (Robot Framework + Appium).
Tu analyses la page actuelle d'une application bancaire mobile Android : MyBiat Retail.

## CONTEXTE
- Page détectée : **{page.upper()}**
- Application : {APP_PACKAGE}
- Timestamp   : {timestamp}
- Total éléments UI : {len(elements)} ({len(interactive)} interactifs)

## ÉLÉMENTS UI DÉTECTÉS (avec leurs locators Appium)

```json
{locators_json}
```

## TES MISSIONS

### 1. 🔍 ANALYSE DE LA PAGE
- Confirme ou corrige l'identification de la page (actuelle : {page})
- Résume en 2-3 phrases ce que l'utilisateur peut faire sur cet écran
- Identifie les éléments critiques à tester

### 2. 🏥 ÉVALUATION QUALITÉ DES LOCATORS
Pour chaque élément interactif, évalue :
- ✅ Robuste : resource_id stable et unique
- ⚠️  Fragile : basé uniquement sur text (peut changer avec les traductions)
- ❌ Manquant : aucun locator fiable
Donne un score global de robustesse (0-100%)

### 3. 🤖 GÉNÉRATION DE TESTS ROBOT FRAMEWORK
Génère des tests complets suivant le **Page Object Model (POM)** :

**a) Page Object** (`{page}_page.robot`)  
Keywords réutilisables pour interagir avec cette page.

**b) Tests Cases** (`test_{page}.robot`)  
Au moins 3 scénarios de test couvrant :
- Cas nominal (happy path)
- Cas d'erreur (champ vide, données invalides)
- Cas limite (timeout, réseau lent si applicable)

**c) Variables** (si applicable)  
Variables centralisées dans `variables_{page}.robot`

### 4. 💡 RECOMMANDATIONS SELF-HEALING
Liste les locators fragiles et propose des locators alternatifs plus robustes.
Format : `locator actuel → locator recommandé [raison]`

### 5. 🎯 PRIORITÉ DE TEST
Classe les éléments par ordre de priorité de test (1=critique, 3=mineur).

---
⚠️  IMPORTANT : Utilise UNIQUEMENT les resource_id et locators fournis ci-dessus.
Ne pas inventer de locators non présents dans les données réelles.
Génère du code Robot Framework valide, syntaxe 4 espaces, pas de tabs.
"""
    return prompt


# ============================================================================
# APPEL GEMINI API
# ============================================================================

def call_gemini(prompt: str, screenshot_b64: Optional[str] = None) -> str:
    """
    Envoie le prompt + screenshot à Gemini API.
    Compatible avec le nouveau SDK google-genai ET l'ancien google-generativeai.
    """
    if not GEMINI_OK:
        return "❌ Gemini non installé. Lancez : pip install google-genai"

    if not GEMINI_API_KEY:
        return "❌ GEMINI_API_KEY manquant dans .env"

    print(f"\n🤖 Envoi à Gemini ({GEMINI_MODEL}) [SDK: {GEMINI_SDK}]...")

    try:
        # ── NOUVEAU SDK : google-genai ──────────────────────────────────────
        if GEMINI_SDK == "new":
            client = genai.Client(api_key=GEMINI_API_KEY)

            # Construction du contenu (texte + image optionnelle)
            parts = [prompt]

            if screenshot_b64:
                img_bytes = base64.b64decode(screenshot_b64)
                parts.append(
                    genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                )
                print("   📸 Screenshot inclus dans le prompt")

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=parts,
            )
            return response.text

        # ── ANCIEN SDK : google-generativeai (fallback) ─────────────────────
        else:
            genai_old.configure(api_key=GEMINI_API_KEY)
            model = genai_old.GenerativeModel(GEMINI_MODEL)

            content = [prompt]
            if screenshot_b64:
                img_data = base64.b64decode(screenshot_b64)
                content.append({"mime_type": "image/png", "data": img_data})
                print("   📸 Screenshot inclus dans le prompt")

            response = model.generate_content(content)
            return response.text

    except Exception as e:
        return f"❌ Erreur Gemini : {e}"


# ============================================================================
# SAUVEGARDE DES RÉSULTATS
# ============================================================================

def save_results(ui_data: dict, gemini_response: str, output_dir: str = "ai_results"):
    """Sauvegarde les résultats : JSON, réponse Gemini, screenshot, tests Robot."""
    now      = datetime.now().strftime("%Y%m%d_%H%M%S")
    page     = ui_data["page_name"]
    out_path = Path(output_dir) / f"{now}_{page}"
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. UI Data JSON
    ui_export = {k: v for k, v in ui_data.items() if k != "screenshot"}
    with open(out_path / "ui_elements.json", "w", encoding="utf-8") as f:
        json.dump(ui_export, f, indent=2, ensure_ascii=False)

    # 2. Réponse Gemini complète
    with open(out_path / "gemini_analysis.md", "w", encoding="utf-8") as f:
        f.write(f"# Analyse Gemini — Page: {page}\n")
        f.write(f"_Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}_\n\n")
        f.write(gemini_response)

    # 3. Screenshot
    if ui_data.get("screenshot"):
        scr_dir = Path(SCREENSHOTS_DIR)
        scr_dir.mkdir(exist_ok=True)
        scr_path = scr_dir / f"{now}_{page}.png"
        with open(scr_path, "wb") as f:
            f.write(base64.b64decode(ui_data["screenshot"]))
        print(f"   📸 Screenshot : {scr_path}")

    # 4. Extraire et sauvegarder les blocs de code Robot Framework
    robot_blocks = _extract_robot_code(gemini_response)
    if robot_blocks:
        tests_dir = out_path / "robot_tests"
        tests_dir.mkdir(exist_ok=True)
        for i, (filename, content) in enumerate(robot_blocks.items()):
            robot_path = tests_dir / filename
            with open(robot_path, "w", encoding="utf-8") as f:
                f.write(content)
        print(f"   🤖 {len(robot_blocks)} fichier(s) Robot : {tests_dir}")

    print(f"\n✅ Résultats sauvegardés dans : {out_path}")
    return str(out_path)


def _extract_robot_code(text: str) -> dict:
    """Extrait les blocs de code Robot Framework de la réponse Gemini."""
    blocks = {}

    # Cherche les patterns : filename.robot suivi d'un bloc de code
    pattern = r'`{3}(?:robot|robotframework)?\n(.*?)`{3}'
    matches = re.findall(pattern, text, re.DOTALL)

    # Cherche aussi les noms de fichiers mentionnés
    filenames = re.findall(r'`([a-zA-Z0-9_]+\.robot)`', text)

    for i, (match) in enumerate(matches):
        content = match.strip()
        if content and ("***" in content or "Keywords" in content or "Test Cases" in content):
            # Trouver le nom de fichier correspondant si possible
            fname = filenames[i] if i < len(filenames) else f"test_{i+1}.robot"
            blocks[fname] = content

    return blocks


# ============================================================================
# AFFICHAGE CONSOLE
# ============================================================================

def print_ui_summary(ui_data: dict):
    """Affiche un résumé coloré des éléments UI dans le terminal."""
    elements = ui_data["elements"]
    page     = ui_data["page_name"]

    print(f"\n{'='*60}")
    print(f"  📱 PAGE : {page.upper()}")
    print(f"{'='*60}")

    # Grouper par type
    by_type = {}
    for e in elements:
        t = e["type"]
        by_type.setdefault(t, []).append(e)

    type_icons = {
        "login_button":      "🟢",
        "submit_button":     "🟢",
        "cancel_button":     "🔴",
        "username_field":    "📝",
        "password_field":    "🔐",
        "input_field":       "📝",
        "amount_field":      "💰",
        "otp_field":         "🔢",
        "checkbox":          "☑️ ",
        "forgot_password_link": "🔗",
        "button":            "🔘",
        "label":             "🏷️ ",
        "title":             "📌",
        "image":             "🖼️ ",
        "clickable_element": "👆",
        "element":           "◽",
    }

    for elem_type, elems in sorted(by_type.items()):
        icon = type_icons.get(elem_type, "◽")
        print(f"\n  {icon} {elem_type.upper()} ({len(elems)})")
        for e in elems[:5]:  # Max 5 par type
            rid   = e["short_id"] or "(no id)"
            text  = f'"{e["text"]}"' if e["text"] else ""
            state = "✅" if e["enabled"] else "🚫"
            print(f"     {state} [{rid}] {text}")

    print(f"\n  Total : {len(elements)} éléments")
    print(f"{'='*60}\n")


# ============================================================================
# POINT D'ENTRÉE PRINCIPAL
# ============================================================================

def run_inspection(save: bool = True, use_screenshot: bool = True) -> dict:
    """Lance une inspection complète : Appium → UI → Gemini."""

    print("\n" + "="*60)
    print("  🔍 AI UI INSPECTOR — MyBiat Test Automation")
    print("="*60)

    # 1. Connexion Appium
    driver = connect_appium()
    if not driver:
        print("❌ Impossible de se connecter au device. Vérifiez :")
        print("   • Appium lancé sur port 4723 : appium")
        print("   • Device connecté : adb devices")
        print("   • APP_PACKAGE dans .env correct")
        return {}

    try:
        # 2. Extraction UI
        print("\n🔎 Extraction de la hiérarchie UI...")
        ui_data = get_full_ui(driver)

        if not ui_data["elements"]:
            print("⚠️  Aucun élément UI détecté. App bien au premier plan ?")
            return {}

        # 3. Affichage résumé terminal
        print_ui_summary(ui_data)

        # 4. Construction du prompt Gemini
        prompt = build_gemini_prompt(ui_data)

        # 5. Appel Gemini (avec ou sans screenshot)
        screenshot = ui_data.get("screenshot") if use_screenshot else None
        gemini_response = call_gemini(prompt, screenshot)

        # 6. Affichage de la réponse
        print("\n" + "="*60)
        print("  🤖 ANALYSE GEMINI")
        print("="*60)
        print(gemini_response)

        # 7. Sauvegarde
        if save:
            print("\n💾 Sauvegarde des résultats...")
            output_path = save_results(ui_data, gemini_response)

        return {
            "page":            ui_data["page_name"],
            "elements_count":  len(ui_data["elements"]),
            "gemini_response": gemini_response,
        }

    finally:
        # Toujours fermer la session Appium
        try:
            driver.quit()
            print("\n🔌 Session Appium fermée.")
        except Exception:
            pass


def run_watch_mode(interval: int = 30):
    """Mode surveillance : inspecte l'UI toutes les N secondes."""
    print(f"\n👁️  Mode surveillance activé (intervalle : {interval}s)")
    print("   Ctrl+C pour arrêter\n")

    last_page = None
    iteration = 0

    while True:
        try:
            iteration += 1
            print(f"\n--- Itération {iteration} — {datetime.now().strftime('%H:%M:%S')} ---")

            result = run_inspection(save=(last_page is None))  # Sauvegarde si 1ère fois

            current_page = result.get("page", "unknown")
            if current_page != last_page:
                print(f"\n🔔 CHANGEMENT DE PAGE : {last_page} → {current_page}")
                run_inspection(save=True)  # Sauvegarde à chaque changement de page
                last_page = current_page
            else:
                print(f"   Page inchangée : {current_page}")

            print(f"\n⏱️  Prochaine inspection dans {interval}s...")
            time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n👋 Mode surveillance arrêté.")
            break


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI UI Inspector — Appium + Gemini pour MyBiat"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Mode surveillance continue (détecte les changements de page)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Intervalle en secondes pour le mode --watch (défaut: 30)"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Ne pas sauvegarder les résultats"
    )
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="N'inclut pas le screenshot dans le prompt Gemini (moins de tokens)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ai_results",
        help="Répertoire de sortie pour les résultats (défaut: ai_results)"
    )

    args = parser.parse_args()

    if args.watch:
        run_watch_mode(args.interval)
    else:
        run_inspection(
            save=not args.no_save,
            use_screenshot=not args.no_screenshot
        )