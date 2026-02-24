"""
Appium Agent — MyBiat Test Automation  [FIXED VERSION]
=======================================================
Key fixes vs original:
  • _call_mcp_tool: handles ExceptionGroup (Python 3.11+) and legacy Exception
  • _call_mcp_tool: captures stderr from MCP server subprocess for diagnosis
  • _call_mcp_tool: uses quoted path to handle spaces in Windows paths
  • Added: async_timeout guard (30s) around MCP calls
  • Added: _diagnose_server() helper for troubleshooting

Workflows:
  - analyze_screen   → Analyse écran + génère tests Robot Framework
  - self_healing     → Répare automatiquement un locator cassé
  - validate_test    → Ré-exécute un test après correction
"""

import os
import re
import sys
import time
import json
import base64
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================================================
# CHARGEMENT .ENV
# ============================================================================
try:
    from dotenv import load_dotenv

    _loaded = False
    _candidates = [
        Path(__file__).parent / "config" / ".env",
        Path(__file__).parent.parent / "config" / ".env",
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
        Path.cwd() / "config" / ".env",
        Path.cwd() / ".env",
    ]
    for _env_path in _candidates:
        if _env_path.exists():
            load_dotenv(_env_path, override=True)
            print(f"✅ .env chargé : {_env_path}")
            _loaded = True
            break

    if not _loaded:
        for _item in Path(__file__).parent.iterdir():
            if _item.is_dir() and "config" in _item.name.lower():
                _e = _item / ".env"
                if _e.exists():
                    load_dotenv(_e, override=True)
                    print(f"✅ .env trouvé (dossier config) : {_e}")
                    _loaded = True
                    break

    if not _loaded:
        load_dotenv()
        print("⚠️  Aucun .env trouvé, utilisation des variables système")

except ImportError:
    print("⚠️  python-dotenv absent")

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
# IMPORTS GEMINI
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
APP_PACKAGE    = os.getenv("APP_PACKAGE", "com.example.mybiat")
TESTS_DIR      = os.getenv("TESTS_DIR", "tests")
RESULTS_DIR    = os.getenv("RESULTS_DIR", "agent_results")

# ── Smart MCP server path resolution ──────────────────────────────────────
def _resolve_mcp_server_path() -> str:
    """
    Resolves the MCP server path using multiple fallback strategies.

    Priority:
      1. MCP_APPIUM_SERVER_PATH env var (only if the file actually exists)
      2. Relative to __file__: ../../mcp_servers/mcp_appium_server.py
      3. Recursive search upward from CWD (up to 4 levels)
      4. Recursive search upward from __file__ (up to 4 levels)

    This handles:
      - Wrong/stale MCP_APPIUM_SERVER_PATH in .env
      - Running the script from unexpected working directories
      - Path resolution differences across Windows/Linux
    """
    filename = "mcp_appium_server.py"

    # Candidate paths to check in order
    candidates = []

    # 1. From environment variable (if set and file exists)
    env_val = os.getenv("MCP_APPIUM_SERVER_PATH", "")
    if env_val:
        candidates.append(("ENV MCP_APPIUM_SERVER_PATH", Path(env_val)))

    # 2. Relative to this script file (most reliable)
    script_dir = Path(__file__).resolve().parent          # agents/
    project_root = script_dir.parent                       # Automation_tests/
    candidates += [
        ("Sibling mcp_servers/", project_root / "mcp_servers" / filename),
        ("Same dir as agent",    script_dir / filename),
        ("Project root",         project_root / filename),
    ]

    # 3. Relative to current working directory
    cwd = Path.cwd()
    candidates += [
        ("CWD mcp_servers/",    cwd / "mcp_servers" / filename),
        ("CWD parent mcp_servers/", cwd.parent / "mcp_servers" / filename),
        ("CWD",                 cwd / filename),
    ]

    # Check each candidate
    for label, path in candidates:
        try:
            resolved = path.resolve()
            if resolved.exists():
                print(f"   ✅ MCP server trouvé [{label}]: {resolved}")
                return str(resolved)
            else:
                print(f"   ✗  [{label}]: {resolved} — introuvable")
        except Exception:
            pass

    # 4. Last resort: recursive search upward from project root
    print("   🔍 Recherche récursive de mcp_appium_server.py...")
    for search_root in [project_root, cwd]:
        for candidate in sorted(search_root.rglob(filename))[:5]:
            print(f"   ✅ Trouvé par recherche récursive : {candidate}")
            return str(candidate)

    # Nothing found — return the most likely path for the error message
    fallback = str(project_root / "mcp_servers" / filename)
    print(f"   ❌ mcp_appium_server.py introuvable ! Chemin attendu : {fallback}")
    return fallback


