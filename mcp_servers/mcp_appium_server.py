"""
MCP Appium Server — MyBiat Test Automation
==========================================
Expose l'UI mobile (Appium) comme contexte structuré à l'IA via MCP Protocol.

Outils exposés:
  • get_ui_hierarchy              → Arborescence complète de l'UI
  • get_page_source               → XML brut de l'écran courant
  • find_element_by_strategies    → Recherche multi-stratégies d'un élément
  • suggest_alternative_locators  → Self-healing : propose des alternatives
  • execute_robot_test            → Lance un test Robot Framework
  • take_screenshot               → Capture d'écran encodée base64
  • analyze_current_screen        → Analyse enrichie : classification sémantique
                                    + détection page + locators RF prêts à l'emploi

Architecture:
  - Simulation automatique si Appium non connecté (mode dev/CI sans device)
  - Détection de page par heuristique ou Gemini Vision (si screenshot dispo)
  - Locators classifiés : robust / fragile / missing
"""

import os
import re
import base64
import subprocess
import json
import xml.etree.ElementTree as ET
from typing import Any, Optional
from pathlib import Path

# ============================================================================
# CHARGEMENT .ENV
# ============================================================================
try:
    from dotenv import load_dotenv

    _candidates = [
        Path(__file__).resolve().parent.parent / "config" / ".env",
        Path(__file__).resolve().parent / "config" / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / "config" / ".env",
        Path.cwd() / ".env",
    ]
    for _p in _candidates:
        if _p.exists():
            load_dotenv(_p)
            print(f"✅ .env chargé : {_p}")
            break
    else:
        load_dotenv()
except ImportError:
    print("⚠️  python-dotenv absent — variables système utilisées")

# ============================================================================
# IMPORTS APPIUM  (graceful degradation → simulation si absent)
# ============================================================================
try:
    from appium import webdriver
    from appium.options.android import UiAutomator2Options
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        NoSuchElementException, TimeoutException, WebDriverException,
    )
    APPIUM_AVAILABLE = True
except ImportError:
    APPIUM_AVAILABLE = False
    print("⚠️  Appium non installé — mode simulation activé")
    print("   pip install Appium-Python-Client selenium")

from mcp.server.fastmcp import FastMCP

# ============================================================================
# CONFIGURATION  (toutes les valeurs proviennent du .env)
# ============================================================================
mcp = FastMCP("Appium Context Server")

APPIUM_SERVER_URL        = os.getenv("APPIUM_SERVER_URL", "")
APPIUM_HOST              = os.getenv("APPIUM_HOST", "http://127.0.0.1")
APPIUM_PORT              = os.getenv("APPIUM_PORT", "4723")
APPIUM_URL               = APPIUM_SERVER_URL or f"{APPIUM_HOST}:{APPIUM_PORT}"

ANDROID_PLATFORM_VERSION = (
    os.getenv("PLATFORM_VERSION") or
    os.getenv("ANDROID_PLATFORM_VERSION") or "13.0"
)
ANDROID_DEVICE_NAME = (
    os.getenv("DEVICE_NAME") or
    os.getenv("ANDROID_DEVICE_NAME") or "emulator-5554"
)
APP_PACKAGE    = os.getenv("APP_PACKAGE",  "com.example.mybiat")
APP_ACTIVITY   = os.getenv("APP_ACTIVITY", ".MainActivity")
APP_APK_PATH   = os.getenv("APP_PATH", os.getenv("APP_APK_PATH", ""))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

ELEMENT_TIMEOUT  = int(os.getenv("ELEMENT_TIMEOUT", "10"))
TESTS_DIR        = os.getenv("TESTS_DIR", "tests")
SCREENSHOTS_DIR  = os.getenv("SCREENSHOTS_DIR", "screenshots")

