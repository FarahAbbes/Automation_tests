"""
Script de test pour valider le MCP GitLab Server
Lance des tests unitaires sur chaque outil MCP
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Trouver les chemins
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent

print(f"🔍 Recherche du dossier mcp_servers...")
print(f"📁 Répertoire du projet: {project_root}")

# Lister TOUS les dossiers pour debug
print(f"\n📂 Tous les dossiers trouvés:")
all_dirs = []
for item in project_root.iterdir():
    if item.is_dir() and not item.name.startswith('.'):
        all_dirs.append(item)
        print(f"  • '{item.name}' → {item}")

# Chercher le dossier qui contient mcp_gitlab_server.py
mcp_servers_dir = None
for dir_path in all_dirs:
    # Vérifier si le nom contient "mcp" (insensible à la casse et aux espaces)
    if "mcp" in dir_path.name.lower():
        # Vérifier si le fichier mcp_gitlab_server.py existe dedans
        potential_file = dir_path / "mcp_gitlab_server.py"
        if potential_file.exists():
            mcp_servers_dir = dir_path
            print(f"\n✅ Dossier MCP trouvé: {dir_path}")
            print(f"✅ Fichier trouvé: {potential_file}")
            break

if mcp_servers_dir is None:
    print("\n❌ ERREUR: Impossible de trouver mcp_gitlab_server.py!")
    sys.exit(1)

# ============================================================================
# CHARGER LES VARIABLES D'ENVIRONNEMENT (avec gestion des espaces)
# ============================================================================

print(f"\n🔧 Chargement des variables d'environnement...")

# Chercher le dossier config (qui peut avoir un espace)
config_dir = None
for item in project_root.iterdir():
    if item.is_dir() and "config" in item.name.lower():
        config_dir = item
        print(f"✅ Dossier config trouvé: {config_dir}")
        break

if config_dir:
    env_path = config_dir / ".env"
    if env_path.exists():
        print(f"✅ Fichier .env trouvé: {env_path}")
        load_dotenv(env_path)
        print(f"✅ Variables chargées depuis: {env_path}")
    else:
        print(f"⚠ Fichier .env introuvable dans {config_dir}")
        # Essayer aussi à la racine
        env_root = project_root / ".env"
        if env_root.exists():
            load_dotenv(env_root)
            print(f"✅ Variables chargées depuis la racine: {env_root}")
else:
    print("⚠ Dossier config introuvable, tentative depuis la racine...")
    load_dotenv()

# Afficher les variables chargées (sans le token complet)
gitlab_url = os.getenv("GITLAB_URL")
gitlab_token = os.getenv("GITLAB_TOKEN")
project_id = os.getenv("GITLAB_PROJECT_ID")

print(f"\n📊 Variables d'environnement:")
print(f"  • GITLAB_URL: {gitlab_url if gitlab_url else '❌ NON DÉFINIE'}")
print(f"  • GITLAB_TOKEN: {'✅ Défini (' + gitlab_token[:15] + '...)' if gitlab_token else '❌ NON DÉFINI'}")
print(f"  • GITLAB_PROJECT_ID: {project_id if project_id else '❌ NON DÉFINI'}")

# ============================================================================
# IMPORT DU MODULE
# ============================================================================

def import_mcp_gitlab_server():
    """Import robuste avec toutes les méthodes possibles"""
    mcp_file = mcp_servers_dir / "mcp_gitlab_server.py"

    # Méthode 1: importlib (la plus fiable)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("mcp_gitlab_server", str(mcp_file))
        if spec is None:
            raise ImportError("spec_from_file_location a retourné None")
        module = importlib.util.module_from_spec(spec)
        sys.modules["mcp_gitlab_server"] = module
        spec.loader.exec_module(module)
        print("\n✅ Import réussi (importlib)")
        return module
    except Exception as e:
        print(f"⚠ Méthode importlib échouée: {e}")

    # Méthode 2: sys.path
    try:
        sys.path.insert(0, str(mcp_servers_dir))
        import mcp_gitlab_server
        print("\n✅ Import réussi (sys.path)")
        return mcp_gitlab_server
    except ImportError as e:
        print(f"⚠ Méthode sys.path échouée: {e}")

    # Méthode 3: exec
    try:
        import types
        module = types.ModuleType("mcp_gitlab_server")
        with open(mcp_file, 'r', encoding='utf-8') as f:
            code = compile(f.read(), str(mcp_file), 'exec')
        exec(code, module.__dict__)
        print("\n✅ Import réussi (exec)")
        return module
    except Exception as e:
        print(f"⚠ Méthode exec échouée: {e}")

    print(f"\n❌ TOUTES LES MÉTHODES ONT ÉCHOUÉ!")
    sys.exit(1)

# Importer le module
print(f"\n📦 Import du module mcp_gitlab_server...")
try:
    mcp_gitlab_server = import_mcp_gitlab_server()

    # Extraire les fonctions
    get_merge_requests = mcp_gitlab_server.get_merge_requests
    get_mr_changes = mcp_gitlab_server.get_mr_changes
    get_file_content = mcp_gitlab_server.get_file_content
    analyze_mr_for_ui_changes = mcp_gitlab_server.analyze_mr_for_ui_changes
    get_test_files = mcp_gitlab_server.get_test_files
    search_locator_in_tests = mcp_gitlab_server.search_locator_in_tests

    print("✅ Toutes les fonctions chargées!")

except Exception as e:
    print(f"❌ Erreur critique: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# FONCTIONS DE TEST
# ============================================================================

def test_get_merge_requests():
    """Test 1: Récupération des Merge Requests"""
    print("\n" + "="*60)
    print("TEST 1: get_merge_requests")
    print("="*60)

    result = get_merge_requests(state="opened", max_results=5)

    if result["success"]:
        print(f"✅ Succès! {result['count']} MRs trouvées")
        for mr in result["merge_requests"][:3]:
            print(f"  • MR #{mr['id']}: {mr['title']}")
            print(f"    Branch: {mr['source_branch']} → {mr['target_branch']}")
    else:
        print(f"❌ Erreur: {result['error']}")

    return result["success"]


def test_get_mr_changes(mr_id: int = None):
    """Test 2: Récupération des changements d'une MR"""
    print("\n" + "="*60)
    print("TEST 2: get_mr_changes")
    print("="*60)

    if mr_id is None:
        mrs = get_merge_requests(state="opened", max_results=1)
        if mrs["success"] and mrs["count"] > 0:
            mr_id = mrs["merge_requests"][0]["id"]
        else:
            print("❌ Aucune MR disponible pour le test")
            return False

    result = get_mr_changes(mr_iid=mr_id)

    if result["success"]:
        print(f"✅ Succès! MR #{mr_id}: {result['mr_title']}")
        print(f"  {result['files_count']} fichiers modifiés")
        for change in result["changes"][:3]:
            print(f"  • {change['new_path']}")
    else:
        print(f"❌ Erreur: {result['error']}")

    return result["success"]