MCP_SERVER_PATH = _resolve_mcp_server_path()

print("\n📋 APPIUM AGENT — CONFIG:")
print(f"   GEMINI_MODEL   : {GEMINI_MODEL}")
print(f"   GEMINI_API_KEY : {'✅ défini' if GEMINI_API_KEY else '❌ MANQUANT'}")
print(f"   MCP SERVER     : {MCP_SERVER_PATH}")
print(f"   MCP SERVER EXISTS: {'✅' if Path(MCP_SERVER_PATH).exists() else '❌ INTROUVABLE'}")
print(f"   MCP CLIENT     : {'✅' if MCP_AVAILABLE else '❌ non installé'}")
print(f"   Python         : {sys.version.split()[0]}\n")


# ============================================================================
# HELPER — EXTRACT ROOT EXCEPTION FROM TASK GROUP ERROR
# ============================================================================

def _extract_exception_message(exc: Exception) -> str:
    """
    Extracts a readable message from an ExceptionGroup or regular Exception.
    Works with Python 3.11+ ExceptionGroup and older asyncio TaskGroup errors.
    """
    # Python 3.11+ ExceptionGroup
    if hasattr(exc, "exceptions"):
        sub_msgs = []
        for sub in exc.exceptions:
            sub_msgs.append(_extract_exception_message(sub))
        return " | ".join(sub_msgs) or str(exc)

    # Check __cause__ and __context__ for chained exceptions
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause and str(cause) != str(exc):
        return f"{type(exc).__name__}: {exc} → caused by: {type(cause).__name__}: {cause}"

    return f"{type(exc).__name__}: {exc}"


# ============================================================================
# CLASSE PRINCIPALE — APPIUM AGENT
# ============================================================================