# ── Pages connues — heuristique multi-app (override par Gemini si screenshot) ──
KNOWN_PAGES = {
    # Auth
    "login":         ["login", "connexion", "username", "password", "mot_de_passe",
                      "edit_username", "edit_password", "btn_login", "se_connecter",
                      "sign_in", "signin", "email", "tv_forgot"],
    "register":      ["register", "signup", "sign_up", "inscription", "create_account",
                      "btn_register", "confirm_password"],
    "otp":           ["otp", "code_sms", "verification", "sms_code", "pin", "verify"],
    # Navigation
    "home":          ["home", "accueil", "dashboard", "main", "feed", "homepage",
                      "welcome", "categories", "search", "what_would", "menu_home"],
    "dashboard":     ["dashboard", "solde", "compte", "balance", "overview"],
    # E-commerce / Food
    "menu":          ["menu", "food", "restaurant", "dish", "meal", "cuisine",
                      "categories", "all_items", "product_list"],
    "cart":          ["cart", "panier", "basket", "order", "checkout", "commande",
                      "total", "btn_checkout", "add_to_cart"],
    "product":       ["product", "item", "detail", "description", "price", "rating",
                      "add_to_cart", "quantity", "btn_add"],
    "search":        ["search", "recherche", "filter", "query", "search_bar"],
    # Compte utilisateur
    "profile":       ["profile", "profil", "settings", "parametres", "mon_compte",
                      "account", "my_account", "personal"],
    "notifications": ["notification", "alerte", "bell", "notif", "alert"],
    # Bancaire MyBiat
    "transfer":      ["transfer", "virement", "beneficiaire", "montant", "amount"],
    "accounts":      ["accounts", "comptes", "liste_comptes", "account_list"],
    "cards":         ["card", "carte", "visa", "mastercard", "carte_bancaire"],
}

# ============================================================================
# UTILITAIRES APPIUM
# ============================================================================

def _get_driver() -> Optional[Any]:
    """
    Crée une session Appium (UiAutomator2Options).
    Retourne None si Appium indisponible ou si la connexion échoue.
    """
    if not APPIUM_AVAILABLE:
        return None
    try:
        options = UiAutomator2Options()
        options.platform_name                  = "Android"
        options.platform_version               = ANDROID_PLATFORM_VERSION
        options.device_name                    = ANDROID_DEVICE_NAME
        options.app_package                    = APP_PACKAGE
        options.app_activity                   = APP_ACTIVITY
        options.no_reset                       = True
        options.auto_grant_permissions         = True
        options.new_command_timeout            = int(os.getenv("ELEMENT_TIMEOUT", "60"))
        options.ignore_hidden_api_policy_error = True

        if (APP_APK_PATH
                and not APP_APK_PATH.startswith("/data/app/")
                and Path(APP_APK_PATH).exists()):
            options.app = APP_APK_PATH

        driver = webdriver.Remote(APPIUM_URL, options=options)
        print(f"✅ Session Appium: {driver.current_package}/{driver.current_activity}")
        return driver
    except Exception as e:
        print(f"⚠️  Session Appium échouée ({e}) → simulation activée")
        return None


def _get_mock_page_source() -> str:
    """XML de simulation pour la page login MyBiat."""
    pkg = APP_PACKAGE
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <android.widget.FrameLayout resource-id="android:id/content" bounds="[0,0][1080,2340]">
    <android.widget.LinearLayout bounds="[0,0][1080,2340]">
      <android.widget.TextView resource-id="{pkg}:id/tv_title"
        text="MyBiat - Connexion" bounds="[0,50][1080,150]" clickable="false"/>
      <android.widget.EditText resource-id="{pkg}:id/edit_username"
        text="" content-desc="Champ identifiant" bounds="[100,200][980,320]"
        clickable="true" enabled="true"/>
      <android.widget.EditText resource-id="{pkg}:id/edit_password"
        text="" content-desc="Champ mot de passe" bounds="[100,350][980,470]"
        clickable="true" enabled="true"/>
      <android.widget.CheckBox resource-id="{pkg}:id/cb_remember_me"
        text="Se souvenir de moi" bounds="[100,500][600,580]"
        clickable="true" enabled="true"/>
      <android.widget.Button resource-id="{pkg}:id/btn_login"
        text="Se connecter" bounds="[100,620][980,740]"
        clickable="true" enabled="true"/>
      <android.widget.TextView resource-id="{pkg}:id/tv_forgot_password"
        text="Mot de passe oublié ?" bounds="[300,780][780,840]"
        clickable="true"/>
    </android.widget.LinearLayout>
  </android.widget.FrameLayout>