def test_get_file_content():
    """Test 3: Lecture d'un fichier"""
    print("\n" + "="*60)
    print("TEST 3: get_file_content")
    print("="*60)

    test_files = ["README.md", "readme.md", ".gitlab-ci.yml"]

    for file_path in test_files:
        result = get_file_content(file_path=file_path)
        if result["success"]:
            print(f"✅ Succès! Fichier: {file_path}")
            print(f"  Taille: {result['size']} bytes")
            print(f"  Aperçu: {result['content'][:100]}...")
            return True

    print("❌ Aucun fichier de test trouvé")
    return False


def test_analyze_mr_for_ui_changes(mr_id: int = None):
    """Test 4: Analyse des changements UI dans une MR"""
    print("\n" + "="*60)
    print("TEST 4: analyze_mr_for_ui_changes")
    print("="*60)

    if mr_id is None:
        mrs = get_merge_requests(state="opened", max_results=1)
        if mrs["success"] and mrs["count"] > 0:
            mr_id = mrs["merge_requests"][0]["id"]
        else:
            print("❌ Aucune MR disponible pour le test")
            return False

    result = analyze_mr_for_ui_changes(mr_iid=mr_id)

    if result["success"]:
        print(f"✅ Succès! MR #{mr_id}: {result['mr_title']}")
        print(f"  Changements UI détectés: {result['has_ui_changes']}")

        if result['has_ui_changes']:
            ui = result['ui_changes']
            print(f"  • {len(ui['xml_files_modified'])} fichiers XML modifiés")
            print(f"  • {len(ui['new_ui_elements'])} nouveaux éléments UI")
            print(f"  • {len(ui['modified_ui_elements'])} éléments UI modifiés")
            print(f"\n  Recommandation:")
            print(f"  {result['recommendation']}")
        else:
            print("  Aucun changement UI détecté dans cette MR")
    else:
        print(f"❌ Erreur: {result['error']}")

    return result["success"]


