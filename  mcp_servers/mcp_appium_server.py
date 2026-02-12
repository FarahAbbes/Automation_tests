"""
MCP Appium Server for MyBiat Test Automation
Expose Appium context (UI hierarchy, test execution) to AI agents via MCP Protocol
"""

import os
import json
import base64
import subprocess
from typing import Any, Optional
from datetime import datetime
from pathlib import Path

# Appium imports
try:
    from appium import webdriver
    from appium.options.android import UiAutomator2Options
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.common.exceptions import NoSuchElementException, TimeoutException
    APPIUM_AVAILABLE = True
except ImportError:
    APPIUM_AVAILABLE = False
    print("⚠️ Appium not installed. Run: pip install Appium-Python-Client")

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("Appium Context Server")

# Appium configuration
APPIUM_SERVER_URL = os.getenv("APPIUM_SERVER_URL", "http://localhost:4723")
APP_PATH = os.getenv("APP_PATH")
DEVICE_NAME = os.getenv("DEVICE_NAME", "emulator-5554")
PLATFORM_VERSION = os.getenv("PLATFORM_VERSION", "11.0")
APP_PACKAGE = os.getenv("APP_PACKAGE", "com.mybiat.retail")
APP_ACTIVITY = os.getenv("APP_ACTIVITY", ".MainActivity")

# Global driver instance
driver = None


def get_driver():
    """
    Récupère ou crée une instance du driver Appium.
    
    Returns:
        WebDriver instance ou None si erreur
    """
    global driver
    
    if driver is not None:
        try:
            # Vérifier si le driver est toujours actif
            driver.current_activity
            return driver
        except:
            driver = None
    
    if not APPIUM_AVAILABLE:
        return None
    
    try:
        # Configuration Appium
        options = UiAutomator2Options()
        options.platform_name = "Android"
        options.device_name = DEVICE_NAME
        options.platform_version = PLATFORM_VERSION
        
        if APP_PATH:
            options.app = APP_PATH
        else:
            options.app_package = APP_PACKAGE
            options.app_activity = APP_ACTIVITY
            options.no_reset = True
        
        options.automation_name = "UiAutomator2"
        options.new_command_timeout = 300
        
        driver = webdriver.Remote(APPIUM_SERVER_URL, options=options)
        return driver
        
    except Exception as e:
        print(f"❌ Erreur connexion Appium: {e}")
        return None


@mcp.tool()
def get_ui_hierarchy() -> dict[str, Any]:
    """
    Récupère la hiérarchie complète de l'UI Android en temps réel.
    Expose l'arborescence XML pour analyse par l'IA.
    
    Returns:
        Dict contenant le XML source et un résumé des éléments
    """
    try:
        drv = get_driver()
        if drv is None:
            return {
                "success": False,
                "error": "Driver Appium non disponible",
                "ui_hierarchy": None
            }
        
        # Récupérer le page source (XML)
        page_source = drv.page_source
        
        # Extraire des stats basiques
        elements_count = page_source.count('<node')
        clickable_count = page_source.count('clickable="true"')
        
        # Extraire les IDs des éléments
        import re
        resource_ids = re.findall(r'resource-id="([^"]+)"', page_source)
        unique_ids = list(set([rid for rid in resource_ids if rid]))
        
        return {
            "success": True,
            "page_source": page_source,
            "stats": {
                "total_elements": elements_count,
                "clickable_elements": clickable_count,
                "unique_resource_ids": len(unique_ids)
            },
            "resource_ids": unique_ids[:20],  # Limiter à 20 pour lisibilité
            "current_activity": drv.current_activity,
            "current_package": drv.current_package
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ui_hierarchy": None
        }


