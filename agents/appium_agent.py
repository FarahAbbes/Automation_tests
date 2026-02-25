"""
Appium Agent — MyBiat Test Automation
======================================
Agent IA qui pilote le MCP Appium Server et raisonne avec Gemini.

Workflows disponibles:
  --workflow analyze       → Analyse l'écran courant + génère les tests RF (POM)
  --workflow self-healing  → Répare automatiquement un locator cassé
  --workflow validate      → Ré-exécute un test Robot Framework après correction
  --diagnose               → Diagnostic complet du serveur MCP

Usage:
  python appium_agent.py --workflow analyze
  python appium_agent.py --workflow self-healing --locator btn_login_old
  python appium_agent.py --workflow validate --test-file tests/suites/login/test_login.robot
  python appium_agent.py --diagnose
"""

import os
import re
import sys
import json
import base64
import asyncio
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================================================
# CHARGEMENT .ENV
# ============================================================================
try:
    from dotenv import load_dotenv

    _candidates = [
        Path(__file__).parent / "config" / ".env",
        Path(__file__).parent.parent / "config" / ".env",
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
        Path.cwd() / "config" / ".env",
        Path.cwd() / ".env",
    ]
    for _p in _candidates:
        if _p.exists():
            load_dotenv(_p, override=True)
            print(f"✅ .env chargé : {_p}")
            break
    else:
        load_dotenv()
        print("⚠️  Aucun .env trouvé — variables système utilisées")
except ImportError:
    print("⚠️  python-dotenv absent (pip install python-dotenv)")

# ============================================================================
# IMPORTS MCP CLIENT
# ============================================================================
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("❌ mcp non installé : pip install mcp")

# ============================================================================
# IMPORTS GEMINI  (new SDK prioritaire, old SDK en fallback)
# ============================================================================
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_OK  = True
    GEMINI_SDK = "new"
except ImportError:
    try:
        import google.generativeai as genai_old
        GEMINI_OK  = True
        GEMINI_SDK = "old"
    except ImportError:
        GEMINI_OK  = False
        GEMINI_SDK = None
        print("❌ Gemini non installé : pip install google-genai")

# ============================================================================
# CONFIGURATION
# ============================================================================
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
APP_PACKAGE     = os.getenv("APP_PACKAGE", "com.example.mybiat")
TESTS_DIR       = os.getenv("TESTS_DIR", "tests")
RESULTS_DIR     = os.getenv("RESULTS_DIR", "agent_results")
TESTS_SUITES_DIR = os.getenv("TESTS_SUITES_DIR", "tests/suites")

# ── Résolution du chemin du serveur MCP ───────────────────────────────────
def _resolve_mcp_server_path() -> str:
    """
    Résout le chemin du MCP server avec plusieurs stratégies de fallback.
    Priorité : variable ENV → relatif au script → relatif au CWD → recherche récursive.
    """
    filename    = "mcp_appium_server.py"
    script_dir  = Path(__file__).resolve().parent
    project_root = script_dir.parent

    candidates = []

    env_val = os.getenv("MCP_APPIUM_SERVER_PATH", "")
    if env_val:
        candidates.append(("ENV", Path(env_val)))

    candidates += [
        ("mcp_servers/",    project_root / "mcp_servers" / filename),
        ("script dir",      script_dir / filename),
        ("project root",    project_root / filename),
        ("CWD mcp_servers", Path.cwd() / "mcp_servers" / filename),
        ("CWD",             Path.cwd() / filename),
    ]

    for label, path in candidates:
        try:
            resolved = path.resolve()
            if resolved.exists():
                print(f"   ✅ MCP server [{label}] : {resolved}")
                return str(resolved)
        except Exception:
            pass

    # Recherche récursive en dernier recours
    for search_root in [project_root, Path.cwd()]:
        for found in sorted(search_root.rglob(filename))[:3]:
            print(f"   ✅ MCP server (récursif) : {found}")
            return str(found)

    fallback = str(project_root / "mcp_servers" / filename)
    print(f"   ❌ {filename} introuvable — chemin attendu : {fallback}")
    return fallback


MCP_SERVER_PATH = _resolve_mcp_server_path()

print("\n📋 APPIUM AGENT — CONFIG:")
print(f"   GEMINI_MODEL   : {GEMINI_MODEL}")
print(f"   GEMINI_API_KEY : {'✅ défini' if GEMINI_API_KEY else '❌ MANQUANT'}")
print(f"   MCP SERVER     : {MCP_SERVER_PATH}")
print(f"   MCP SERVER     : {'✅ trouvé' if Path(MCP_SERVER_PATH).exists() else '❌ INTROUVABLE'}")
print(f"   MCP CLIENT     : {'✅' if MCP_AVAILABLE else '❌ non installé'}")
print(f"   Python         : {sys.version.split()[0]}\n")