</hierarchy>"""


# ============================================================================
# UTILITAIRES UI — CLASSIFICATION & EXTRACTION
# ============================================================================

def _classify_element(cls: str, rid: str, text: str, desc: str, clickable: bool) -> str:
    """Détermine le type sémantique d'un élément UI (label lisible par l'IA)."""
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


def _build_rf_locators(resource_id: str, short_id: str, text: str,
                        content_desc: str, cls: str) -> dict:
    """Construit tous les locators Robot Framework disponibles pour un élément."""
    locators = {}
    if resource_id:
        locators["by_id"]     = f"id={resource_id}"
        locators["appium_id"] = f"id:{resource_id}"
    if text and len(text) < 60:
        locators["by_text"]          = f"xpath=//*[@text='{text}']"
        locators["by_text_contains"] = f"xpath=//*[contains(@text,'{text[:20]}')]"
    if content_desc:
        locators["by_accessibility"] = f"accessibility id={content_desc}"
    if cls and text:
        short_cls = cls.split(".")[-1]
        locators["by_class_text"] = f"xpath=//{short_cls}[@text='{text}']"
    return locators


def _compute_locator_quality(resource_id: str, text: str, locators: dict) -> str:
    """
    Calcule la qualité du locator selon la chaîne de priorité :
      resource-id → robust | accessibility id → robust | text → fragile | rien → missing
    """
    if resource_id:
        return "robust"
    if locators.get("by_accessibility") or locators.get("appium_a11y"):
        return "robust"
    if text or locators.get("by_text") or locators.get("by_xpath"):
        return "fragile"
    return "missing"


def _extract_enriched_elements(node: ET.Element, depth: int = 0) -> list:
    """Parse récursivement l'XML UI → liste d'éléments enrichis avec locators RF."""
    elements = []
    attrib   = node.attrib

    resource_id  = attrib.get("resource-id", "")
    text         = attrib.get("text", "")
    content_desc = attrib.get("content-desc", "")
    cls          = attrib.get("class", "")
    clickable    = attrib.get("clickable", "false") == "true"
    enabled      = attrib.get("enabled", "true") == "true"
    bounds       = attrib.get("bounds", "")
    short_id     = resource_id.split("/")[-1] if "/" in resource_id else resource_id

    if resource_id or (text and len(text) < 120) or content_desc or clickable:
        elem_type       = _classify_element(cls, short_id, text, content_desc, clickable)
        locators        = _build_rf_locators(resource_id, short_id, text, content_desc, cls)
        locator_quality = _compute_locator_quality(resource_id, text, locators)

        # Fallback xpath par position pour EditText/Button sans identifiant
        if locator_quality == "missing":
            if "EditText" in cls:
                locators["by_xpath"] = f"xpath=//android.widget.EditText"
                locator_quality = "fragile"
            elif "Button" in cls:
                locators["by_xpath"] = f"xpath=//android.widget.Button"
                locator_quality = "fragile"

        elements.append({
            "type":           elem_type,
            "class":          cls,
            "resource_id":    resource_id,
            "short_id":       short_id,
            "text":           text,
            "content_desc":   content_desc,
            "bounds":         bounds,
            "clickable":      clickable,
            "enabled":        enabled,
            "depth":          depth,
            "locators":       locators,
            "locator_quality": locator_quality,
        })

    for child in node:
        elements.extend(_extract_enriched_elements(child, depth + 1))
    return elements


def _compute_locator_stats(elements: list) -> dict:
    """Calcule les statistiques de couverture des locators."""
    robust  = sum(1 for e in elements if e.get("locator_quality") == "robust")
    fragile = sum(1 for e in elements if e.get("locator_quality") == "fragile")
    missing = sum(1 for e in elements if e.get("locator_quality") == "missing")
    total   = len(elements)
    covered = robust + fragile
    return {
        "robust":           robust,
        "fragile":          fragile,
        "missing":          missing,
        "coverage_percent": round(covered / total * 100, 1) if total > 0 else 0.0,
    }


# ============================================================================
# DÉTECTION DE PAGE  (heuristique + Gemini Vision)
# ============================================================================

def _detect_page(elements: list) -> str:
    """Détection heuristique de la page courante via mots-clés des resource_id/text."""
    ids_and_texts = " ".join(
        f"{e.get('short_id', '')} {e.get('text', '')} {e.get('content_desc', '')}"
        for e in elements
    ).lower()
    scores = {
        page: sum(1 for kw in kws if kw in ids_and_texts)
        for page, kws in KNOWN_PAGES.items()
    }
    best = {p: s for p, s in scores.items() if s > 0}
    return max(best, key=best.get) if best else "unknown"


def _detect_page_with_gemini(elements: list, screenshot_b64: str) -> str:
    """
    Détection intelligente via Gemini Vision — plus fiable que l'heuristique.
    Utilisée uniquement si un vrai screenshot est disponible (>500 bytes).
    Fallback transparent vers _detect_page() en cas d'erreur.
    """
    if not GEMINI_API_KEY or not screenshot_b64:
        return _detect_page(elements)

    # Ignorer les screenshots simulés (trop petits)
    try:
        if len(base64.b64decode(screenshot_b64)) < 500:
            return _detect_page(elements)
    except Exception:
        return _detect_page(elements)

    ui_summary = ", ".join(
        e.get("text", e.get("short_id", ""))
        for e in elements[:15]
        if e.get("text") or e.get("short_id")
    )

    prompt = f"""Look at this mobile app screenshot carefully.