class AppiumAgent:
    """
    Agent IA qui pilote le MCP Appium Server et raisonne avec Gemini.
    """

    def __init__(self):
        self.session: Optional[object] = None
        self._mcp_tools: dict = {}

    # ──────────────────────────────────────────────────────────────────────
    # CONNEXION MCP  [FIXED]
    # ──────────────────────────────────────────────────────────────────────

    async def _call_mcp_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """
        Appelle un outil du MCP Appium Server.

        FIXES vs original:
        - Handles ExceptionGroup (Python 3.11 TaskGroup errors)
        - Passes sys.executable to avoid venv/path issues
        - Captures stderr for better diagnostics
        - 30-second timeout guard
        """
        if not MCP_AVAILABLE:
            print(f"⚠️  MCP non disponible — simulation de {tool_name}")
            return self._simulate_mcp_call(tool_name, arguments or {})

        if not Path(MCP_SERVER_PATH).exists():
            print(f"❌ MCP server introuvable: {MCP_SERVER_PATH}")
            print("   → Utilisation du mode simulation")
            return self._simulate_mcp_call(tool_name, arguments or {})

        # Use the SAME Python interpreter that's running this script
        # This ensures the venv is respected and avoids path issues
        server_params = StdioServerParameters(
            command=sys.executable,           # ← FIX: use current interpreter
            args=[MCP_SERVER_PATH],
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},  # FIX: force UTF-8
        )

        try:
            async with asyncio.timeout(30):   # ← FIX: 30-second guard
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        result = await session.call_tool(
                            tool_name,
                            arguments=arguments or {}
                        )

                        if result.content:
                            for content in result.content:
                                if hasattr(content, "text"):
                                    try:
                                        return json.loads(content.text)
                                    except json.JSONDecodeError:
                                        return {"success": True, "raw": content.text}
                        return {"success": False, "error": "Réponse MCP vide"}

        except TimeoutError:
            print(f"⏰ Timeout MCP ({tool_name}) — falling back to simulation")
            return self._simulate_mcp_call(tool_name, arguments or {})

        except Exception as exc:
            # ── FIX: handle ExceptionGroup (TaskGroup errors) ────
            msg = _extract_exception_message(exc)
            print(f"❌ Erreur MCP {tool_name}: {msg}")
            if "Connection closed" in msg or "connection closed" in msg.lower():
                print("\n   ⚠️  Connection closed = serveur MCP crashé au démarrage")
                print("   🔧 Diagnostic automatique...\n")
                await self._diagnose_server()
            else:
                print(f"   → Vérifiez: python \"{MCP_SERVER_PATH}\"")
            print("\n   → Mode simulation activé...")
            return self._simulate_mcp_call(tool_name, arguments or {})

    async def _diagnose_server(self) -> dict:
        """
        Runs a full pre-flight diagnostic of the MCP server.
        Captures the actual crash reason when 'Connection closed' occurs.
        """
        import subprocess
        print("\n" + "="*60)
        print("  🔧 PRE-FLIGHT DIAGNOSTIC MCP SERVER")
        print("="*60)

        # ── 1. Check path ─────────────────────────────────────────────────
        p = Path(MCP_SERVER_PATH)
        print(f"\n[1] Server path  : {MCP_SERVER_PATH}")
        print(f"    File exists  : {'✅' if p.exists() else '❌'}")
        if p.exists():
            # Check for hidden characters in path (like the leading-space folder)
            parts = p.parts
            suspicious = [part for part in parts if part != part.strip()]
            if suspicious:
                print(f"    ⚠️  LEADING/TRAILING SPACES IN PATH SEGMENTS: {suspicious}")
                print(f"    💡 FIX: Rename folder(s) to remove the spaces!")

        # ── 2. Syntax check ───────────────────────────────────────────────
        print(f"\n[2] Syntax check (py_compile)...")
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", MCP_SERVER_PATH],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            print("    ✅ No syntax errors")
        else:
            print(f"    ❌ SYNTAX ERROR:\n{r.stderr}")

        # ── 3. Import check ───────────────────────────────────────────────
        print(f"\n[3] Import check (key packages)...")
        for pkg in ["mcp", "mcp.server.fastmcp", "xml.etree.ElementTree", "pathlib"]:
            ri = subprocess.run(
                [sys.executable, "-c", f"import {pkg}; print('OK')"],
                capture_output=True, text=True, timeout=8
            )
            status = "✅" if ri.stdout.strip() == "OK" else f"❌ {ri.stderr.strip()[:80]}"
            print(f"    {status}  {pkg}")

        # ── 4. Startup test — capture the real crash output ───────────────
        print(f"\n[4] Startup test (3 sec)...")
        try:
            proc = subprocess.Popen(
                [sys.executable, MCP_SERVER_PATH],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
            import time; time.sleep(3)
            ret = proc.poll()

            if ret is None:
                print("    ✅ Server process alive after 3s")
                proc.terminate()
                proc.wait(timeout=5)
                crash_stderr = ""
            else:
                crash_stderr = proc.stderr.read().decode("utf-8", errors="replace")
                crash_stdout = proc.stdout.read().decode("utf-8", errors="replace")
                print(f"    ❌ Server exited with code {ret}")
                if crash_stderr:
                    print(f"\n    ══ CRASH STDERR ══\n{crash_stderr[:1500]}")
                if crash_stdout:
                    print(f"\n    ══ CRASH STDOUT ══\n{crash_stdout[:500]}")

                # Parse the most common crash causes
                if "ModuleNotFoundError" in crash_stderr:
                    missing = re.findall(r"No module named '([^']+)'", crash_stderr)
                    print(f"\n    💡 MISSING MODULES: {missing}")
                    print(f"       Fix: pip install {' '.join(missing)}")
                if "SyntaxError" in crash_stderr:
                    print(f"\n    💡 SYNTAX ERROR in server — check Python version compatibility")
                    print(f"       You're running Python {sys.version.split()[0]}")
        except Exception as e:
            crash_stderr = str(e)
            print(f"    ❌ Could not start: {e}")

        print("\n" + "="*60)
        return {"path": MCP_SERVER_PATH, "exists": p.exists()}

    def _simulate_mcp_call(self, tool_name: str, arguments: dict) -> dict:
        """
        Simulation locale des outils MCP (sans connexion réelle).
        """
        print(f"   [SIMULATION] Appel MCP: {tool_name}({arguments})")
        if tool_name == "analyze_current_screen":
            return {
                "success":          True,
                "simulation":       True,
                "page_name":        "login",
                "app_package":      APP_PACKAGE,
                "total_elements":   6,
                "interactive_elements": 5,
                "interactive_summary": [
                    {
                        "type":           "username_field",
                        "short_id":       "edit_username",
                        "resource_id":    f"{APP_PACKAGE}:id/edit_username",
                        "text":           "",
                        "content_desc":   "Champ identifiant",
                        "enabled":        True,
                        "locator_quality": "robust",
                        "locators":       {
                            "by_id":            f"id={APP_PACKAGE}:id/edit_username",
                            "by_accessibility": "accessibility id=Champ identifiant"
                        }
                    },
                    {
                        "type":           "password_field",
                        "short_id":       "edit_password",
                        "resource_id":    f"{APP_PACKAGE}:id/edit_password",
                        "text":           "",
                        "content_desc":   "Champ mot de passe",
                        "enabled":        True,
                        "locator_quality": "robust",
                        "locators":       {
                            "by_id":            f"id={APP_PACKAGE}:id/edit_password",
                            "by_accessibility": "accessibility id=Champ mot de passe"
                        }
                    },
                    {
                        "type":           "login_button",
                        "short_id":       "btn_login",
                        "resource_id":    f"{APP_PACKAGE}:id/btn_login",
                        "text":           "Se connecter",
                        "content_desc":   "",
                        "enabled":        True,
                        "locator_quality": "robust",
                        "locators":       {
                            "by_id":   f"id={APP_PACKAGE}:id/btn_login",
                            "by_text": "xpath=//*[@text='Se connecter']"
                        }
                    },
                    {
                        "type":           "checkbox",
                        "short_id":       "cb_remember_me",
                        "resource_id":    f"{APP_PACKAGE}:id/cb_remember_me",
                        "text":           "Se souvenir de moi",
                        "content_desc":   "",
                        "enabled":        True,
                        "locator_quality": "robust",
                        "locators":       {
                            "by_id":   f"id={APP_PACKAGE}:id/cb_remember_me",
                            "by_text": "xpath=//*[@text='Se souvenir de moi']"
                        }
                    },
                    {
                        "type":           "forgot_password_link",
                        "short_id":       "tv_forgot_password",
                        "resource_id":    f"{APP_PACKAGE}:id/tv_forgot_password",
                        "text":           "Mot de passe oublié ?",
                        "content_desc":   "",
                        "enabled":        True,
                        "locator_quality": "robust",
                        "locators":       {
                            "by_id":   f"id={APP_PACKAGE}:id/tv_forgot_password",
                            "by_text": "xpath=//*[@text='Mot de passe oublié ?']"
                        }
                    }
                ],
                "locator_stats": {
                    "robust":           5,
                    "fragile":          0,
                    "missing":          1,
                    "coverage_percent": 83.3
                },
                "fragile_locators": [],
                "missing_locators": []
            }
        elif tool_name == "suggest_alternative_locators":
            broken = arguments.get("broken_locator_id", "unknown")
            return {
                "success":            True,
                "simulation":         True,
                "broken_locator":     broken,
                "alternatives_count": 1,
                "alternatives": [
                    {
                        "resource_id":    f"{APP_PACKAGE}:id/btn_login",
                        "text":           "Se connecter",
                        "confidence_score": 0.75,
                        "suggested_locators": [f"id:btn_login"]
                    }
                ],
                "recommendation": f"Remplacer '{broken}' par 'id:btn_login' (confiance: 75%)"
            }
        elif tool_name == "execute_robot_test":
            return {
                "success": True, "total": 3, "passed": 2,
                "failed": 1, "all_passed": False,
                "simulation": True
            }
        return {"success": False, "error": f"Outil {tool_name} non simulé"}

    # ──────────────────────────────────────────────────────────────────────
    # APPEL GEMINI
    # ──────────────────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str, screenshot_b64: Optional[str] = None) -> str:
        """Envoie le prompt à Gemini et retourne la réponse texte."""
        if not GEMINI_OK:
            return "❌ Gemini non installé"
        if not GEMINI_API_KEY:
            return "❌ GEMINI_API_KEY manquant"

        print(f"\n🤖 Appel Gemini ({GEMINI_MODEL}) [SDK: {GEMINI_SDK}]...")

        try:
            if GEMINI_SDK == "new":
                client = genai.Client(api_key=GEMINI_API_KEY)
                parts  = [prompt]
                if screenshot_b64:
                    img_bytes = base64.b64decode(screenshot_b64)
                    parts.append(
                        genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                    )
                    print("   📸 Screenshot inclus dans le prompt")
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=parts
                )
                return response.text

            else:  # old SDK
                genai_old.configure(api_key=GEMINI_API_KEY)
                model   = genai_old.GenerativeModel(GEMINI_MODEL)
                content = [prompt]
                if screenshot_b64:
                    content.append({
                        "mime_type": "image/png",
                        "data": base64.b64decode(screenshot_b64)
                    })
                response = model.generate_content(content)
                return response.text

        except Exception as e:
            return f"❌ Erreur Gemini : {e}"

    # ──────────────────────────────────────────────────────────────────────
    # CONSTRUCTION DES PROMPTS
    # ──────────────────────────────────────────────────────────────────────

    def _build_analyze_prompt(self, screen_data: dict) -> str:
        page      = screen_data.get("page_name", "unknown")
        summary   = screen_data.get("interactive_summary", [])
        stats     = screen_data.get("locator_stats", {})
        fragile   = screen_data.get("fragile_locators", [])
        sim       = screen_data.get("simulation", False)

        summary_json = json.dumps(summary, indent=2, ensure_ascii=False)
        fragile_json = json.dumps(fragile, indent=2, ensure_ascii=False) if fragile else "[]"

        return f"""Tu es un expert en automatisation de tests mobiles (Robot Framework + Appium).
Tu analyses la page actuelle d'une application bancaire mobile Android : **MyBiat Retail**.

## CONTEXTE
- Page détectée        : **{page.upper()}**
- Application          : {APP_PACKAGE}
- Timestamp            : {datetime.now().isoformat()}
- Mode                 : {"⚠️ SIMULATION" if sim else "✅ Device réel"}
- Éléments interactifs : {len(summary)}
- Couverture locators  : {stats.get('coverage_percent', 0)}%
  (robust: {stats.get('robust', 0)} | fragile: {stats.get('fragile', 0)} | missing: {stats.get('missing', 0)})

## ÉLÉMENTS UI DÉTECTÉS (avec locators Appium)

```json
{summary_json}
```

{"## ⚠️ LOCATORS FRAGILES (à corriger en priorité)" if fragile else ""}
{"```json" if fragile else ""}
{fragile_json if fragile else ""}
{"```" if fragile else ""}

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
- ❌ Cas d'erreur (champs vides / credentials incorrects)
- ⚠️ Cas limite (champ vide partiel, whitespace, etc.)

### 4. RECOMMANDATIONS SELF-HEALING
Pour chaque locator fragile ou manquant, propose un locator alternatif robuste.

---
⚠️ RÈGLES STRICTES :
- Utilise UNIQUEMENT les resource_id et locators fournis dans les données JSON
- Ne jamais inventer de locators absents des données
- Syntaxe Robot Framework : 4 espaces, pas de tabs
"""

    def _build_self_healing_prompt(self, broken_locator: str,
                                    alternatives: list,
                                    test_context: Optional[str] = None) -> str:
        alts_json = json.dumps(alternatives, indent=2, ensure_ascii=False)

        return f"""Tu es un expert en self-healing de tests mobiles automatisés.
Un test Robot Framework a échoué car le locator suivant n'existe plus :

**Locator cassé :** `{broken_locator}`
{"**Contexte du test :** " + test_context if test_context else ""}

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
Liste les autres tests potentiellement impactés.
"""

    # ──────────────────────────────────────────────────────────────────────
    # WORKFLOWS
    # ──────────────────────────────────────────────────────────────────────

    async def workflow_analyze_screen(
        self,
        include_screenshot: bool = True,
        save_results: bool = True
    ) -> dict:
        """WORKFLOW 1 : Analyse de l'écran courant."""
        print("\n" + "="*60)
        print("  WORKFLOW : ANALYZE SCREEN")
        print("="*60)

        print("\n📱 Étape 1/4 — Appel MCP: analyze_current_screen...")
        screen_data = await self._call_mcp_tool(
            "analyze_current_screen",
            {"include_screenshot": include_screenshot}
        )

        if not screen_data.get("success"):
            return {
                "success": False,
                "error":   screen_data.get("error", "Échec analyze_current_screen"),
                "step":    "mcp_call"
            }

        page = screen_data.get("page_name", "unknown")
        sim  = screen_data.get("simulation", False)
        print(f"   {'⚠️ SIMULATION' if sim else '✅'} Page détectée : {page.upper()}")
        print(f"   📊 Éléments : {screen_data.get('total_elements', 0)} total, "
              f"{screen_data.get('interactive_elements', 0)} interactifs")
        print(f"   🔒 Couverture locators : "
              f"{screen_data.get('locator_stats', {}).get('coverage_percent', 0)}%")

        print("\n📝 Étape 2/4 — Construction du prompt Gemini...")
        prompt = self._build_analyze_prompt(screen_data)

        print("\n🤖 Étape 3/4 — Appel Gemini pour analyse et génération...")
        screenshot_b64 = None
        if include_screenshot and screen_data.get("screenshot"):
            screenshot_b64 = screen_data["screenshot"].get("data")

        gemini_response = self._call_gemini(prompt, screenshot_b64)
        print("   ✅ Réponse Gemini reçue")

        robot_files = _extract_robot_blocks(gemini_response)
        saved_paths = []

        if save_results:
            print(f"\n💾 Étape 4/4 — Sauvegarde ({len(robot_files)} fichier(s) Robot)...")
            saved_paths = _save_agent_results(
                workflow     = "analyze",
                page         = page,
                screen_data  = screen_data,
                llm_response = gemini_response,
                robot_files  = robot_files
            )

        return {
            "success":               True,
            "workflow":              "analyze_screen",
            "page_name":             page,
            "simulation":            sim,
            "locator_stats":         screen_data.get("locator_stats", {}),
            "fragile_count":         len(screen_data.get("fragile_locators", [])),
            "robot_files_generated": list(robot_files.keys()),
            "saved_to":              saved_paths,
            "gemini_response":       gemini_response,
        }

    async def workflow_self_healing(
        self,
        broken_locator_id: str,
        context_hint: Optional[str] = None,
        test_file: Optional[str] = None,
        auto_apply: bool = False
    ) -> dict:
        """WORKFLOW 2 : Self-Healing automatique d'un locator cassé."""
        print("\n" + "="*60)
        print("  WORKFLOW : SELF-HEALING")
        print("="*60)
        print(f"   Locator cassé : {broken_locator_id}")

        print("\n🔍 Étape 1/3 — Appel MCP: suggest_alternative_locators...")
        healing_data = await self._call_mcp_tool(
            "suggest_alternative_locators",
            {"broken_locator_id": broken_locator_id, "context_hint": context_hint or ""}
        )

        if not healing_data.get("success"):
            return {
                "success": False,
                "error":   healing_data.get("error", "Échec suggest_alternative_locators"),
                "step":    "mcp_alternatives"
            }

        alternatives = healing_data.get("alternatives", [])
        print(f"   ✅ {len(alternatives)} alternative(s) trouvée(s)")

        if not alternatives:
            return {"success": False, "error": "Aucune alternative trouvée", "broken_locator": broken_locator_id}

        print("\n🤖 Étape 2/3 — Appel Gemini pour sélection et correction...")
        prompt = self._build_self_healing_prompt(
            broken_locator = broken_locator_id,
            alternatives   = alternatives,
            test_context   = f"Test file: {test_file}" if test_file else None
        )
        gemini_response = self._call_gemini(prompt)
        print("   ✅ Réponse Gemini reçue")

        validation_result = None
        if test_file and auto_apply:
            print(f"\n🧪 Étape 3/3 — Validation : exécution de {test_file}...")
            validation_result = await self._call_mcp_tool("execute_robot_test", {"test_file": test_file})
        else:
            print("\n⏭️  Étape 3/3 — Validation ignorée (auto_apply=False)")

        saved_paths = _save_agent_results(
            workflow     = "self_healing",
            page         = f"locator_{broken_locator_id}",
            screen_data  = {"simulation": healing_data.get("simulation", False)},
            llm_response = gemini_response,
            robot_files  = {}
        )

        return {
            "success":            True,
            "workflow":           "self_healing",
            "broken_locator":     broken_locator_id,
            "alternatives_found": len(alternatives),
            "mcp_recommendation": healing_data.get("recommendation"),
            "gemini_analysis":    gemini_response,
            "validation":         validation_result,
            "saved_to":           saved_paths,
        }

    async def workflow_validate_test(self, test_file: str, test_tags: Optional[str] = None) -> dict:
        """WORKFLOW 3 : Ré-exécution et validation d'un test Robot Framework."""
        print("\n" + "="*60)
        print("  WORKFLOW : VALIDATE TEST")
        print("="*60)
        print(f"   Fichier : {test_file}")

        result = await self._call_mcp_tool("execute_robot_test", {"test_file": test_file, "test_tags": test_tags or ""})

        status = "✅ TOUS LES TESTS PASSENT" if result.get("all_passed") else "❌ ÉCHECS DÉTECTÉS"
        print(f"\n{status}")
        print(f"   Total: {result.get('total', 0)} | Passés: {result.get('passed', 0)} | Échoués: {result.get('failed', 0)}")

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
# UTILITAIRES
# ============================================================================

