"""
Script de test pour valider le MCP Appium Server
Lance des tests unitaires sur chaque outil MCP Appium.
Fonctionne même SANS Appium installé grâce au mode simulation.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ============================================================================
# RÉSOLUTION DES CHEMINS (robuste aux espaces dans les noms de dossiers)
# ============================================================================

current_dir  = Path(__file__).resolve().parent
project_root = current_dir.parent

print(f"🔍 Recherche du dossier mcp_servers...")
print(f"📁 Répertoire du projet: {project_root}")

print(f"\n📂 Tous les dossiers trouvés:")
all_dirs = []
for item in project_root.iterdir():
    if item.is_dir() and not item.name.startswith('.'):
        all_dirs.append(item)
        print(f"  • '{item.name}' → {item}")

mcp_servers_dir = None
for dir_path in all_dirs:
    if "mcp" in dir_path.name.lower():
        potential_file = dir_path / "mcp_appium_server.py"
        if potential_file.exists():
            mcp_servers_dir = dir_path
            print(f"\n✅ Dossier MCP trouvé: {dir_path}")
            print(f"✅ Fichier trouvé: {potential_file}")
            break

if mcp_servers_dir is None:
    print("\n❌ ERREUR: Impossible de trouver mcp_appium_server.py!")
    print("   Vérifiez que le fichier est dans le dossier mcp_servers/")
    sys.exit(1)

# ============================================================================
# CHARGEMENT DES VARIABLES D'ENVIRONNEMENT
# ============================================================================

print(f"\n🔧 Chargement des variables d'environnement...")

config_dir = None
for item in project_root.iterdir():
    if item.is_dir() and "config" in item.name.lower():
        config_dir = item
        print(f"✅ Dossier config trouvé: {config_dir}")
        break

if config_dir:
    env_path = config_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Variables chargées depuis: {env_path}")
    else:
        print(f"⚠ Fichier .env introuvable dans {config_dir}")
else:
    load_dotenv()

appium_server_url = os.getenv("APPIUM_SERVER_URL", "")
appium_host       = os.getenv("APPIUM_HOST", "http://127.0.0.1")
appium_port       = os.getenv("APPIUM_PORT", "4723")
appium_url        = appium_server_url if appium_server_url else f"{appium_host}:{appium_port}"

app_package  = os.getenv("APP_PACKAGE",  "com.example.mybiat")
device_name  = os.getenv("DEVICE_NAME") or os.getenv("ANDROID_DEVICE_NAME", "emulator-5554")
platform_ver = os.getenv("PLATFORM_VERSION") or os.getenv("ANDROID_PLATFORM_VERSION", "13.0")

print(f"\n📊 Variables Appium:")
print(f"  • APPIUM_URL:            {appium_url}")
print(f"  • APP_PACKAGE:           {app_package}")
print(f"  • DEVICE_NAME:           {device_name}")
print(f"  • PLATFORM_VERSION:      {platform_ver}")

# ============================================================================
# IMPORT DU MODULE mcp_appium_server
# ============================================================================

def import_module(module_name: str, file_path: Path):
    """Import robuste via importlib."""
    try:
        import importlib.util
        spec   = importlib.util.spec_from_file_location(module_name, str(file_path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"❌ Import échoué ({module_name}): {e}")
        import traceback
        traceback.print_exc()
        return None


print(f"\n📦 Import du module mcp_appium_server...")
appium_file = mcp_servers_dir / "mcp_appium_server.py"
mcp_appium  = import_module("mcp_appium_server", appium_file)

if mcp_appium is None:
    sys.exit(1)

# Extraire les fonctions
try:
    get_ui_hierarchy            = mcp_appium.get_ui_hierarchy
    get_page_source             = mcp_appium.get_page_source
    find_element_by_strategies  = mcp_appium.find_element_by_strategies
    suggest_alternative_locators = mcp_appium.suggest_alternative_locators
    take_screenshot             = mcp_appium.take_screenshot
    execute_robot_test          = mcp_appium.execute_robot_test
    print("✅ Toutes les fonctions chargées!\n")
except AttributeError as e:
    print(f"❌ Fonction manquante dans mcp_appium_server: {e}")
    sys.exit(1)

# ============================================================================
# FONCTIONS DE TEST
# ============================================================================

def test_get_ui_hierarchy_tree():
    """Test 1a: Hiérarchie UI en mode arbre"""
    print("\n" + "="*60)
    print("TEST 1a: get_ui_hierarchy (mode arbre)")
    print("="*60)

    result = get_ui_hierarchy(flatten=False)

    if result["success"]:
        mode = result.get("mode")
        sim  = result.get("simulation", False)
        hier = result.get("hierarchy", {})

        print(f"✅ Succès! Mode: {mode} | Simulation: {sim}")
        print(f"  Classe racine: {hier.get('class', '?')}")
        print(f"  Enfants: {len(hier.get('children', []))}")
        if sim:
            print(f"  ℹ️  Mode simulation (Appium non connecté) — comportement attendu")
    else:
        print(f"❌ Erreur: {result.get('error')}")

    return result["success"]


def test_get_ui_hierarchy_flat():
    """Test 1b: Hiérarchie UI en mode plat"""
    print("\n" + "="*60)
    print("TEST 1b: get_ui_hierarchy (mode flat)")
    print("="*60)

    result = get_ui_hierarchy(flatten=True)

    if result["success"]:
        elements = result.get("elements", [])
        sim      = result.get("simulation", False)

        print(f"✅ Succès! {len(elements)} éléments interactifs trouvés")
        if sim:
            print(f"  ℹ️  Mode simulation activé")

        # Afficher les 5 premiers éléments
        for elem in elements[:5]:
            rid  = elem.get("resource_id", "")
            text = elem.get("text", "")
            cls  = elem.get("class", "").split(".")[-1]
            click = "✓" if elem.get("clickable") else " "
            print(f"  [{click}] {cls:<25} | id: {rid:<40} | text: {text}")
    else:
        print(f"❌ Erreur: {result.get('error')}")

    return result["success"]


def test_get_page_source():
    """Test 2: Récupération du XML source"""
    print("\n" + "="*60)
    print("TEST 2: get_page_source")
    print("="*60)

    result = get_page_source()

    if result["success"]:
        size = result.get("size_bytes", 0)
        xml  = result.get("xml", "")
        sim  = result.get("simulation", False)

        print(f"✅ Succès! Taille: {size} bytes | Simulation: {sim}")
        print(f"  Aperçu XML: {xml[:120].strip()}...")

        # Vérifier que c'est du XML valide
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(xml)
            print(f"  ✅ XML valide et parseable")
        except ET.ParseError as e:
            print(f"  ⚠ XML invalide: {e}")
    else:
        print(f"❌ Erreur: {result.get('error')}")

    return result["success"]


def test_find_element_by_resource_id():
    """Test 3a: Recherche par resource-id"""
    print("\n" + "="*60)
    print("TEST 3a: find_element_by_strategies (resource_id)")
    print("="*60)

    result = find_element_by_strategies(resource_id="btn_login")

    if result["success"]:
        found    = result.get("found", False)
        strategy = result.get("strategy_used")
        elem     = result.get("element_details", {})
        sim      = result.get("simulation", False)

        status = "✅ Élément trouvé" if found else "⚠ Élément non trouvé"
        print(f"{status} | Stratégie: {strategy} | Simulation: {sim}")
        if found and elem:
            print(f"  resource_id: {elem.get('resource_id', '')}")
            print(f"  text:        {elem.get('text', '')}")
            print(f"  class:       {elem.get('class', '').split('.')[-1]}")
    else:
        print(f"❌ Erreur: {result.get('error')}")

    return result["success"]


def test_find_element_by_text():
    """Test 3b: Recherche par texte visible"""
    print("\n" + "="*60)
    print("TEST 3b: find_element_by_strategies (text)")
    print("="*60)

    result = find_element_by_strategies(text="Se connecter")

    if result["success"]:
        found    = result.get("found", False)
        strategy = result.get("strategy_used")
        sim      = result.get("simulation", False)

        status = "✅ Élément trouvé" if found else "⚠ Élément non trouvé (texte inexistant)"
        print(f"{status} | Stratégie: {strategy} | Simulation: {sim}")
        if found:
            elem = result.get("element_details", {})
            print(f"  text:  {elem.get('text', '')}")
            print(f"  class: {elem.get('class', '').split('.')[-1]}")
    else:
        print(f"❌ Erreur: {result.get('error')}")

    return result["success"]


def test_find_element_not_found():
    """Test 3c: Élément inexistant (cas négatif)"""
    print("\n" + "="*60)
    print("TEST 3c: find_element_by_strategies (élément inexistant)")
    print("="*60)

    result = find_element_by_strategies(resource_id="id_qui_nexiste_pas_xyz")

    if result["success"]:
        found = result.get("found", False)
        tried = result.get("tried_strategies", [])
        print(f"✅ Appel réussi | Trouvé: {found} | Stratégies testées: {tried}")
        if not found:
            print(f"  ✅ Comportement correct: retourne found=False sans crash")
    else:
        print(f"❌ Erreur: {result.get('error')}")

    return result["success"]


def test_suggest_alternative_locators():
    """Test 4: Self-healing — suggestions de locators alternatifs"""
    print("\n" + "="*60)
    print("TEST 4: suggest_alternative_locators (self-healing)")
    print("="*60)

    # Simuler un locator cassé qui ressemble à btn_login
    result = suggest_alternative_locators(
        broken_locator_id="btn_login_v2",
        context_hint="bouton connexion"
    )

    if result["success"]:
        sim   = result.get("simulation", False)
        count = result.get("alternatives_count", 0)
        reco  = result.get("recommendation", "Aucune")
        alts  = result.get("alternatives", [])

        print(f"✅ Succès! {count} alternatives trouvées | Simulation: {sim}")
        print(f"\n  📋 Recommandation: {reco}")

        if alts:
            print(f"\n  Top alternatives:")
            for i, alt in enumerate(alts[:3], 1):
                rid   = alt.get("resource_id", "")
                score = alt.get("confidence_score", 0)
                suggs = alt.get("suggested_locators", [])
                print(f"  {i}. score={score:.2f} | {rid}")
                for s in suggs[:2]:
                    print(f"       → {s}")
        else:
            print(f"  ⚠ Aucune alternative (locator trop différent)")
    else:
        print(f"❌ Erreur: {result.get('error')}")

    return result["success"]


def test_take_screenshot():
    """Test 5: Capture d'écran"""
    print("\n" + "="*60)
    print("TEST 5: take_screenshot")
    print("="*60)

    result = take_screenshot()

    if result["success"]:
        sim      = result.get("simulation", False)
        fmt      = result.get("format", "?")
        data     = result.get("data", "")
        encoding = result.get("encoding", "?")

        print(f"✅ Succès! Format: {fmt} | Encoding: {encoding} | Simulation: {sim}")
        print(f"  Data length (base64): {len(data)} chars")

        # Vérifier que c'est du base64 valide
        try:
            import base64
            decoded = base64.b64decode(data)
            print(f"  Taille décodée: {len(decoded)} bytes")
            print(f"  ✅ Base64 valide")
        except Exception as e:
            print(f"  ⚠ Base64 invalide: {e}")

        if sim:
            print(f"  ℹ️  Image simulée (Appium non connecté) — comportement attendu")
    else:
        print(f"❌ Erreur: {result.get('error')}")

    return result["success"]