Identify the current page/screen type from this list:
login, register, otp, home, dashboard, menu, cart, product, search,
profile, notifications, transfer, accounts, cards, settings, unknown

UI text elements visible: {ui_summary}

Rules:
- Answer with ONLY the page name (one word, lowercase)
- If you see a search bar + food categories + list of items -> "home"
- If you see username/password fields -> "login"
- If you see a shopping cart/order summary -> "cart"
- If you see a food/product detail with price -> "product"
- If unsure -> "unknown"

Page name:"""

    try:
        import urllib.request, json as _json
        payload = _json.dumps({
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": screenshot_b64}},
            ]}],
            "generationConfig": {"maxOutputTokens": 20, "temperature": 0.1},
        }).encode("utf-8")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        )
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = _json.loads(resp.read().decode())
            raw    = result["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
            page   = re.sub(r"[^a-z_]", "", raw.split()[0] if raw.split() else "unknown")
            valid  = list(KNOWN_PAGES.keys()) + ["unknown", "product", "search", "cart"]
            return page if page in valid else _detect_page(elements)
    except Exception as e:
        print(f"⚠️  Gemini page detection failed: {e} — fallback heuristique")
        return _detect_page(elements)


# ============================================================================
# UTILITAIRES SELF-HEALING
# ============================================================================

def _score_locator_similarity(candidate: str, target: str) -> float:
    """Score de similarité Jaccard entre deux identifiants (0.0 → 1.0)."""
    if not candidate or not target:
        return 0.0
    if candidate.lower() == target.lower():
        return 1.0

    def tokenize(s):
        s = re.sub(r"([A-Z])", r"_\1", s).lower()
        return set(re.split(r"[_\-\.\s]+", s)) - {""}

    cand_tok = tokenize(candidate)
    tgt_tok  = tokenize(target)
    if not cand_tok or not tgt_tok:
        return 0.0

    jaccard = len(cand_tok & tgt_tok) / len(cand_tok | tgt_tok)
    if target.lower() in candidate.lower() or candidate.lower() in target.lower():
        jaccard = min(1.0, jaccard + 0.3)
    return round(jaccard, 3)


def _build_locator_suggestions(element: dict) -> list[str]:
    """Construit plusieurs suggestions de locators pour un élément (self-healing)."""
    suggestions = []
    rid  = element.get("resource_id", "")
    text = element.get("text", "")
    desc = element.get("content_desc", "")
    cls  = element.get("class", "")

    if rid:
        short_id = rid.split("/")[-1] if "/" in rid else rid
        suggestions += [f"id:{short_id}", f"resource-id:{rid}"]
    if text:
        suggestions.append(f"xpath://*[@text='{text}']")
    if desc:
        suggestions.append(f"accessibility-id:{desc}")
    if cls and text:
        suggestions.append(f"xpath://{cls.split('.')[-1]}[@text='{text}']")

    return suggestions or ["Aucune suggestion disponible"]


def _parse_robot_output(stdout: str) -> dict:
    """Parse la sortie de Robot Framework pour extraire les statistiques pass/fail."""
    stats = {"passed": 0, "failed": 0, "skipped": 0, "total": 0}
    if not stdout:
        return stats
    match = re.search(r"(\d+) tests?,\s*(\d+) passed,\s*(\d+) failed", stdout, re.IGNORECASE)
    if match:
        stats.update(
            total=int(match.group(1)),
            passed=int(match.group(2)),
            failed=int(match.group(3)),
        )
    return stats


def _parse_ui_node(node: ET.Element, depth: int = 0) -> dict:
    """Parse récursivement un nœud XML → dict structuré (pour get_ui_hierarchy)."""
    attrib = node.attrib
    result = {
        "class":        attrib.get("class", ""),
        "resource_id":  attrib.get("resource-id", ""),
        "content_desc": attrib.get("content-desc", ""),
        "text":         attrib.get("text", ""),
        "bounds":       attrib.get("bounds", ""),
        "clickable":    attrib.get("clickable", "false") == "true",
        "enabled":      attrib.get("enabled", "true") == "true",
        "depth":        depth,
        "children":     [_parse_ui_node(child, depth + 1) for child in node],
    }
    return result


def _flatten_ui_elements(node: dict, elements: list = None) -> list:
    """Aplatit la hiérarchie UI en liste d'éléments interactifs."""
    if elements is None:
        elements = []
    if (node.get("resource_id")
            or (node.get("text") and len(node.get("text", "")) < 100)
            or node.get("clickable")):
        elements.append({k: node[k] for k in
                         ("class", "resource_id", "text", "content_desc",
                          "bounds", "clickable", "enabled")})
    for child in node.get("children", []):
        _flatten_ui_elements(child, elements)
    return elements