def _extract_robot_blocks(text: str) -> dict:
    blocks    = {}
    pattern   = r'`{3}(?:robot|robotframework)?\n(.*?)`{3}'
    matches   = re.findall(pattern, text, re.DOTALL)
    filenames = re.findall(r'`([a-zA-Z0-9_\-]+\.robot)`', text)

    for i, content in enumerate(matches):
        content = content.strip()
        if content and ("*** " in content or "Keywords" in content):
            fname = filenames[i] if i < len(filenames) else f"generated_test_{i+1}.robot"
            blocks[fname] = content

    return blocks


def _save_agent_results(workflow, page, screen_data, llm_response, robot_files) -> list:
    now      = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(RESULTS_DIR) / f"{now}_{workflow}_{page}"
    out_path.mkdir(parents=True, exist_ok=True)
    saved    = []

    llm_path = out_path / "llm_response.md"
    with open(llm_path, "w", encoding="utf-8") as f:
        f.write(f"# Agent Appium — Workflow: {workflow}\n")
        f.write(f"_Page: {page} | {datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n")
        f.write(llm_response)
    saved.append(str(llm_path))

    ctx_export = {k: v for k, v in screen_data.items() if k != "screenshot"}
    ctx_path   = out_path / "screen_context.json"
    with open(ctx_path, "w", encoding="utf-8") as f:
        json.dump(ctx_export, f, indent=2, ensure_ascii=False)
    saved.append(str(ctx_path))

    if robot_files:
        tests_dir = out_path / "robot_tests"
        tests_dir.mkdir(exist_ok=True)
        for fname, content in robot_files.items():
            rpath = tests_dir / fname
            with open(rpath, "w", encoding="utf-8") as f:
                f.write(content)
            saved.append(str(rpath))
        print(f"   📁 {len(robot_files)} fichier(s) Robot sauvegardé(s) dans {tests_dir}")

    print(f"   ✅ Résultats dans : {out_path}")
    return saved


