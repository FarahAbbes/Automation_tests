"""
MCP Appium Server for MyBiat Test Automation
Expose l'UI mobile (Appium) comme contexte à l'IA via MCP Protocol
Permet : inspection UI, self-healing des locators, exécution de tests

Outils exposés:
  - get_ui_hierarchy        → Arborescence complète de l'UI
  - find_element_by_strategies → Cherche un élément (multi-stratégies)
  - suggest_alternative_locators → Self-healing : propose des alternatives
  - execute_robot_test      → Lance un test Robot Framework
  - get_page_source         → XML brut de l'écran courant
  - take_screenshot         → Capture d'écran encodée base64
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
# CHARGEMENT AUTOMATIQUE DU .ENV
# ============================================================================
try:
    from dotenv import load_dotenv

    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent

    # Chercher config/.env (avec ou sans espace dans le nom du dossier)
    env_loaded = False
    for item in project_root.iterdir():
        if item.is_dir() and "config" in item.name.lower():
            env_path = item / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                print(f"✅ Variables d'environnement chargées depuis: {env_path}")
                env_loaded = True
                break

    if not env_loaded:
        env_root = project_root / ".env"
        if env_root.exists():
            load_dotenv(env_root)
            print(f"✅ Variables chargées depuis la racine: {env_root}")
        else:
            load_dotenv()

except ImportError:
    print("⚠️ Module 'python-dotenv' non installé")

# ============================================================================
# IMPORTS APPIUM (avec gestion d'absence)
# ============================================================================
try:
    from appium import webdriver
    from appium.options import AndroidOptions
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        NoSuchElementException,
        TimeoutException,
        WebDriverException
    )
    APPIUM_AVAILABLE = True
except ImportError:
    APPIUM_AVAILABLE = False
    print("⚠️ Appium non installé. Mode simulation activé.")
    print("   Installez avec: pip install Appium-Python-Client")

from mcp.server.fastmcp import FastMCP

# ============================================================================
# CONFIGURATION
# ============================================================================

mcp = FastMCP("Appium Context Server")

# Configuration Appium depuis .env
# Support des deux conventions de nommage
APPIUM_SERVER_URL = os.getenv("APPIUM_SERVER_URL", "")
APPIUM_HOST       = os.getenv("APPIUM_HOST", "http://127.0.0.1")
APPIUM_PORT       = os.getenv("APPIUM_PORT", "4723")

# Résoudre l'URL finale : APPIUM_SERVER_URL prioritaire, sinon HOST:PORT
if APPIUM_SERVER_URL:
    APPIUM_URL = APPIUM_SERVER_URL
else:
    APPIUM_URL = f"{APPIUM_HOST}:{APPIUM_PORT}"

# Android Device / Capabilities
# Support des deux conventions : DEVICE_NAME ou ANDROID_DEVICE_NAME
ANDROID_PLATFORM_VERSION = (
    os.getenv("PLATFORM_VERSION") or
    os.getenv("ANDROID_PLATFORM_VERSION") or
    "13.0"
)
ANDROID_DEVICE_NAME = (
    os.getenv("DEVICE_NAME") or
    os.getenv("ANDROID_DEVICE_NAME") or
    "emulator-5554"
)
APP_PACKAGE  = os.getenv("APP_PACKAGE",  "com.example.mybiat")
APP_ACTIVITY = os.getenv("APP_ACTIVITY", ".MainActivity")
APP_APK_PATH = os.getenv("APP_PATH",     os.getenv("APP_APK_PATH", ""))

# Timeouts
ELEMENT_TIMEOUT = int(os.getenv("ELEMENT_TIMEOUT", "10"))

# Répertoire des tests Robot Framework
TESTS_DIR       = os.getenv("TESTS_DIR", "tests")
SCREENSHOTS_DIR = os.getenv("SCREENSHOTS_DIR", "screenshots")

# ============================================================================
# UTILITAIRES INTERNES
# ============================================================================

def _get_driver() -> Optional[Any]:
    """
    Crée une session Appium avec la configuration du .env.
    Retourne None si Appium n'est pas disponible / pas connecté.
    """
    if not APPIUM_AVAILABLE:
        return None
    try:
        options = AndroidOptions()
        options.platform_version       = ANDROID_PLATFORM_VERSION
        options.device_name            = ANDROID_DEVICE_NAME
        options.app_package            = APP_PACKAGE
        options.app_activity           = APP_ACTIVITY
        options.no_reset               = True
        options.auto_grant_permissions = True

        # Utiliser le chemin APK si fourni (APP_PATH ou APP_APK_PATH dans .env)
        if APP_APK_PATH and Path(APP_APK_PATH).exists():
            options.app = APP_APK_PATH

        driver = webdriver.Remote(APPIUM_URL, options=options)
        return driver
    except Exception:
        return None


def _parse_ui_node(node: ET.Element, depth: int = 0) -> dict:
    """
    Parse récursivement un nœud XML de l'UI hierarchy.
    Retourne un dict structuré avec les attributs utiles pour l'IA.
    """
    attrib = node.attrib
    result = {
        "class":       attrib.get("class", ""),
        "resource_id": attrib.get("resource-id", ""),
        "content_desc": attrib.get("content-desc", ""),
        "text":        attrib.get("text", ""),
        "bounds":      attrib.get("bounds", ""),
        "clickable":   attrib.get("clickable", "false") == "true",
        "enabled":     attrib.get("enabled", "true") == "true",
        "depth":       depth,
        "children":    []
    }
    for child in node:
        result["children"].append(_parse_ui_node(child, depth + 1))
    return result


def _flatten_ui_elements(node: dict, elements: list = None) -> list:
    """
    Aplatit la hiérarchie UI en liste d'éléments interactifs uniquement.
    Filtre : clickable, ou avec resource_id, ou avec text.
    """
    if elements is None:
        elements = []

    resource_id = node.get("resource_id", "")
    text        = node.get("text", "")
    clickable   = node.get("clickable", False)
    cls         = node.get("class", "")

    # Garder seulement les éléments utiles
    if resource_id or (text and len(text) < 100) or clickable:
        elements.append({
            "class":       cls,
            "resource_id": resource_id,
            "text":        text,
            "content_desc": node.get("content_desc", ""),
            "bounds":      node.get("bounds", ""),
            "clickable":   clickable,
            "enabled":     node.get("enabled", True),
        })

    for child in node.get("children", []):
        _flatten_ui_elements(child, elements)

    return elements


def _score_locator_similarity(candidate: str, target: str) -> float:
    """
    Score de similarité entre deux locators (0.0 → 1.0).
    Utilisé pour le self-healing : trouver le meilleur remplaçant.
    """
    if not candidate or not target:
        return 0.0

    candidate_lower = candidate.lower()
    target_lower    = target.lower()

    if candidate_lower == target_lower:
        return 1.0

    # Mots communs (après split sur _ et camelCase)
    def tokenize(s):
        s = re.sub(r'([A-Z])', r'_\1', s).lower()
        return set(re.split(r'[_\-\.\s]+', s)) - {''}

    cand_tokens   = tokenize(candidate)
    target_tokens = tokenize(target)

    if not cand_tokens or not target_tokens:
        return 0.0

    intersection = cand_tokens & target_tokens
    union        = cand_tokens | target_tokens
    jaccard      = len(intersection) / len(union)

    # Bonus si l'un contient l'autre
    if target_lower in candidate_lower or candidate_lower in target_lower:
        jaccard = min(1.0, jaccard + 0.3)

    return round(jaccard, 3)


# ============================================================================
# MODE SIMULATION (si Appium pas connecté)
# Utile pour les tests sans device/émulateur
# ============================================================================

def _get_mock_page_source() -> str:
    """Génère un XML de simulation avec le vrai APP_PACKAGE du .env."""
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
# OUTILS MCP
# ============================================================================

@mcp.tool()
def get_ui_hierarchy(flatten: bool = False) -> dict[str, Any]:
    """
    Récupère la hiérarchie complète de l'UI de l'application mobile en cours.
    Retourne une arborescence structurée (ou aplatie) des éléments UI.

    Args:
        flatten: Si True, retourne une liste plate des éléments interactifs
                 au lieu de l'arborescence complète.

    Returns:
        Dict contenant la hiérarchie UI parsée, prête à être analysée par l'IA.
    """
    page_source = None
    simulation  = False

    # Essayer avec Appium réel
    if APPIUM_AVAILABLE:
        driver = _get_driver()
        if driver:
            try:
                page_source = driver.page_source
                driver.quit()
            except Exception:
                pass

    # Fallback : mode simulation
    if not page_source:
        page_source = _get_mock_page_source()
        simulation  = True

    try:
        root = ET.fromstring(page_source)
        hierarchy = _parse_ui_node(root)

        if flatten:
            elements = _flatten_ui_elements(hierarchy)
            return {
                "success":    True,
                "simulation": simulation,
                "mode":       "flat",
                "count":      len(elements),
                "elements":   elements
            }
        else:
            return {
                "success":    True,
                "simulation": simulation,
                "mode":       "tree",
                "hierarchy":  hierarchy
            }

    except ET.ParseError as e:
        return {
            "success": False,
            "error":   f"Erreur parsing XML: {e}",
            "raw":     page_source[:500]
        }


@mcp.tool()
def get_page_source() -> dict[str, Any]:
    """
    Retourne le XML brut de l'écran actuel (page source Appium).
    Utile pour l'IA afin d'analyser directement le XML complet.

    Returns:
        Dict avec le XML source de la page et les métadonnées de taille.
    """
    page_source = None
    simulation  = False

    if APPIUM_AVAILABLE:
        driver = _get_driver()
        if driver:
            try:
                page_source = driver.page_source
                driver.quit()
            except Exception:
                pass

    if not page_source:
        page_source = _get_mock_page_source()
        simulation  = True

    return {
        "success":    True,
        "simulation": simulation,
        "xml":        page_source,
        "size_bytes": len(page_source.encode("utf-8"))
    }


@mcp.tool()
def find_element_by_strategies(
    resource_id:  Optional[str] = None,
    text:         Optional[str] = None,
    content_desc: Optional[str] = None,
    class_name:   Optional[str] = None,
    xpath:        Optional[str] = None
) -> dict[str, Any]:
    """
    Cherche un élément UI avec plusieurs stratégies en cascade.
    Essaie chaque stratégie dans l'ordre jusqu'à en trouver une qui fonctionne.
    Essentiel pour le self-healing : si resource-id ne marche plus, tente text/xpath.

    Args:
        resource_id:  Ex: "com.example.mybiat:id/btn_login" ou "btn_login"
        text:         Texte visible de l'élément. Ex: "Se connecter"
        content_desc: Description d'accessibilité. Ex: "Login button"
        class_name:   Classe Android. Ex: "android.widget.Button"
        xpath:        XPath complet. Ex: "//Button[@text='Login']"

    Returns:
        Dict indiquant quelle stratégie a réussi et les attributs de l'élément trouvé.
    """
    results = {
        "success":          False,
        "found":            False,
        "strategy_used":    None,
        "element_details":  None,
        "tried_strategies": [],
        "simulation":       False
    }

    if APPIUM_AVAILABLE:
        driver = _get_driver()
        if driver:
            try:
                strategies = []
                if resource_id:
                    # Normaliser : ajouter le package si absent
                    rid = resource_id
                    if ":" not in rid and APP_PACKAGE:
                        rid = f"{APP_PACKAGE}:id/{rid}"
                    strategies.append(("resource_id", AppiumBy.ID, rid))

                if text:
                    strategies.append(("text",
                        AppiumBy.XPATH, f"//*[@text='{text}']"))

                if content_desc:
                    strategies.append(("content_desc",
                        AppiumBy.ACCESSIBILITY_ID, content_desc))

                if class_name:
                    strategies.append(("class_name",
                        AppiumBy.CLASS_NAME, class_name))

                if xpath:
                    strategies.append(("xpath", AppiumBy.XPATH, xpath))

                for strategy_name, by, value in strategies:
                    results["tried_strategies"].append(strategy_name)
                    try:
                        wait = WebDriverWait(driver, timeout=ELEMENT_TIMEOUT)
                        element = wait.until(
                            EC.presence_of_element_located((by, value))
                        )
                        results.update({
                            "success":       True,
                            "found":         True,
                            "strategy_used": strategy_name,
                            "element_details": {
                                "resource_id":  element.get_attribute("resourceId"),
                                "text":         element.text,
                                "content_desc": element.get_attribute("contentDescription"),
                                "class":        element.get_attribute("className"),
                                "bounds":       element.get_attribute("bounds"),
                                "enabled":      element.is_enabled(),
                                "displayed":    element.is_displayed(),
                            }
                        })
                        break
                    except (NoSuchElementException, TimeoutException):
                        continue

                driver.quit()
                results["success"] = True
                return results

            except Exception as e:
                results["error"] = str(e)

    # Mode simulation : chercher dans le mock XML
    results["simulation"] = True
    results["success"]    = True

    try:
        root = ET.fromstring(_get_mock_page_source())

        def search_mock(node, strategy, value):
            attrib = node.attrib
            if strategy == "resource_id":
                rid = attrib.get("resource-id", "")
                if value in rid or rid.endswith(value):
                    return attrib
            elif strategy == "text":
                if attrib.get("text", "") == value:
                    return attrib
            elif strategy == "content_desc":
                if attrib.get("content-desc", "") == value:
                    return attrib
            elif strategy == "class_name":
                if attrib.get("class", "") == value:
                    return attrib
            for child in node:
                found = search_mock(child, strategy, value)
                if found:
                    return found
            return None

        strategies_to_try = []
        if resource_id:
            strategies_to_try.append(("resource_id", resource_id))
        if text:
            strategies_to_try.append(("text", text))
        if content_desc:
            strategies_to_try.append(("content_desc", content_desc))
        if class_name:
            strategies_to_try.append(("class_name", class_name))

        for strategy_name, value in strategies_to_try:
            results["tried_strategies"].append(strategy_name)
            found = search_mock(root, strategy_name, value)
            if found:
                results.update({
                    "found":         True,
                    "strategy_used": strategy_name,
                    "element_details": {
                        "resource_id":  found.get("resource-id", ""),
                        "text":         found.get("text", ""),
                        "content_desc": found.get("content-desc", ""),
                        "class":        found.get("class", ""),
                        "bounds":       found.get("bounds", ""),
                        "enabled":      found.get("enabled", "true") == "true",
                        "displayed":    True
                    }
                })
                break

    except ET.ParseError:
        pass

    return results


@mcp.tool()
def suggest_alternative_locators(
    broken_locator_id: str,
    context_hint:      Optional[str] = None
) -> dict[str, Any]:
    """
    ⭐ SELF-HEALING : Propose des locators alternatifs pour un locator cassé.
    Analyse l'UI actuelle et trouve les meilleurs candidats de remplacement
    basés sur la similarité sémantique.

    Args:
        broken_locator_id: L'ID du locator cassé (ex: "btn_login_old")
        context_hint: Indice sur le rôle de l'élément (ex: "bouton de connexion")

    Returns:
        Dict avec les alternatives triées par score de confiance décroissant.
    """
    # Récupérer tous les éléments de l'UI actuelle
    ui_result = get_ui_hierarchy(flatten=True)

    if not ui_result["success"]:
        return {
            "success":      False,
            "error":        "Impossible de récupérer l'UI",
            "alternatives": []
        }

    elements    = ui_result.get("elements", [])
    simulation  = ui_result.get("simulation", False)
    alternatives = []

    for elem in elements:
        rid   = elem.get("resource_id", "")
        text  = elem.get("text", "")
        desc  = elem.get("content_desc", "")
        cls   = elem.get("class", "")

        # Calculer les scores de similarité
        scores = []

        if rid:
            # Extraire l'ID court (sans package)
            short_id = rid.split("/")[-1] if "/" in rid else rid
            score_rid = _score_locator_similarity(short_id, broken_locator_id)
            scores.append(score_rid)
        else:
            scores.append(0.0)

        # Bonus si le context_hint correspond au text/desc
        context_bonus = 0.0
        if context_hint:
            hint_lower = context_hint.lower()
            if text and hint_lower in text.lower():
                context_bonus = 0.2
            elif desc and hint_lower in desc.lower():
                context_bonus = 0.15

        max_score = max(scores) + context_bonus

        if max_score > 0.1:  # Seuil minimum
            alternatives.append({
                "resource_id":       rid,
                "text":              text,
                "content_desc":      desc,
                "class":             cls,
                "bounds":            elem.get("bounds", ""),
                "confidence_score":  round(min(1.0, max_score), 3),
                "suggested_locators": _build_locator_suggestions(elem)
            })

    # Trier par score décroissant, garder top 5
    alternatives.sort(key=lambda x: x["confidence_score"], reverse=True)
    alternatives = alternatives[:5]

    recommendation = None
    if alternatives:
        best = alternatives[0]
        recommendation = (
            f"Remplacer '{broken_locator_id}' par "
            f"'{best['suggested_locators'][0]}' "
            f"(confiance: {best['confidence_score']*100:.0f}%)"
        )

    return {
        "success":          True,
        "simulation":       simulation,
        "broken_locator":   broken_locator_id,
        "alternatives_count": len(alternatives),
        "alternatives":     alternatives,
        "recommendation":   recommendation
    }


def _build_locator_suggestions(element: dict) -> list[str]:
    """Construit plusieurs suggestions de locators pour un élément."""
    suggestions = []
    rid  = element.get("resource_id", "")
    text = element.get("text", "")
    desc = element.get("content_desc", "")
    cls  = element.get("class", "")

    if rid:
        short_id = rid.split("/")[-1] if "/" in rid else rid
        suggestions.append(f"id:{short_id}")
        suggestions.append(f"resource-id:{rid}")

    if text:
        suggestions.append(f"xpath://*[@text='{text}']")

    if desc:
        suggestions.append(f"accessibility-id:{desc}")

    if cls and text:
        suggestions.append(f"xpath://{cls.split('.')[-1]}[@text='{text}']")

    return suggestions or ["Aucune suggestion disponible"]


@mcp.tool()
def take_screenshot(save_path: Optional[str] = None) -> dict[str, Any]:
    """
    Capture l'écran actuel de l'application mobile.
    Retourne l'image en base64 et optionnellement la sauvegarde sur disque.

    Args:
        save_path: Chemin optionnel pour sauvegarder le PNG (ex: "screenshots/test.png")

    Returns:
        Dict avec l'image en base64 et les métadonnées.
    """
    if APPIUM_AVAILABLE:
        driver = _get_driver()
        if driver:
            try:
                screenshot_b64 = driver.get_screenshot_as_base64()
                driver.quit()

                result = {
                    "success":    True,
                    "simulation": False,
                    "format":     "PNG",
                    "encoding":   "base64",
                    "data":       screenshot_b64,
                    "size_bytes": len(base64.b64decode(screenshot_b64))
                }

                if save_path:
                    path = Path(save_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(screenshot_b64))
                    result["saved_to"] = str(path)

                return result

            except Exception as e:
                pass

    # Mode simulation : image PNG 1x1 pixel transparente
    MOCK_PNG_B64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
        "DwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    return {
        "success":    True,
        "simulation": True,
        "format":     "PNG",
        "encoding":   "base64",
        "data":       MOCK_PNG_B64,
        "note":       "Image simulée (Appium non connecté)"
    }


@mcp.tool()
def execute_robot_test(
    test_file:   str,
    test_tags:   Optional[str]  = None,
    test_name:   Optional[str]  = None,
    output_dir:  str            = "results"
) -> dict[str, Any]:
    """
    Lance l'exécution d'un fichier de test Robot Framework.
    Retourne les résultats, statistiques et logs.

    Args:
        test_file:  Chemin du fichier .robot à exécuter (relatif à TESTS_DIR)
        test_tags:  Tags à exécuter (ex: "login" ou "smoke"). None = tous les tests.
        test_name:  Nom exact du test à exécuter. None = tous les tests.
        output_dir: Répertoire de sortie pour les rapports Allure/Robot.

    Returns:
        Dict avec le statut d'exécution, statistiques pass/fail et logs.
    """
    project_root = Path(__file__).resolve().parent.parent
    full_test_path = None

    # Résoudre le chemin du fichier de test
    for candidate in [
        Path(test_file),
        project_root / test_file,
        project_root / TESTS_DIR / test_file
    ]:
        if candidate.exists():
            full_test_path = candidate
            break

    if not full_test_path:
        return {
            "success": False,
            "error":   f"Fichier de test introuvable: {test_file}",
            "searched_paths": [str(project_root / test_file),
                               str(project_root / TESTS_DIR / test_file)]
        }

    # Construire la commande robot
    output_path = project_root / output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python", "-m", "robot",
        "--outputdir", str(output_path),
        "--nostatusrc",  # Ne pas échouer le process Python si tests échouent
        "--log",    "log.html",
        "--report", "report.html",
        "--output", "output.xml",
    ]

    if test_tags:
        cmd += ["--include", test_tags]
    if test_name:
        cmd += ["--test", test_name]

    cmd.append(str(full_test_path))

    # Exécuter
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max
        )

        # Parser les statistiques depuis stdout
        stdout    = proc.stdout
        returncode = proc.returncode

        # Extraire les stats Robot Framework depuis la sortie
        stats = _parse_robot_output(stdout)

        return {
            "success":      True,
            "returncode":   returncode,
            "passed":       stats["passed"],
            "failed":       stats["failed"],
            "skipped":      stats["skipped"],
            "total":        stats["total"],
            "all_passed":   stats["failed"] == 0 and stats["total"] > 0,
            "output_dir":   str(output_path),
            "log_file":     str(output_path / "log.html"),
            "report_file":  str(output_path / "report.html"),
            "stdout_tail":  stdout[-2000:] if stdout else "",
            "stderr_tail":  proc.stderr[-1000:] if proc.stderr else ""
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error":   "Timeout: le test a dépassé 5 minutes"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error":   "Robot Framework non trouvé. Installez: pip install robotframework"
        }
    except Exception as e:
        return {
            "success": False,
            "error":   str(e)
        }


def _parse_robot_output(stdout: str) -> dict:
    """Parse la sortie Robot Framework pour extraire les statistiques."""
    stats = {"passed": 0, "failed": 0, "skipped": 0, "total": 0}

    if not stdout:
        return stats

    # Pattern : "X tests, X passed, X failed"
    pattern = r"(\d+) tests?,\s*(\d+) passed,\s*(\d+) failed"
    match   = re.search(pattern, stdout, re.IGNORECASE)
    if match:
        stats["total"]  = int(match.group(1))
        stats["passed"] = int(match.group(2))
        stats["failed"] = int(match.group(3))

    # Pattern alternatif pour les suites
    pattern2 = r"(\d+) critical tests?,\s*(\d+) passed"
    match2   = re.search(pattern2, stdout, re.IGNORECASE)
    if match2 and stats["total"] == 0:
        stats["passed"] = int(match2.group(2))

    return stats


# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("MCP APPIUM SERVER - DÉMARRAGE")
    print("="*60)
    print(f"   Appium URL:    {APPIUM_URL}")
    print(f"   Package:       {APP_PACKAGE}")
    print(f"   Activity:      {APP_ACTIVITY}")
    print(f"   Device:        {ANDROID_DEVICE_NAME}")
    print(f"   Android:       {ANDROID_PLATFORM_VERSION}")
    print(f"   Appium SDK:    {'✅ Disponible' if APPIUM_AVAILABLE else '⚠️ Non installé (simulation)'}")
    print("\n🚀 Serveur MCP Appium prêt!")
    print("="*60 + "\n")

    mcp.run()