@mcp.tool()
def find_element_by_strategies(element_identifier: str) -> dict[str, Any]:
    """
    Cherche un élément avec plusieurs stratégies (id, xpath, text, accessibility).
    Utilisé pour le self-healing quand un locator échoue.
    
    Args:
        element_identifier: ID, text ou description de l'élément
    
    Returns:
        Dict contenant l'élément trouvé et la stratégie utilisée
    """
    try:
        drv = get_driver()
        if drv is None:
            return {
                "success": False,
                "error": "Driver Appium non disponible"
            }
        
        strategies = [
            ("id", AppiumBy.ID, element_identifier),
            ("id_full", AppiumBy.ID, f"{APP_PACKAGE}:id/{element_identifier}"),
            ("accessibility_id", AppiumBy.ACCESSIBILITY_ID, element_identifier),
            ("xpath_id", AppiumBy.XPATH, f'//*[@resource-id="{element_identifier}"]'),
            ("xpath_id_contains", AppiumBy.XPATH, f'//*[contains(@resource-id, "{element_identifier}")]'),
            ("xpath_text", AppiumBy.XPATH, f'//*[@text="{element_identifier}"]'),
            ("xpath_text_contains", AppiumBy.XPATH, f'//*[contains(@text, "{element_identifier}")]'),
            ("xpath_desc", AppiumBy.XPATH, f'//*[@content-desc="{element_identifier}"]'),
        ]
        
        results = []
        
        for strategy_name, strategy_type, locator in strategies:
            try:
                elements = drv.find_elements(strategy_type, locator)
                if elements:
                    for idx, elem in enumerate(elements[:3]):  # Max 3 éléments
                        elem_info = {
                            "strategy": strategy_name,
                            "locator": locator,
                            "index": idx,
                            "found": True
                        }
                        
                        # Extraire les attributs
                        try:
                            elem_info["text"] = elem.text or ""
                            elem_info["resource_id"] = elem.get_attribute("resource-id") or ""
                            elem_info["class"] = elem.get_attribute("class") or ""
                            elem_info["clickable"] = elem.get_attribute("clickable") == "true"
                            elem_info["enabled"] = elem.get_attribute("enabled") == "true"
                            elem_info["bounds"] = elem.get_attribute("bounds") or ""
                        except:
                            pass
                        
                        results.append(elem_info)
                        
            except NoSuchElementException:
                continue
            except Exception as e:
                results.append({
                    "strategy": strategy_name,
                    "locator": locator,
                    "found": False,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "element_identifier": element_identifier,
            "strategies_tried": len(strategies),
            "strategies_successful": len([r for r in results if r.get("found")]),
            "results": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": []
        }


@mcp.tool()
def suggest_alternative_locators(broken_locator: str, context: str = "") -> dict[str, Any]:
    """
    Analyse l'UI actuelle et suggère des locators alternatifs pour remplacer
    un locator cassé (self-healing).
    
    Args:
        broken_locator: Le locator qui ne fonctionne plus
        context: Contexte additionnel (ex: "bouton de login")
    
    Returns:
        Dict contenant des suggestions de locators alternatifs
    """
    try:
        drv = get_driver()
        if drv is None:
            return {
                "success": False,
                "error": "Driver Appium non disponible"
            }
        
        # Récupérer l'UI hierarchy
        page_source = drv.page_source
        
        # Extraire des locators potentiels
        import re
        
        suggestions = []
        
        # Chercher des IDs similaires
        resource_ids = re.findall(r'resource-id="([^"]+)"', page_source)
        for rid in set(resource_ids):
            if rid and (broken_locator.lower() in rid.lower() or 
                       any(word in rid.lower() for word in context.lower().split())):
                suggestions.append({
                    "type": "resource-id",
                    "locator": rid,
                    "xpath": f'//*[@resource-id="{rid}"]',
                    "confidence": "high" if broken_locator in rid else "medium"
                })
        
        # Chercher des texts similaires
        texts = re.findall(r'text="([^"]+)"', page_source)
        for text in set(texts):
            if text and context and any(word.lower() in text.lower() 
                                       for word in context.split()):
                suggestions.append({
                    "type": "text",
                    "locator": text,
                    "xpath": f'//*[@text="{text}"]',
                    "confidence": "medium"
                })
        
        # Chercher des content-desc similaires
        descs = re.findall(r'content-desc="([^"]+)"', page_source)
        for desc in set(descs):
            if desc and context and any(word.lower() in desc.lower() 
                                       for word in context.split()):
                suggestions.append({
                    "type": "content-desc",
                    "locator": desc,
                    "xpath": f'//*[@content-desc="{desc}"]',
                    "confidence": "medium"
                })
        
        return {
            "success": True,
            "broken_locator": broken_locator,
            "context": context,
            "suggestions_count": len(suggestions),
            "suggestions": suggestions[:10],  # Top 10
            "recommendation": _generate_locator_recommendation(suggestions, broken_locator)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestions": []
        }


def _generate_locator_recommendation(suggestions: list, broken_locator: str) -> str:
    """
    Génère une recommandation textuelle pour les locators alternatifs.
    
    Args:
        suggestions: Liste des suggestions
        broken_locator: L'ancien locator cassé
    
    Returns:
        Recommandation sous forme de texte
    """
    if not suggestions:
        return "Aucun locator alternatif trouvé. Vérifiez l'UI hierarchy manuellement."
    
    high_confidence = [s for s in suggestions if s.get("confidence") == "high"]
    
    if high_confidence:
        best = high_confidence[0]
        return f"✅ Recommandation forte: Utilisez {best['type']} = '{best['locator']}'"
    
    if suggestions:
        best = suggestions[0]
        return f"⚠️ Suggestion: Testez {best['type']} = '{best['locator']}' (confiance moyenne)"
    
    return "Aucune recommandation fiable"


@mcp.tool()
def execute_robot_test(test_file: str, tags: str = "") -> dict[str, Any]:
    """
    Exécute un test Robot Framework et retourne les résultats.
    
    Args:
        test_file: Chemin vers le fichier .robot
        tags: Tags Robot Framework à exécuter (ex: "smoke")
    
    Returns:
        Dict contenant les résultats de l'exécution
    """
    try:
        # Construire la commande robot
        cmd = ["robot"]
        
        if tags:
            cmd.extend(["--include", tags])
        
        # Output directory
        output_dir = Path("/home/claude/robot_results")
        output_dir.mkdir(exist_ok=True)
        
        cmd.extend([
            "--outputdir", str(output_dir),
            "--output", "output.xml",
            "--log", "log.html",
            "--report", "report.html",
            test_file
        ])
        
        # Exécuter
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max
        )
        
        # Parser les résultats
        output_xml = output_dir / "output.xml"
        test_results = _parse_robot_output(output_xml) if output_xml.exists() else {}
        
        return {
            "success": result.returncode == 0,
            "test_file": test_file,
            "return_code": result.returncode,
            "stdout": result.stdout[-1000:],  # Derniers 1000 chars
            "stderr": result.stderr[-1000:] if result.stderr else "",
            "results": test_results,
            "output_dir": str(output_dir)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Test timeout (>5 minutes)",
            "test_file": test_file
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "test_file": test_file
        }