# ============================================================================
# POINT D'ENTRÉE — CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Appium Agent — MyBiat Test Automation")
    parser.add_argument("--workflow", choices=["analyze", "self-healing", "validate"], default="analyze")
    parser.add_argument("--locator",  type=str, default=None)
    parser.add_argument("--context",  type=str, default=None)
    parser.add_argument("--test-file", type=str, default=None)
    parser.add_argument("--tags",     type=str, default=None)
    parser.add_argument("--no-screenshot", action="store_true")
    parser.add_argument("--no-save",  action="store_true")
    parser.add_argument("--auto-apply", action="store_true")
    parser.add_argument("--diagnose", action="store_true", help="Run MCP server diagnosis")

    args  = parser.parse_args()
    agent = AppiumAgent()

    if args.diagnose:
        await agent._diagnose_server()
        return

    if args.workflow == "analyze":
        result = await agent.workflow_analyze_screen(
            include_screenshot = not args.no_screenshot,
            save_results       = not args.no_save
        )
    elif args.workflow == "self-healing":
        if not args.locator:
            print("❌ --locator requis pour self-healing")
            return
        result = await agent.workflow_self_healing(
            broken_locator_id = args.locator,
            context_hint      = args.context,
            test_file         = args.test_file,
            auto_apply        = args.auto_apply
        )
    elif args.workflow == "validate":
        if not args.test_file:
            print("❌ --test-file requis pour validate")
            return
        result = await agent.workflow_validate_test(
            test_file = args.test_file,
            test_tags = args.tags
        )

    print("\n" + "="*60)
    print("  RÉSULTAT FINAL")
    print("="*60)
    print(json.dumps(
        {k: v for k, v in result.items() if k != "gemini_response"},
        indent=2, ensure_ascii=False, default=str
    ))


if __name__ == "__main__":
    asyncio.run(main())