# ============================================================================
# HELPERS
# ============================================================================

def _extract_exception_message(exc: Exception) -> str:
    """Extrait un message lisible depuis une Exception ou ExceptionGroup (Python 3.11+)."""
    if hasattr(exc, "exceptions"):
        return " | ".join(_extract_exception_message(sub) for sub in exc.exceptions)
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause and str(cause) != str(exc):
        return f"{type(exc).__name__}: {exc} → caused by: {type(cause).__name__}: {cause}"
    return f"{type(exc).__name__}: {exc}"


# ============================================================================
# CLASSE PRINCIPALE — APPIUM AGENT
# ============================================================================

class AppiumAgent:
    """
    Agent IA qui orchestre le MCP Appium Server et raisonne avec Gemini.
    Implémente les trois workflows : analyze_screen, self_healing, validate_test.
    """

    # ──────────────────────────────────────────────────────────────────────
    # APPEL MCP
    # ──────────────────────────────────────────────────────────────────────

    async def _call_mcp_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """
        Appelle un outil exposé par le MCP Appium Server.
        Fallback automatique vers la simulation si le serveur est indisponible.

        Protections intégrées :
          • Timeout 30s (asyncio.timeout)
          • Gestion ExceptionGroup (Python 3.11+)
          • Utilisation du même interpréteur Python (respect du venv)
        """
        if not MCP_AVAILABLE:
            print(f"⚠️  MCP non disponible — simulation de {tool_name}")
            return self._simulate_mcp_call(tool_name, arguments or {})

        if not Path(MCP_SERVER_PATH).exists():
            print(f"❌ MCP server introuvable : {MCP_SERVER_PATH} → simulation")
            return self._simulate_mcp_call(tool_name, arguments or {})

        server_params = StdioServerParameters(
            command=sys.executable,  # même interpréteur → venv respecté
            args=[MCP_SERVER_PATH],
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )

        try:
            async with asyncio.timeout(30):
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments=arguments or {})

                        if result.content:
                            for content in result.content:
                                if hasattr(content, "text"):
                                    try:
                                        return json.loads(content.text)
                                    except json.JSONDecodeError:
                                        return {"success": True, "raw": content.text}
                        return {"success": False, "error": "Réponse MCP vide"}

        except TimeoutError:
            print(f"⏰ Timeout MCP ({tool_name}) → simulation")
            return self._simulate_mcp_call(tool_name, arguments or {})

        except Exception as exc:
            msg = _extract_exception_message(exc)
            print(f"❌ Erreur MCP {tool_name}: {msg}")
            if "connection closed" in msg.lower():
                print("   ⚠️  Serveur MCP crashé au démarrage — lancez --diagnose")
            print("   → Mode simulation activé")
            return self._simulate_mcp_call(tool_name, arguments or {})

    async def _diagnose_server(self) -> None:
        """Diagnostic complet du serveur MCP (crash, imports manquants, etc.)."""
        print("\n" + "=" * 60)
        print("  🔧 DIAGNOSTIC MCP SERVER")
        print("=" * 60)

        p = Path(MCP_SERVER_PATH)
        print(f"\n[1] Path    : {MCP_SERVER_PATH}")
        print(f"    Exists  : {'✅' if p.exists() else '❌'}")

        # Vérification syntaxe
        print("\n[2] Syntax check ...")
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", MCP_SERVER_PATH],
            capture_output=True, text=True, timeout=10,
        )
        print(f"    {'✅ OK' if r.returncode == 0 else f'❌ ERREUR: {r.stderr}'}")

        # Vérification imports
        print("\n[3] Import check ...")
        for pkg in ["mcp", "mcp.server.fastmcp", "appium", "selenium"]:
            ri = subprocess.run(
                [sys.executable, "-c", f"import {pkg}; print('OK')"],
                capture_output=True, text=True, timeout=8,
            )
            status = "✅" if ri.stdout.strip() == "OK" else f"❌ {ri.stderr.strip()[:80]}"
            print(f"    {status}  {pkg}")

        # Test de démarrage
        print("\n[4] Startup test (3s) ...")
        try:
            proc = subprocess.Popen(
                [sys.executable, MCP_SERVER_PATH],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            import time; time.sleep(3)
            ret = proc.poll()
            if ret is None:
                print("    ✅ Serveur vivant après 3s")
                proc.terminate()
            else:
                stderr = proc.stderr.read().decode("utf-8", errors="replace")
                print(f"    ❌ Exited (code {ret})")
                if stderr:
                    print(f"    STDERR:\n{stderr[:1000]}")
                missing = re.findall(r"No module named '([^']+)'", stderr)
                if missing:
                    print(f"    💡 Modules manquants : pip install {' '.join(missing)}")
        except Exception as e:
            print(f"    ❌ {e}")

        print("\n" + "=" * 60)

    def _simulate_mcp_call(self, tool_name: str, arguments: dict) -> dict:
        """Simulation locale des outils MCP (sans connexion réelle au serveur)."""
        print(f"   [SIM] {tool_name}({list(arguments.keys())})")

        if tool_name == "analyze_current_screen":
            return {
                "success": True, "simulation": True,
                "page_name": "login", "app_package": APP_PACKAGE,
                "total_elements": 6, "interactive_elements": 5,
                "interactive_summary": [
                    {
                        "type": "username_field", "short_id": "edit_username",
                        "resource_id": f"{APP_PACKAGE}:id/edit_username",
                        "text": "", "content_desc": "Champ identifiant",
                        "enabled": True, "locator_quality": "robust",
                        "locators": {
                            "by_id": f"id={APP_PACKAGE}:id/edit_username",
                            "by_accessibility": "accessibility id=Champ identifiant",
                        },
                    },
                    {
                        "type": "password_field", "short_id": "edit_password",
                        "resource_id": f"{APP_PACKAGE}:id/edit_password",
                        "text": "", "content_desc": "Champ mot de passe",
                        "enabled": True, "locator_quality": "robust",
                        "locators": {
                            "by_id": f"id={APP_PACKAGE}:id/edit_password",
                            "by_accessibility": "accessibility id=Champ mot de passe",
                        },
                    },
                    {
                        "type": "login_button", "short_id": "btn_login",
                        "resource_id": f"{APP_PACKAGE}:id/btn_login",
                        "text": "Se connecter", "content_desc": "",
                        "enabled": True, "locator_quality": "robust",
                        "locators": {
                            "by_id":   f"id={APP_PACKAGE}:id/btn_login",
                            "by_text": "xpath=//*[@text='Se connecter']",
                        },
                    },
                    {
                        "type": "checkbox", "short_id": "cb_remember_me",
                        "resource_id": f"{APP_PACKAGE}:id/cb_remember_me",
                        "text": "Se souvenir de moi", "content_desc": "",
                        "enabled": True, "locator_quality": "robust",
                        "locators": {
                            "by_id":   f"id={APP_PACKAGE}:id/cb_remember_me",
                            "by_text": "xpath=//*[@text='Se souvenir de moi']",
                        },
                    },
                    {
                        "type": "forgot_password_link", "short_id": "tv_forgot_password",
                        "resource_id": f"{APP_PACKAGE}:id/tv_forgot_password",
                        "text": "Mot de passe oublié ?", "content_desc": "",
                        "enabled": True, "locator_quality": "robust",
                        "locators": {
                            "by_id":   f"id={APP_PACKAGE}:id/tv_forgot_password",
                            "by_text": "xpath=//*[@text='Mot de passe oublié ?']",
                        },
                    },
                ],
                "locator_stats": {"robust": 5, "fragile": 0, "missing": 1, "coverage_percent": 83.3},
                "fragile_locators": [],
                "missing_locators": [],
            }

        if tool_name == "suggest_alternative_locators":
            broken = arguments.get("broken_locator_id", "unknown")
            return {
                "success": True, "simulation": True,
                "broken_locator": broken, "alternatives_count": 1,
                "alternatives": [{
                    "resource_id": f"{APP_PACKAGE}:id/btn_login",
                    "text": "Se connecter", "confidence_score": 0.75,
                    "suggested_locators": [f"id:{APP_PACKAGE}:id/btn_login"],
                }],
                "recommendation": f"Remplacer '{broken}' par 'id:btn_login' (confiance : 75%)",
            }

        if tool_name == "execute_robot_test":
            return {"success": True, "total": 3, "passed": 2, "failed": 1,
                    "all_passed": False, "simulation": True}

        return {"success": False, "error": f"Outil {tool_name} non simulé"}

    # ──────────────────────────────────────────────────────────────────────
    # APPEL GEMINI
    # ──────────────────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str, screenshot_b64: Optional[str] = None) -> str:
        """Envoie le prompt à Gemini et retourne la réponse texte."""
        if not GEMINI_OK:
            return "❌ Gemini non installé (pip install google-genai)"
        if not GEMINI_API_KEY:
            return "❌ GEMINI_API_KEY manquant dans le .env"

        print(f"\n🤖 Gemini ({GEMINI_MODEL}) [SDK: {GEMINI_SDK}]...")
        try:
            if GEMINI_SDK == "new":
                client = genai.Client(api_key=GEMINI_API_KEY)
                parts  = [prompt]
                if screenshot_b64:
                    img_bytes = base64.b64decode(screenshot_b64)
                    parts.append(
                        genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                    )
                    print("   📸 Screenshot joint au prompt")
                response = client.models.generate_content(model=GEMINI_MODEL, contents=parts)
                return response.text

            else:  # old SDK
                genai_old.configure(api_key=GEMINI_API_KEY)
                model   = genai_old.GenerativeModel(GEMINI_MODEL)
                content = [prompt]
                if screenshot_b64:
                    content.append({"mime_type": "image/png",
                                    "data": base64.b64decode(screenshot_b64)})
                return model.generate_content(content).text

        except Exception as e:
            return f"❌ Erreur Gemini : {e}"

    # ──────────────────────────────────────────────────────────────────────
    # CONSTRUCTION DES PROMPTS
    # ──────────────────────────────────────────────────────────────────────

    def _build_analyze_prompt(self, screen_data: dict) -> str:
        page    = screen_data.get("page_name", "unknown")
        summary = screen_data.get("interactive_summary", [])
        stats   = screen_data.get("locator_stats", {})
        fragile = screen_data.get("fragile_locators", [])
        sim     = screen_data.get("simulation", False)

        # Valeurs réelles du .env injectées dans le prompt
        # Gemini ne peut plus inventer de valeurs incorrectes
        device_name      = os.getenv("DEVICE_NAME", "emulator-5554")
        platform_version = os.getenv("PLATFORM_VERSION",
                           os.getenv("ANDROID_PLATFORM_VERSION", "12"))
        appium_url       = (os.getenv("APPIUM_SERVER_URL", "")
                           or f"{os.getenv('APPIUM_HOST','http://127.0.0.1')}:{os.getenv('APPIUM_PORT','4723')}")
        app_activity     = os.getenv("APP_ACTIVITY", ".MainActivity")

        summary_json = json.dumps(summary, indent=2, ensure_ascii=False)
        fragile_json = json.dumps(fragile, indent=2, ensure_ascii=False) if fragile else "[]"

        fragile_section = ""
        if fragile:
            fragile_section = f"""
## ⚠️ LOCATORS FRAGILES (à corriger en priorité)
```json
{fragile_json}
```"""

        return f"""Tu es un expert en automatisation de tests mobiles (Robot Framework + Appium).
Tu analyses la page actuelle d'une application mobile Android.

## CONTEXTE
- Page détectée        : **{page.upper()}**
- Application          : {APP_PACKAGE}
- Timestamp            : {datetime.now().isoformat()}
- Mode                 : {"⚠️ SIMULATION" if sim else "✅ Device réel"}
- Éléments interactifs : {len(summary)}
- Couverture locators  : {stats.get("coverage_percent", 0)}%
  (robust: {stats.get("robust", 0)} | fragile: {stats.get("fragile", 0)} | missing: {stats.get("missing", 0)})

## ÉLÉMENTS UI DÉTECTÉS (avec locators Appium)
```json
{summary_json}
```
{fragile_section}

## TES MISSIONS

### 1. CONFIRMATION DE LA PAGE
Confirme ou corrige l'identification de la page (actuelle : {page}).
Décris en 2 phrases ce que l'utilisateur peut faire sur cet écran.

### 2. GÉNÉRATION PAGE OBJECT (POM)
Génère le fichier `{page}_page.robot` avec :
- Section `*** Variables ***` : tous les locators de la page
- Section `*** Keywords ***` : au moins 5 keywords réutilisables

### 3. GÉNÉRATION TEST CASES
Génère `test_{page}.robot` avec au moins 3 scénarios :
- ✅ Cas nominal (happy path avec données valides)
- ❌ Cas d'erreur (données invalides / élément absent)
- ⚠️ Cas limite (champ vide, whitespace, recherche partielle)

### 4. RECOMMANDATIONS SELF-HEALING
Pour chaque locator fragile ou manquant, propose un locator alternatif robuste.

---
## ⚠️ RÈGLES CRITIQUES — FORMAT DES LOCATORS

### RÈGLE 1 — Format exact dans *** Variables ***
Les locators dans la section Variables utilisent ces formats EXACTS selon le type :

```
# resource-id disponible → format id=
${{LOC_BTN_LOGIN}}    id=com.example.app:id/btn_login

# accessibility id disponible → format accessibility id=
${{LOC_CAT_ALL}}      accessibility id=All

# xpath seulement → format xpath=
${{LOC_SEARCH}}       xpath=//android.widget.EditText
```

### RÈGLE 2 — Utilisation dans Keywords (CRITIQUE)
Quand la variable contient déjà le préfixe (`id=`, `accessibility id=`, `xpath=`),
AppiumLibrary la reconnaît automatiquement. Utilise directement la variable :

```robot
# ✅ CORRECT — la variable contient déjà le préfixe complet
Click Element    ${{LOC_CAT_ALL}}
Input Text       ${{LOC_SEARCH}}    texte à saisir
Wait Until Page Contains Element    ${{LOC_BTN_LOGIN}}    timeout=10s

# ❌ INTERDIT — ne jamais reconstruire le locator dynamiquement
${{locator}}=    Set Variable    accessibility id=${{category_name}}
Click Element    ${{locator}}
```

### RÈGLE 3 — Variables sans commentaires inline
```robot
# ✅ CORRECT
${{APP_PACKAGE}}      {APP_PACKAGE}

# ❌ INTERDIT — le commentaire fait partie de la valeur en Robot Framework
${{APP_PACKAGE}}      {APP_PACKAGE}    # ceci casse la variable
```

### RÈGLE 4 — Ne jamais inventer de variables inexistantes
Utilise UNIQUEMENT les noms de variables définis dans `*** Variables ***`.
Ne jamais référencer une variable non déclarée.

---
## FORMAT OBLIGATOIRE DES DEUX FICHIERS

**Fichier 1 — Page Object** : `{page}_page.robot`
```robot
*** Settings ***
Library           AppiumLibrary

*** Variables ***
# Format : ${{NOM_VARIABLE}}    prefix=valeur
# prefix = id= ou accessibility id= ou xpath=
${{LOC_EXAMPLE_ID}}           id={APP_PACKAGE}:id/element_id
${{LOC_EXAMPLE_A11Y}}         accessibility id=Some Label
${{LOC_EXAMPLE_XPATH}}        xpath=//android.widget.EditText

*** Keywords ***
Open {page} Page
    [Documentation]    Vérifie que la page {page} est affichée.
    Wait Until Page Contains Element    ${{LOC_EXAMPLE_ID}}    timeout=10s

Click Some Element
    [Documentation]    Exemple de click avec variable de locator.
    Click Element    ${{LOC_EXAMPLE_A11Y}}

Type In Search Field
    [Arguments]    ${{text}}
    [Documentation]    Saisit du texte dans un champ.
    Input Text    ${{LOC_EXAMPLE_XPATH}}    ${{text}}
```

**Fichier 2 — Test Cases** : `test_{page}.robot`
```robot
*** Settings ***
Library           AppiumLibrary
Resource          {page}_page.robot
Test Setup        Open Application For Tests
Test Teardown     Close Application

*** Variables ***
${{APPIUM_URL}}         {appium_url}
${{DEVICE_NAME}}        {device_name}
${{APP_PACKAGE}}        {APP_PACKAGE}
${{APP_ACTIVITY}}       {app_activity}
${{PLATFORM_VERSION}}   {platform_version}

*** Test Cases ***
TC-{page.upper()}-01 Happy Path Description
    [Documentation]    Description du scénario nominal.
    [Tags]             {page}    smoke    happy_path
    Open {page} Page
    # steps utilisant les keywords du POM
    # Click Some Element
    # Type In Search Field    ma recherche

TC-{page.upper()}-02 Error Case Description
    [Documentation]    Description du scénario d'erreur.
    [Tags]             {page}    error_case
    Open {page} Page
    # steps

TC-{page.upper()}-03 Edge Case Description
    [Documentation]    Description du cas limite.
    [Tags]             {page}    edge_case
    Open {page} Page
    # steps

*** Keywords ***
Open Application For Tests
    [Documentation]    Ouvre l'application mobile.
    Open Application    ${{APPIUM_URL}}
    ...    platformName=Android
    ...    platformVersion=${{PLATFORM_VERSION}}
    ...    deviceName=${{DEVICE_NAME}}
    ...    appPackage=${{APP_PACKAGE}}
    ...    appActivity=${{APP_ACTIVITY}}
    ...    automationName=UiAutomator2
    ...    noReset=true
    ...    autoGrantPermissions=true
```

RAPPELS FINAUX :
- DEUX blocs ```robot obligatoires (un par fichier)
- [Tags] obligatoire sur chaque Test Case
- Test Setup / Test Teardown dans Settings (pas dans chaque test)
- Aucun commentaire # après une valeur de variable
- Aucune variable inventée non déclarée dans *** Variables ***
"""

    def _build_self_healing_prompt(self, broken_locator: str,
                                    alternatives: list,
                                    test_context: Optional[str] = None) -> str:
        alts_json = json.dumps(alternatives, indent=2, ensure_ascii=False)
        context_line = f"\n**Contexte du test :** {test_context}" if test_context else ""

        return f"""Tu es un expert en self-healing de tests mobiles automatisés.
Un test Robot Framework a échoué car le locator suivant n'existe plus :

**Locator cassé :** `{broken_locator}`{context_line}

## ALTERNATIVES PROPOSÉES PAR L'ANALYSE UI
```json
{alts_json}
```

## TES MISSIONS

### 1. DIAGNOSTIC
Explique en 2 phrases pourquoi ce locator a probablement cassé.

### 2. CHOIX DU MEILLEUR LOCATOR
Sélectionne le locator de remplacement le plus robuste parmi les alternatives.

### 3. CODE CORRIGÉ
```robot
# AVANT (cassé)
${{OLD_LOCATOR}}    id=<ancien_id>

# APRÈS (corrigé)
${{NEW_LOCATOR}}    id=<nouvel_id>
```

### 4. IMPACT
Liste les autres tests potentiellement impactés par ce changement.
"""

    # ──────────────────────────────────────────────────────────────────────
    # WORKFLOWS
    # ──────────────────────────────────────────────────────────────────────

    async def workflow_analyze_screen(
        self,
        include_screenshot: bool = True,
        save_results: bool = True,
    ) -> dict:
        """WORKFLOW 1 — Analyse l'écran courant et génère les fichiers Robot Framework (POM)."""
        print("\n" + "=" * 60)
        print("  WORKFLOW : ANALYZE SCREEN")
        print("=" * 60)

        print("\n📱 Étape 1/4 — MCP: analyze_current_screen ...")
        screen_data = await self._call_mcp_tool(
            "analyze_current_screen", {"include_screenshot": include_screenshot}
        )
        if not screen_data.get("success"):
            return {"success": False, "error": screen_data.get("error"), "step": "mcp_call"}

        page = screen_data.get("page_name", "unknown")
        sim  = screen_data.get("simulation", False)
        stat = screen_data.get("locator_stats", {})
        print(f"   {'⚠️ SIMULATION' if sim else '✅'} Page : {page.upper()}")
        print(f"   📊 {screen_data.get('total_elements', 0)} éléments, "
              f"{screen_data.get('interactive_elements', 0)} interactifs")
        print(f"   🔒 Couverture locators : {stat.get('coverage_percent', 0)}%")

        print("\n📝 Étape 2/4 — Construction du prompt ...")
        prompt = self._build_analyze_prompt(screen_data)

        print("\n🤖 Étape 3/4 — Appel Gemini ...")
        screenshot_b64 = None
        if include_screenshot and screen_data.get("screenshot"):
            screenshot_b64 = screen_data["screenshot"].get("data")
        gemini_response = self._call_gemini(prompt, screenshot_b64)
        print("   ✅ Réponse reçue")

        robot_files = _extract_robot_blocks(gemini_response)
        saved_paths = []
        if save_results:
            print(f"\n💾 Étape 4/4 — Sauvegarde ({len(robot_files)} fichier(s)) ...")
            saved_paths = _save_agent_results(
                workflow="analyze", page=page,
                screen_data=screen_data, llm_response=gemini_response,
                robot_files=robot_files,
            )

        return {
            "success": True, "workflow": "analyze_screen",
            "page_name": page, "simulation": sim,
            "locator_stats": stat,
            "fragile_count": len(screen_data.get("fragile_locators", [])),
            "robot_files_generated": list(robot_files.keys()),
            "saved_to": saved_paths,
            "gemini_response": gemini_response,
        }

    async def workflow_self_healing(
        self,
        broken_locator_id: str,
        context_hint: Optional[str] = None,
        test_file: Optional[str] = None,
        auto_apply: bool = False,
    ) -> dict:
        """WORKFLOW 2 — Répare automatiquement un locator cassé."""
        print("\n" + "=" * 60)
        print("  WORKFLOW : SELF-HEALING")
        print("=" * 60)
        print(f"   Locator cassé : {broken_locator_id}")

        print("\n🔍 Étape 1/3 — MCP: suggest_alternative_locators ...")
        healing_data = await self._call_mcp_tool(
            "suggest_alternative_locators",
            {"broken_locator_id": broken_locator_id, "context_hint": context_hint or ""},
        )
        if not healing_data.get("success"):
            return {"success": False, "error": healing_data.get("error"), "step": "mcp_alternatives"}

        alternatives = healing_data.get("alternatives", [])
        print(f"   ✅ {len(alternatives)} alternative(s)")
        if not alternatives:
            return {"success": False, "error": "Aucune alternative trouvée",
                    "broken_locator": broken_locator_id}

        print("\n🤖 Étape 2/3 — Appel Gemini pour sélection ...")
        prompt = self._build_self_healing_prompt(
            broken_locator=broken_locator_id, alternatives=alternatives,
            test_context=f"Test file: {test_file}" if test_file else None,
        )
        gemini_response = self._call_gemini(prompt)
        print("   ✅ Réponse reçue")

        validation_result = None
        if test_file and auto_apply:
            print(f"\n🧪 Étape 3/3 — Validation : {test_file} ...")
            validation_result = await self._call_mcp_tool(
                "execute_robot_test", {"test_file": test_file}
            )
        else:
            print("\n⏭️  Étape 3/3 — Validation ignorée (auto_apply=False)")

        saved_paths = _save_agent_results(
            workflow="self_healing", page=f"locator_{broken_locator_id}",
            screen_data={"simulation": healing_data.get("simulation", False)},
            llm_response=gemini_response, robot_files={},
        )

        return {
            "success": True, "workflow": "self_healing",
            "broken_locator": broken_locator_id,
            "alternatives_found": len(alternatives),
            "mcp_recommendation": healing_data.get("recommendation"),
            "gemini_analysis": gemini_response,
            "validation": validation_result,
            "saved_to": saved_paths,
        }

    async def workflow_validate_test(
        self, test_file: str, test_tags: Optional[str] = None
    ) -> dict:
        """WORKFLOW 3 — Ré-exécute un test Robot Framework et retourne les résultats."""
        print("\n" + "=" * 60)
        print("  WORKFLOW : VALIDATE TEST")
        print("=" * 60)
        print(f"   Fichier : {test_file}")

        result = await self._call_mcp_tool(
            "execute_robot_test", {"test_file": test_file, "test_tags": test_tags or ""}
        )

        status = "✅ TOUS LES TESTS PASSENT" if result.get("all_passed") else "❌ ÉCHECS DÉTECTÉS"
        print(f"\n{status}")
        print(f"   Total: {result.get('total', 0)} | "
              f"Passés: {result.get('passed', 0)} | "
              f"Échoués: {result.get('failed', 0)}")

        return {
            "success":    result.get("success", False),
            "workflow":   "validate_test",
            "test_file":  test_file,
            "passed":     result.get("passed", 0),
            "failed":     result.get("failed", 0),
            "total":      result.get("total", 0),
            "all_passed": result.get("all_passed", False),
            "log_file":   result.get("log_file"),
            "error":      result.get("error"),
        }


# ============================================================================
# UTILITAIRES — EXTRACTION ET SAUVEGARDE
# ============================================================================

def _extract_robot_blocks(text: str) -> dict:
    """
    Extrait les blocs de code Robot Framework depuis la réponse Gemini.
    Gère : ```robot, ```robotframework, ```rf, blocs plain avec marqueurs *** .
    Infère le nom de fichier depuis les headers markdown environnants.
    """
    blocks = {}

    # Blocs avec tag de langage explicite
    fenced = re.findall(
        r"```[ \t]*(?:robot(?:framework)?|rf)[ \t]*\n(.*?)```",
        text, re.DOTALL | re.IGNORECASE,
    )
    # Blocs plain contenant des marqueurs Robot Framework
    plain       = re.findall(r"```[ \t]*\n(.*?)```", text, re.DOTALL)
    plain_robot = [b for b in plain if "*** " in b and b not in fenced]
    all_blocks  = fenced + plain_robot

    # Noms de fichiers dans le contexte (backtick, header, bold)
    filenames = (
        re.findall(r"`([a-zA-Z0-9_\-]+\.robot)`", text)
        + re.findall(r"###?\s+([a-zA-Z0-9_\-]+\.robot)", text)
        + re.findall(r"\*\*([a-zA-Z0-9_\-]+\.robot)\*\*", text)
    )

    for i, block in enumerate(all_blocks):
        block = block.strip()
        if not block or "*** " not in block:
            continue

        fname = filenames[i] if i < len(filenames) else (
            f"test_login_{i+1}.robot"
            if "*** Test Cases" in block and "login" in block.lower()
            else f"page_object_{i+1}.robot"
            if "*** Keywords" in block
            else f"generated_{i+1}.robot"
        )

        blocks[fname] = block
        print(f"   📄 Bloc RF extrait → {fname} ({len(block)} chars)")

    if not blocks:
        print("   ⚠️  Aucun bloc Robot trouvé — vérifiez llm_response.md")
    return blocks


def _classify_robot_file(fname: str, content: str) -> str:
    """Détermine si un fichier est un Page Object ou une Test Suite."""
    fname_lower = fname.lower()
    if "_page" in fname_lower or "page_" in fname_lower:
        return "page_object"
    if "*** Test Cases ***" in content or "*** Test Cases\n" in content:
        return "test_suite"
    if "*** Keywords ***" in content and "*** Test Cases" not in content:
        return "page_object"
    return "test_suite"


def _save_agent_results(
    workflow: str, page: str, screen_data: dict,
    llm_response: str, robot_files: dict,
) -> list:
    """
    Sauvegarde les résultats selon la structure POM :

    tests/suites/{page}/
        {page}_page.robot     ← Page Object (locators + keywords)
        test_{page}.robot     ← Test Cases

    agent_results/{timestamp}_{workflow}_{page}/
        llm_response.md       ← Réponse brute Gemini
        screen_context.json   ← Contexte UI capturé
    """
    now      = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(RESULTS_DIR) / f"{now}_{workflow}_{page}"
    out_path.mkdir(parents=True, exist_ok=True)
    saved    = []

    # Réponse LLM
    llm_path = out_path / "llm_response.md"
    llm_path.write_text(
        f"# Agent Appium — Workflow: {workflow}\n"
        f"_Page: {page} | {datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
        + llm_response,
        encoding="utf-8",
    )
    saved.append(str(llm_path))

    # Contexte écran (sans screenshot pour alléger)
    ctx_path = out_path / "screen_context.json"
    ctx_path.write_text(
        json.dumps({k: v for k, v in screen_data.items() if k != "screenshot"},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    saved.append(str(ctx_path))

    # Fichiers Robot (structure POM)
    if robot_files:
        suite_dir = Path(TESTS_SUITES_DIR) / page
        suite_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n   📁 Structure POM → {suite_dir}")

        for fname, file_content in robot_files.items():
            file_type   = _classify_robot_file(fname, file_content)
            target_name = f"{page}_page.robot" if file_type == "page_object" else f"test_{page}.robot"
            target_path = suite_dir / target_name

            if target_path.exists():
                target_path.rename(suite_dir / f"{target_name}.bak")
                print(f"   💾 Backup : {target_name}.bak")

            target_path.write_text(file_content, encoding="utf-8")
            saved.append(str(target_path))
            icon = "📋" if file_type == "page_object" else "🧪"
            print(f"   {icon} {file_type:12} → {target_path}")

        print(f"\n   ✅ {len(robot_files)} fichier(s) → {suite_dir}")
        print(f"      robot --listener allure_robotframework "
              f"--outputdir output/allure {suite_dir / f'test_{page}.robot'}")

    print(f"   📊 Logs → {out_path}")
    return saved


# ============================================================================
# POINT D'ENTRÉE — CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Appium Agent — MyBiat Test Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python appium_agent.py --workflow analyze
  python appium_agent.py --workflow self-healing --locator btn_login_old --context "bouton connexion"
  python appium_agent.py --workflow validate --test-file tests/suites/login/test_login.robot
  python appium_agent.py --diagnose
""",
    )
    parser.add_argument("--workflow",       choices=["analyze", "self-healing", "validate"], default="analyze")
    parser.add_argument("--locator",        type=str, default=None,    help="ID du locator cassé (self-healing)")
    parser.add_argument("--context",        type=str, default=None,    help="Indice sur le rôle de l'élément")
    parser.add_argument("--test-file",      type=str, default=None,    help="Fichier .robot à exécuter")
    parser.add_argument("--tags",           type=str, default=None,    help="Tags Robot Framework à inclure")
    parser.add_argument("--no-screenshot",  action="store_true",       help="Ne pas inclure le screenshot")
    parser.add_argument("--no-save",        action="store_true",       help="Ne pas sauvegarder les résultats")
    parser.add_argument("--auto-apply",     action="store_true",       help="Appliquer le fix et relancer le test")
    parser.add_argument("--diagnose",       action="store_true",       help="Diagnostic du serveur MCP")

    args  = parser.parse_args()
    agent = AppiumAgent()

    if args.diagnose:
        await agent._diagnose_server()
        return

    if args.workflow == "analyze":
        result = await agent.workflow_analyze_screen(
            include_screenshot=not args.no_screenshot,
            save_results=not args.no_save,
        )
    elif args.workflow == "self-healing":
        if not args.locator:
            print("❌ --locator requis pour self-healing")
            return
        result = await agent.workflow_self_healing(
            broken_locator_id=args.locator,
            context_hint=args.context,
            test_file=args.test_file,
            auto_apply=args.auto_apply,
        )
    elif args.workflow == "validate":
        if not args.test_file:
            print("❌ --test-file requis pour validate")
            return
        result = await agent.workflow_validate_test(
            test_file=args.test_file,
            test_tags=args.tags,
        )
    else:
        print(f"❌ Workflow inconnu : {args.workflow}")
        return

    print("\n" + "=" * 60)
    print("  RÉSULTAT FINAL")
    print("=" * 60)
    print(json.dumps(
        {k: v for k, v in result.items() if k != "gemini_response"},
        indent=2, ensure_ascii=False, default=str,
    ))


if __name__ == "__main__":
    asyncio.run(main())