# ============================================================================
# OUTILS MCP
# ============================================================================

@mcp.tool()
def get_ui_hierarchy(flatten: bool = False) -> dict[str, Any]:
    """
    Récupère la hiérarchie complète de l'UI.

    Args:
        flatten: Si True, retourne une liste plate des éléments interactifs.

    Returns:
        Arborescence structurée ou liste plate selon `flatten`.
    """
    page_source, simulation = _fetch_page_source()
    try:
        root      = ET.fromstring(page_source)
        hierarchy = _parse_ui_node(root)
        if flatten:
            elements = _flatten_ui_elements(hierarchy)
            return {"success": True, "simulation": simulation,
                    "mode": "flat", "count": len(elements), "elements": elements}
        return {"success": True, "simulation": simulation,
                "mode": "tree", "hierarchy": hierarchy}
    except ET.ParseError as e:
        return {"success": False, "error": f"Erreur parsing XML: {e}"}


@mcp.tool()
def get_page_source() -> dict[str, Any]:
    """
    Retourne le XML brut de l'écran actuel (page source Appium).
    """
    page_source, simulation = _fetch_page_source()
    return {
        "success":    True,
        "simulation": simulation,
        "xml":        page_source,
        "size_bytes": len(page_source.encode("utf-8")),
    }


@mcp.tool()
def find_element_by_strategies(
    resource_id:  Optional[str] = None,
    text:         Optional[str] = None,
    content_desc: Optional[str] = None,
    class_name:   Optional[str] = None,
    xpath:        Optional[str] = None,
) -> dict[str, Any]:
    """
    Cherche un élément UI avec plusieurs stratégies en cascade.
    Si une stratégie échoue, les suivantes sont tentées automatiquement.

    Args:
        resource_id:  Ex: "com.example.mybiat:id/btn_login" ou simplement "btn_login"
        text:         Texte visible. Ex: "Se connecter"
        content_desc: Description d'accessibilité
        class_name:   Classe Android. Ex: "android.widget.Button"
        xpath:        XPath complet

    Returns:
        Quelle stratégie a réussi + attributs de l'élément trouvé.
    """
    results = {
        "success": False, "found": False,
        "strategy_used": None, "element_details": None,
        "tried_strategies": [], "simulation": False,
    }

    if APPIUM_AVAILABLE:
        driver = _get_driver()
        if driver:
            try:
                strategies = []
                if resource_id:
                    rid = resource_id if ":" in resource_id else f"{APP_PACKAGE}:id/{resource_id}"
                    strategies.append(("resource_id", AppiumBy.ID, rid))
                if text:
                    strategies.append(("text", AppiumBy.XPATH, f"//*[@text='{text}']"))
                if content_desc:
                    strategies.append(("content_desc", AppiumBy.ACCESSIBILITY_ID, content_desc))
                if class_name:
                    strategies.append(("class_name", AppiumBy.CLASS_NAME, class_name))
                if xpath:
                    strategies.append(("xpath", AppiumBy.XPATH, xpath))

                for strategy_name, by, value in strategies:
                    results["tried_strategies"].append(strategy_name)
                    try:
                        element = WebDriverWait(driver, ELEMENT_TIMEOUT).until(
                            EC.presence_of_element_located((by, value))
                        )
                        results.update(success=True, found=True, strategy_used=strategy_name,
                                       element_details={
                                           "resource_id":  element.get_attribute("resourceId"),
                                           "text":         element.text,
                                           "content_desc": element.get_attribute("contentDescription"),
                                           "class":        element.get_attribute("className"),
                                           "bounds":       element.get_attribute("bounds"),
                                           "enabled":      element.is_enabled(),
                                           "displayed":    element.is_displayed(),
                                       })
                        break
                    except (NoSuchElementException, TimeoutException):
                        continue

                driver.quit()
                results["success"] = True
                return results
            except Exception as e:
                results["error"] = str(e)
                try: driver.quit()
                except Exception: pass

    # ── Mode simulation ────────────────────────────────────────────────────
    results["simulation"] = True
    results["success"]    = True
    try:
        root = ET.fromstring(_get_mock_page_source())
        for strategy_name, value in [
            ("resource_id", resource_id), ("text", text),
            ("content_desc", content_desc), ("class_name", class_name),
        ]:
            if not value:
                continue
            results["tried_strategies"].append(strategy_name)
            found = _search_mock_xml(root, strategy_name, value)
            if found:
                results.update(found=True, strategy_used=strategy_name, element_details={
                    "resource_id":  found.get("resource-id", ""),
                    "text":         found.get("text", ""),
                    "content_desc": found.get("content-desc", ""),
                    "class":        found.get("class", ""),
                    "bounds":       found.get("bounds", ""),
                    "enabled":      found.get("enabled", "true") == "true",
                    "displayed":    True,
                })
                break
    except ET.ParseError:
        pass
    return results