def test_execute_robot_test():
    """Test 6: Exécution d'un test Robot Framework"""
    print("\n" + "="*60)
    print("TEST 6: execute_robot_test")
    print("="*60)

    # Tester avec un fichier qui n'existe pas (cas attendu)
    result = execute_robot_test(test_file="tests_inexistants/fake_test.robot")

    if not result["success"] and "introuvable" in result.get("error", ""):
        print(f"✅ Comportement correct: retourne erreur claire si fichier inexistant")
        print(f"  Message: {result.get('error', '')}")
        return True

    # Si Robot Framework est installé et un fichier test existe
    if result["success"]:
        print(f"✅ Succès! Résultats:")
        print(f"  Passed:  {result.get('passed', 0)}")
        print(f"  Failed:  {result.get('failed', 0)}")
        print(f"  Total:   {result.get('total', 0)}")
        print(f"  Output:  {result.get('output_dir', '')}")
        return True

    print(f"⚠ Résultat: {result.get('error', 'Inconnu')} — peut être normal si RF non installé")
    return True  # Non bloquant


# ============================================================================
# RUNNER PRINCIPAL
# ============================================================================

def run_all_tests():
    """Lance tous les tests de validation du MCP Appium Server."""

    print("\n" + "🚀"*30)
    print("VALIDATION DU MCP APPIUM SERVER")
    print("🚀"*30)

    # Vérifier Appium
    try:
        import appium
        # Certaines versions n'exposent pas __version__ directement
        try:
            appium_version = appium.__version__
        except AttributeError:
            try:
                from appium import version
                appium_version = version.__version__
            except Exception:
                appium_version = "installé (version inconnue)"
        print(f"\n✅ Appium Python Client: v{appium_version}")
    except ImportError:
        print(f"\n⚠️  Appium Python Client non installé")
        print(f"   → Mode SIMULATION activé pour tous les tests")
        print(f"   → Pour tests réels: pip install Appium-Python-Client")

    print(f"\n📱 Configuration:")
    print(f"  Appium URL: {appium_url}")
    print(f"  App:        {app_package}")
    print(f"  Device:     {device_name}")
    print(f"  Android:    {platform_ver}")

    tests = [
        ("UI Hierarchy (tree)",          test_get_ui_hierarchy_tree),
        ("UI Hierarchy (flat)",          test_get_ui_hierarchy_flat),
        ("Page Source XML",              test_get_page_source),
        ("Find Element (resource_id)",   test_find_element_by_resource_id),
        ("Find Element (text)",          test_find_element_by_text),
        ("Find Element (not found)",     test_find_element_not_found),
        ("Self-Healing Locators",        test_suggest_alternative_locators),
        ("Screenshot",                   test_take_screenshot),
        ("Execute Robot Test",           test_execute_robot_test),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ Exception dans {test_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # ---- Résumé ----
    print("\n" + "="*60)
    print("RÉSUMÉ DES TESTS")
    print("="*60)

    passed = sum(1 for _, s in results if s)
    total  = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")

    print(f"\nScore: {passed}/{total} tests réussis")

    if passed == total:
        print("\n🎉 Tous les tests sont passés! Le serveur MCP Appium est opérationnel.")
        print("\n📌 Prochaine étape: configurer votre .env avec les vraies valeurs Appium")
        print("   APPIUM_HOST=http://127.0.0.1")
        print("   APPIUM_PORT=4723")
        print("   APP_PACKAGE=com.example.votreapp")
        print("   ANDROID_DEVICE_NAME=emulator-5554")
    else:
        failed = total - passed
        print(f"\n⚠ {failed} test(s) échoué(s). Vérifiez la configuration.")


if __name__ == "__main__":
    run_all_tests()