def test_get_test_files():
    """Test 5: Liste des fichiers de test"""
    print("\n" + "="*60)
    print("TEST 5: get_test_files")
    print("="*60)

    test_paths = ["tests", "test", "Tests", "robot", "automation"]

    for path in test_paths:
        result = get_test_files(directory=path)
        if result["success"] and result["count"] > 0:
            print(f"✅ Succès! Répertoire: {path}")
            print(f"  {result['count']} fichiers .robot trouvés")
            for test_file in result["test_files"][:5]:
                print(f"  • {test_file['name']}")
            return True

    print("⚠ Aucun fichier de test trouvé (normal si pas encore de tests)")
    return True


def test_search_locator_in_tests():
    """Test 6: Recherche de locator dans les tests"""
    print("\n" + "="*60)
    print("TEST 6: search_locator_in_tests")
    print("="*60)

    test_locators = ["btn_login", "edit_username", "text_title", "button"]

    for locator in test_locators:
        result = search_locator_in_tests(locator_id=locator)
        if result["success"] and result["affected_tests_count"] > 0:
            print(f"✅ Succès! Locator: {locator}")
            print(f"  Trouvé dans {result['affected_tests_count']} fichiers de test")
            return True

    print("⚠ Aucun locator trouvé (normal si pas encore de tests)")
    return True


def run_all_tests():
    """Lance tous les tests de validation"""
    print("\n" + "🚀"*30)
    print("VALIDATION DU MCP GITLAB SERVER")
    print("🚀"*30)

    # Vérifier les variables d'environnement
    required_vars = ["GITLAB_URL", "GITLAB_TOKEN", "GITLAB_PROJECT_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("\n❌ Variables d'environnement manquantes:")
        for var in missing_vars:
            print(f"  • {var}")
        print("\n💡 Le fichier .env existe mais les variables ne sont pas chargées!")
        print("💡 Vérifiez le contenu du fichier .env:")

        # Afficher le contenu du .env si possible
        if config_dir:
            env_file = config_dir / ".env"
            if env_file.exists():
                print(f"\n📄 Contenu de {env_file}:")
                with open(env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines[:10], 1):
                        # Masquer les tokens
                        if "TOKEN" in line and "=" in line:
                            parts = line.split("=", 1)
                            print(f"  {i}. {parts[0]}=***masqué***")
                        else:
                            print(f"  {i}. {line.rstrip()}")
        return

    print(f"\n✅ Configuration OK")
    print(f"  URL: {os.getenv('GITLAB_URL')}")
    print(f"  Projet: {os.getenv('GITLAB_PROJECT_ID')}")

    # Exécuter les tests
    tests = [
        ("Merge Requests", test_get_merge_requests),
        ("MR Changes", lambda: test_get_mr_changes()),
        ("File Content", test_get_file_content),
        ("UI Changes Analysis", lambda: test_analyze_mr_for_ui_changes()),
        ("Test Files", test_get_test_files),
        ("Locator Search", test_search_locator_in_tests)
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

    # Résumé
    print("\n" + "="*60)
    print("RÉSUMÉ DES TESTS")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")

    print(f"\nScore: {passed}/{total} tests réussis")

    if passed == total:
        print("\n🎉 Tous les tests sont passés! Le serveur MCP est opérationnel.")
    else:
        print(f"\n⚠ {total - passed} test(s) échoué(s). Vérifiez la configuration.")


if __name__ == "__main__":
    run_all_tests()