def _parse_robot_output(output_xml_path: Path) -> dict:
    """
    Parse le fichier output.xml de Robot Framework.
    
    Args:
        output_xml_path: Chemin vers output.xml
    
    Returns:
        Dict avec statistiques des tests
    """
    try:
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(output_xml_path)
        root = tree.getroot()
        
        # Extraire les stats
        stats = root.find(".//statistics/total/stat")
        
        if stats is not None:
            return {
                "total": int(stats.get("pass", 0)) + int(stats.get("fail", 0)),
                "passed": int(stats.get("pass", 0)),
                "failed": int(stats.get("fail", 0)),
                "pass_rate": f"{(int(stats.get('pass', 0)) / (int(stats.get('pass', 0)) + int(stats.get('fail', 0))) * 100):.1f}%" 
                            if (int(stats.get("pass", 0)) + int(stats.get("fail", 0))) > 0 else "0%"
            }
        
        return {"error": "Could not parse statistics"}
        
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def capture_screenshot(name: str = "screenshot") -> dict[str, Any]:
    """
    Capture l'écran actuel de l'application.
    
    Args:
        name: Nom du fichier (sans extension)
    
    Returns:
        Dict contenant le chemin de la capture et les données base64
    """
    try:
        drv = get_driver()
        if drv is None:
            return {
                "success": False,
                "error": "Driver Appium non disponible"
            }
        
        # Créer le dossier screenshots
        screenshots_dir = Path("/home/claude/screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        
        # Générer le nom de fichier
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = screenshots_dir / filename
        
        # Capturer
        drv.save_screenshot(str(filepath))
        
        # Lire en base64 pour transmission
        with open(filepath, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        return {
            "success": True,
            "filename": filename,
            "filepath": str(filepath),
            "size_bytes": filepath.stat().st_size,
            "base64_data": img_base64[:100] + "...",  # Aperçu
            "current_activity": drv.current_activity
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def get_current_screen_info() -> dict[str, Any]:
    """
    Récupère les informations sur l'écran actuel (activité, package, orientation).
    
    Returns:
        Dict contenant les informations de l'écran
    """
    try:
        drv = get_driver()
        if drv is None:
            return {
                "success": False,
                "error": "Driver Appium non disponible"
            }
        
        return {
            "success": True,
            "current_activity": drv.current_activity,
            "current_package": drv.current_package,
            "orientation": drv.orientation,
            "window_size": drv.get_window_size(),
            "contexts": drv.contexts,
            "current_context": drv.current_context
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def analyze_ui_for_testability() -> dict[str, Any]:
    """
    Analyse l'UI actuelle et identifie les éléments testables et leurs locators.
    Utile pour la génération automatique de tests.
    
    Returns:
        Dict contenant l'analyse de testabilité de l'UI
    """
    try:
        drv = get_driver()
        if drv is None:
            return {
                "success": False,
                "error": "Driver Appium non disponible"
            }
        
        page_source = drv.page_source
        
        # Analyser les éléments interactifs
        import re
        
        testable_elements = {
            "buttons": [],
            "input_fields": [],
            "checkboxes": [],
            "switches": [],
            "clickable_texts": []
        }
        
        # Parser le XML
        from xml.etree import ElementTree as ET
        root = ET.fromstring(page_source)
        
        for elem in root.iter():
            if elem.get("clickable") == "true":
                elem_info = {
                    "resource_id": elem.get("resource-id", ""),
                    "text": elem.get("text", ""),
                    "class": elem.get("class", ""),
                    "content_desc": elem.get("content-desc", ""),
                    "bounds": elem.get("bounds", "")
                }
                
                # Classifier l'élément
                class_name = elem.get("class", "").lower()
                if "button" in class_name:
                    testable_elements["buttons"].append(elem_info)
                elif "edittext" in class_name or "input" in class_name:
                    testable_elements["input_fields"].append(elem_info)
                elif "checkbox" in class_name:
                    testable_elements["checkboxes"].append(elem_info)
                elif "switch" in class_name:
                    testable_elements["switches"].append(elem_info)
                elif elem_info["text"]:
                    testable_elements["clickable_texts"].append(elem_info)
        
        # Générer des recommandations
        recommendations = []
        
        if testable_elements["buttons"]:
            recommendations.append(
                f"✓ {len(testable_elements['buttons'])} boutons détectés → Créer tests de clic"
            )
        
        if testable_elements["input_fields"]:
            recommendations.append(
                f"✓ {len(testable_elements['input_fields'])} champs de saisie → Créer tests de validation"
            )
        
        if testable_elements["checkboxes"]:
            recommendations.append(
                f"✓ {len(testable_elements['checkboxes'])} checkboxes → Créer tests de sélection"
            )
        
        return {
            "success": True,
            "current_activity": drv.current_activity,
            "testable_elements": testable_elements,
            "total_interactive_elements": sum(len(v) for v in testable_elements.values()),
            "recommendations": recommendations
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def close_driver() -> dict[str, Any]:
    """
    Ferme la session Appium proprement.
    
    Returns:
        Dict confirmant la fermeture
    """
    global driver
    
    try:
        if driver is not None:
            driver.quit()
            driver = None
            return {
                "success": True,
                "message": "Driver Appium fermé avec succès"
            }
        else:
            return {
                "success": True,
                "message": "Aucun driver actif à fermer"
            }
    except Exception as e:
        driver = None
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    # Vérifier que les variables d'environnement sont configurées
    if not APPIUM_AVAILABLE:
        print("❌ Appium Python Client n'est pas installé!")
        print("Installez-le: pip install Appium-Python-Client")
        exit(1)
    
    if not APP_PATH and not APP_PACKAGE:
        print("⚠️  APP_PATH ou APP_PACKAGE doit être configuré!")
        print("Exportez: export APP_PATH='/path/to/app.apk'")
        print("Ou: export APP_PACKAGE='com.mybiat.retail'")
    
    print("✅ MCP Appium Server démarré")
    print(f"🔗 Appium URL: {APPIUM_SERVER_URL}")
    print(f"📱 Device: {DEVICE_NAME}")
    print(f"📦 Package: {APP_PACKAGE}")
    
    # Démarrer le serveur MCP
    mcp.run()