def _search_mock_xml(node: ET.Element, strategy: str, value: str) -> Optional[dict]:
    """Recherche récursive dans l'XML simulé."""
    attrib = node.attrib
    match  = False
    if strategy == "resource_id":
        rid   = attrib.get("resource-id", "")
        match = value in rid or rid.endswith(value)
    elif strategy == "text":
        match = attrib.get("text", "") == value
    elif strategy == "content_desc":
        match = attrib.get("content-desc", "") == value
    elif strategy == "class_name":
        match = attrib.get("class", "") == value
    if match:
        return attrib
    for child in node:
        result = _search_mock_xml(child, strategy, value)
        if result:
            return result
    return None


@mcp.tool()
def suggest_alternative_locators(
    broken_locator_id: str,
    context_hint:      Optional[str] = None,
) -> dict[str, Any]:
    """
    SELF-HEALING : Propose des locators alternatifs pour un locator cassé.

    Args:
        broken_locator_id: L'identifiant du locator cassé (ex: "btn_login_old")
        context_hint: Description du rôle de l'élément (ex: "bouton de connexion")

    Returns:
        Liste d'alternatives triées par score de confiance décroissant.
    """
    ui_result = get_ui_hierarchy(flatten=True)
    if not ui_result["success"]:
        return {"success": False, "error": "Impossible de récupérer l'UI", "alternatives": []}

    elements     = ui_result.get("elements", [])
    simulation   = ui_result.get("simulation", False)
    alternatives = []

    for elem in elements:
        rid      = elem.get("resource_id", "")
        short_id = rid.split("/")[-1] if "/" in rid else rid
        score    = _score_locator_similarity(short_id, broken_locator_id) if rid else 0.0

        if context_hint:
            hint = context_hint.lower()
            if hint in elem.get("text", "").lower() or hint in elem.get("content_desc", "").lower():
                score = min(1.0, score + 0.2)

        if score > 0.1:
            alternatives.append({
                "resource_id":        rid,
                "text":               elem.get("text", ""),
                "content_desc":       elem.get("content_desc", ""),
                "class":              elem.get("class", ""),
                "bounds":             elem.get("bounds", ""),
                "confidence_score":   round(score, 3),
                "suggested_locators": _build_locator_suggestions(elem),
            })

    alternatives.sort(key=lambda x: x["confidence_score"], reverse=True)
    alternatives = alternatives[:5]

    recommendation = None
    if alternatives:
        best = alternatives[0]
        recommendation = (
            f"Remplacer '{broken_locator_id}' par "
            f"'{best['suggested_locators'][0]}' "
            f"(confiance : {best['confidence_score']*100:.0f}%)"
        )

    return {
        "success":            True,
        "simulation":         simulation,
        "broken_locator":     broken_locator_id,
        "alternatives_count": len(alternatives),
        "alternatives":       alternatives,
        "recommendation":     recommendation,
    }


@mcp.tool()
def take_screenshot(save_path: Optional[str] = None) -> dict[str, Any]:
    """
    Capture l'écran actuel de l'application mobile.

    Args:
        save_path: Chemin optionnel pour sauvegarder le PNG localement.

    Returns:
        Image encodée en base64 + métadonnées.
    """
    if APPIUM_AVAILABLE:
        driver = _get_driver()
        if driver:
            try:
                screenshot_b64 = driver.get_screenshot_as_base64()
                driver.quit()
                result = {
                    "success": True, "simulation": False,
                    "format": "PNG", "encoding": "base64",
                    "data": screenshot_b64,
                    "size_bytes": len(base64.b64decode(screenshot_b64)),
                }
                if save_path:
                    path = Path(save_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(base64.b64decode(screenshot_b64))
                    result["saved_to"] = str(path)
                return result
            except Exception:
                pass

    # Image simulée 1×1 px
    MOCK_PNG = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
        "DwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    return {
        "success": True, "simulation": True,
        "format": "PNG", "encoding": "base64",
        "data": MOCK_PNG, "note": "Image simulée (Appium non connecté)",
    }


@mcp.tool()
def execute_robot_test(
    test_file:  str,
    test_tags:  Optional[str] = None,
    test_name:  Optional[str] = None,
    output_dir: str           = "results",
) -> dict[str, Any]:
    """
    Lance l'exécution d'un fichier de test Robot Framework.

    Args:
        test_file:  Chemin du fichier .robot
        test_tags:  Tags à inclure (ex: "login", "smoke")
        test_name:  Nom exact d'un test à exécuter
        output_dir: Répertoire pour les rapports Allure/RF

    Returns:
        Statistiques pass/fail + chemin des rapports.
    """
    project_root = Path(__file__).resolve().parent.parent
    full_path    = None

    for candidate in [
        Path(test_file),
        project_root / test_file,
        project_root / TESTS_DIR / test_file,
    ]:
        if candidate.exists():
            full_path = candidate
            break

    if not full_path:
        return {"success": False, "error": f"Fichier introuvable: {test_file}"}

    output_path = project_root / output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python", "-m", "robot",
        "--outputdir", str(output_path),
        "--nostatusrc",
        "--log",    "log.html",
        "--report", "report.html",
        "--output", "output.xml",
    ]
    if test_tags:
        cmd += ["--include", test_tags]
    if test_name:
        cmd += ["--test", test_name]
    cmd.append(str(full_path))

    try:
        proc  = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        stats = _parse_robot_output(proc.stdout)
        return {
            "success":     True,
            "returncode":  proc.returncode,
            "passed":      stats["passed"],
            "failed":      stats["failed"],
            "skipped":     stats["skipped"],
            "total":       stats["total"],
            "all_passed":  stats["failed"] == 0 and stats["total"] > 0,
            "output_dir":  str(output_path),
            "log_file":    str(output_path / "log.html"),
            "report_file": str(output_path / "report.html"),
            "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
            "stderr_tail": proc.stderr[-1000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout : test dépassé 5 minutes"}
    except FileNotFoundError:
        return {"success": False, "error": "Robot Framework non trouvé (pip install robotframework)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def analyze_current_screen(include_screenshot: bool = True) -> dict[str, Any]:
    """
    ⭐ ANALYSE ENRICHIE DE L'ÉCRAN COURANT — outil principal de l'agent.

    Combine Appium + enrichissement sémantique en un seul appel MCP.
    Fournit à l'agent un contexte complet prêt pour injection dans un prompt LLM :
      • Éléments UI avec type sémantique (login_button, password_field…)
      • Détection automatique de la page (login, home, transfer…)
      • Locators Robot Framework pour chaque élément
      • Qualité des locators : robust / fragile / missing
      • Statistiques de couverture
      • Screenshot base64 optionnel

    Args:
        include_screenshot: Inclure le screenshot base64 dans la réponse.
    """
    page_source, simulation = _fetch_page_source()
    screenshot_b64          = None

    # Screenshot via Appium si disponible
    if APPIUM_AVAILABLE and not simulation and include_screenshot:
        driver = _get_driver()
        if driver:
            try:
                screenshot_b64 = driver.get_screenshot_as_base64()
                driver.quit()
            except Exception:
                try: driver.quit()
                except Exception: pass

    # Parse XML
    try:
        root     = ET.fromstring(page_source)
        elements = _extract_enriched_elements(root)
    except ET.ParseError as e:
        return {"success": False, "error": f"Erreur parsing XML: {e}"}

    # Détection de page
    page_name = (
        _detect_page_with_gemini(elements, screenshot_b64)
        if screenshot_b64
        else _detect_page(elements)
    )

    # Éléments interactifs uniquement (pour le prompt LLM)
    interactive = [
        e for e in elements
        if e["clickable"] or "field" in e["type"] or "button" in e["type"]
    ]

    locator_stats = _compute_locator_stats(elements)

    result = {
        "success":    True,
        "simulation": simulation,
        # Contexte page
        "page_name":    page_name,
        "app_package":  APP_PACKAGE,
        "app_activity": APP_ACTIVITY,
        # Éléments
        "total_elements":       len(elements),
        "interactive_elements": len(interactive),
        "elements":             elements,
        # Résumé pour le prompt (éléments interactifs uniquement)
        "interactive_summary": [
            {
                "type":            e["type"],
                "short_id":        e["short_id"],
                "resource_id":     e["resource_id"],
                "text":            e["text"],
                "content_desc":    e["content_desc"],
                "enabled":         e["enabled"],
                "locator_quality": e["locator_quality"],
                "locators":        e["locators"],
            }
            for e in interactive
        ],
        # Qualité globale
        "locator_stats": locator_stats,
        # Locators fragiles (surveiller pour self-healing)
        "fragile_locators": [
            {
                "short_id": e["short_id"],
                "type":     e["type"],
                "text":     e["text"],
                "locators": e["locators"],
                "reason":   "Basé sur le texte visible — sensible aux traductions",
            }
            for e in elements if e["locator_quality"] == "fragile"
        ],
        # Éléments sans locator (à corriger)
        "missing_locators": [
            {
                "class":  e["class"],
                "bounds": e["bounds"],
                "type":   e["type"],
                "reason": "Aucun resource-id, text ou content-desc disponible",
            }
            for e in elements if e["locator_quality"] == "missing"
        ],
    }

    # Screenshot optionnel
    if include_screenshot:
        if screenshot_b64:
            result["screenshot"] = {"encoding": "base64", "format": "PNG", "data": screenshot_b64}
        elif simulation:
            result["screenshot"] = {
                "encoding": "base64", "format": "PNG",
                "data": ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
                         "DwAChwGA60e6kgAAAABJRU5ErkJggg=="),
                "note": "Image simulée",
            }

    return result


# ============================================================================
# HELPER INTERNE — récupération page source (factorisée)
# ============================================================================

def _fetch_page_source() -> tuple[str, bool]:
    """
    Tente de récupérer le page source via Appium.
    Retourne (xml_string, simulation_bool).
    """
    if APPIUM_AVAILABLE:
        driver = _get_driver()
        if driver:
            try:
                source = driver.page_source
                driver.quit()
                return source, False
            except Exception:
                try: driver.quit()
                except Exception: pass
    return _get_mock_page_source(), True


# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  MCP APPIUM SERVER — DÉMARRAGE")
    print("=" * 60)
    print(f"   Appium URL     : {APPIUM_URL}")
    print(f"   App Package    : {APP_PACKAGE}")
    print(f"   App Activity   : {APP_ACTIVITY}")
    print(f"   Device         : {ANDROID_DEVICE_NAME}")
    print(f"   Android        : {ANDROID_PLATFORM_VERSION}")
    print(f"   Appium SDK     : {'✅ Disponible' if APPIUM_AVAILABLE else '⚠️  Simulation'}")
    print(f"   Gemini Vision  : {'✅ Configuré' if GEMINI_API_KEY else '⚠️  Heuristique only'}")
    print("\n   Outils exposés :")
    for tool in [
        "get_ui_hierarchy", "get_page_source", "find_element_by_strategies",
        "suggest_alternative_locators", "execute_robot_test",
        "take_screenshot", "analyze_current_screen",
    ]:
        print(f"   • {tool}")
    print("\n🚀 Serveur MCP prêt!\n" + "=" * 60 + "\n")
    mcp.run()