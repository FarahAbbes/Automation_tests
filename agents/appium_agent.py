"""
Appium Agent — MyBiat Test Automation
=======================================
Agent IA qui consomme le MCP Appium Server et orchestre les workflows via Gemini.

Workflows implémentés :
  - analyze_screen      → Analyse l'écran courant + génère tests Robot Framework
  - self_healing        → Répare automatiquement un locator cassé
  - validate_test       → Ré-exécute un test après correction et valide

Usage:
    python appium_agent.py --workflow analyze
    python appium_agent.py --workflow self-healing --locator btn_login_old
    python appium_agent.py --workflow validate --test-file tests/login_test.robot
"""

import os
import re
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

    # Cherche aussi les dossiers config avec espace caché
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

# Chemin vers le MCP Appium Server
MCP_SERVER_PATH = os.getenv(
    "MCP_APPIUM_SERVER_PATH",
    str(Path(__file__).parent / "mcp_appium_server.py")
)

print("\n📋 APPIUM AGENT — CONFIG:")
print(f"   GEMINI_MODEL   : {GEMINI_MODEL}")
print(f"   GEMINI_API_KEY : {'✅ défini' if GEMINI_API_KEY else '❌ MANQUANT'}")
print(f"   MCP SERVER     : {MCP_SERVER_PATH}")
print(f"   MCP CLIENT     : {'✅' if MCP_AVAILABLE else '❌ non installé'}\n")


# ============================================================================
# CLASSE PRINCIPALE — APPIUM AGENT
# ============================================================================

class AppiumAgent:
    """
    Agent IA qui pilote le MCP Appium Server et raisonne avec Gemini.

    Responsabilités (selon l'architecture) :
      • Appeler les outils MCP Appium pour récupérer le contexte UI
      • Construire des prompts contextuels pour le LLM
      • Interpréter les réponses Gemini et générer les artefacts
      • Retourner les résultats structurés à l'Orchestrateur
    """

    def __init__(self):
        self.session: Optional[object] = None
        self._mcp_tools: dict = {}

    # ──────────────────────────────────────────────────────────────────────
    # CONNEXION MCP
    # ──────────────────────────────────────────────────────────────────────

    async def _call_mcp_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """
        Appelle un outil du MCP Appium Server.
        Gère la connexion, l'appel et le parsing de la réponse.
        """
        if not MCP_AVAILABLE:
            print(f"⚠️  MCP non disponible — simulation de {tool_name}")
            return self._simulate_mcp_call(tool_name, arguments or {})

        server_params = StdioServerParameters(
            command="python",
            args=[MCP_SERVER_PATH],
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    result = await session.call_tool(
                        tool_name,
                        arguments=arguments or {}
                    )

                    # Parser le contenu retourné par le MCP
                    if result.content:
                        for content in result.content:
                            if hasattr(content, "text"):
                                try:
                                    return json.loads(content.text)
                                except json.JSONDecodeError:
                                    return {"success": True, "raw": content.text}
                    return {"success": False, "error": "Réponse MCP vide"}

        except Exception as e:
            print(f"❌ Erreur appel MCP {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    def _simulate_mcp_call(self, tool_name: str, arguments: dict) -> dict:
        """
        Simulation locale des outils MCP (sans connexion réelle).
        Utilisé quand le client MCP n'est pas disponible.
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
                            "by_id":          f"id={APP_PACKAGE}:id/edit_username",
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
                            "by_id":          f"id={APP_PACKAGE}:id/edit_password",
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
        return {"success": False, "error": f"Outil {tool_name} non simulé"}

    # ──────────────────────────────────────────────────────────────────────
    # APPEL GEMINI
    # ──────────────────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str, screenshot_b64: Optional[str] = None) -> str:
        """
        Envoie le prompt à Gemini et retourne la réponse texte.
        Supporte le nouveau SDK (google-genai) et l'ancien (google-generativeai).
        """
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
        """
        Construit le prompt d'analyse d'écran pour Gemini.
        Contexte fourni par analyze_current_screen du MCP Appium Server.
        """
        page      = screen_data.get("page_name", "unknown")
        summary   = screen_data.get("interactive_summary", [])
        stats     = screen_data.get("locator_stats", {})
        fragile   = screen_data.get("fragile_locators", [])
        missing   = screen_data.get("missing_locators", [])
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
  (Open {page.capitalize()} Page, Enter Credentials, Click Login, etc.)

### 3. GÉNÉRATION TEST CASES
Génère `test_{page}.robot` avec au moins 3 scénarios :
- ✅ Cas nominal (happy path avec données valides)
- ❌ Cas d'erreur (champs vides / credentials incorrects)
- ⚠️ Cas limite (champ vide partiel, whitespace, etc.)

### 4. RECOMMANDATIONS SELF-HEALING
Pour chaque locator fragile ou manquant, propose un locator alternatif robuste.
Format : `[element] : locator actuel → locator recommandé (raison)`

---
⚠️ RÈGLES STRICTES :
- Utilise UNIQUEMENT les resource_id et locators fournis dans les données JSON
- Ne jamais inventer de locators absents des données
- Syntaxe Robot Framework : 4 espaces, pas de tabs
- Chaque keyword doit être sur une ligne distincte
"""

    def _build_self_healing_prompt(self, broken_locator: str,
                                    alternatives: list,
                                    test_context: Optional[str] = None) -> str:
        """
        Construit le prompt de self-healing pour Gemini.
        L'IA choisit le meilleur locator parmi les alternatives proposées par le MCP.
        """
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
Justifie ton choix (stabilité, unicité, résistance aux changements de texte).

### 3. CODE CORRIGÉ
Fournis le code Robot Framework corrigé avec le nouveau locator.
Format attendu :
```robot
# AVANT (cassé)
${{OLD_LOCATOR}}    id=<ancien_id>

# APRÈS (corrigé)
${{NEW_LOCATOR}}    id=<nouvel_id>
```

### 4. IMPACT
Liste les autres tests potentiellement impactés par ce changement
(s'ils utilisent le même locator).

---
⚠️ Utilise UNIQUEMENT les locators présents dans les alternatives fournies.
Choisir le locator avec le meilleur score de confiance ET la stratégie la plus robuste.
"""

    # ──────────────────────────────────────────────────────────────────────
    # WORKFLOWS PUBLICS
    # ──────────────────────────────────────────────────────────────────────

    async def workflow_analyze_screen(
        self,
        include_screenshot: bool = True,
        save_results: bool = True
    ) -> dict:
        """
        WORKFLOW 1 : Analyse de l'écran courant.

        Étapes :
          1. Appel MCP → analyze_current_screen (UI enrichie)
          2. Construction prompt contextuel
          3. Appel Gemini → analyse + génération tests
          4. Extraction et sauvegarde des fichiers Robot Framework
          5. Retour résultat structuré à l'Orchestrateur

        Returns:
            Dict avec page_name, gemini_response, robot_files, locator_stats
        """
        print("\n" + "="*60)
        print("  WORKFLOW : ANALYZE SCREEN")
        print("="*60)

        # ── Étape 1 : Récupérer l'UI via MCP ──────────────────────────────
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
        print(f"   ✅ Page détectée : {page.upper()}")
        print(f"   📊 Éléments : {screen_data.get('total_elements', 0)} total, "
              f"{screen_data.get('interactive_elements', 0)} interactifs")
        print(f"   🔒 Couverture locators : "
              f"{screen_data.get('locator_stats', {}).get('coverage_percent', 0)}%")

        # ── Étape 2 : Construire le prompt ─────────────────────────────────
        print("\n📝 Étape 2/4 — Construction du prompt Gemini...")
        prompt = self._build_analyze_prompt(screen_data)

        # ── Étape 3 : Appel Gemini ─────────────────────────────────────────
        print("\n🤖 Étape 3/4 — Appel Gemini pour analyse et génération...")
        screenshot_b64 = None
        if include_screenshot and screen_data.get("screenshot"):
            screenshot_b64 = screen_data["screenshot"].get("data")

        gemini_response = self._call_gemini(prompt, screenshot_b64)
        print("   ✅ Réponse Gemini reçue")

        # ── Étape 4 : Extraire et sauvegarder les fichiers Robot ───────────
        robot_files = _extract_robot_blocks(gemini_response)
        saved_paths = []

        if save_results:
            print(f"\n💾 Étape 4/4 — Sauvegarde ({len(robot_files)} fichier(s) Robot)...")
            saved_paths = _save_agent_results(
                workflow    = "analyze",
                page        = page,
                screen_data = screen_data,
                llm_response = gemini_response,
                robot_files = robot_files
            )

        # ── Résultat final ─────────────────────────────────────────────────
        return {
            "success":        True,
            "workflow":       "analyze_screen",
            "page_name":      page,
            "simulation":     screen_data.get("simulation", False),
            "locator_stats":  screen_data.get("locator_stats", {}),
            "fragile_count":  len(screen_data.get("fragile_locators", [])),
            "robot_files_generated": list(robot_files.keys()),
            "saved_to":       saved_paths,
            "gemini_response": gemini_response,
        }

    async def workflow_self_healing(
        self,
        broken_locator_id: str,
        context_hint: Optional[str] = None,
        test_file: Optional[str] = None,
        auto_apply: bool = False
    ) -> dict:
        """
        WORKFLOW 2 : Self-Healing automatique d'un locator cassé.

        Étapes :
          1. Appel MCP → suggest_alternative_locators
          2. Appel Gemini → choisit le meilleur locator + code corrigé
          3. (optionnel) Validation via execute_robot_test
          4. Retour résultat + code corrigé à l'Orchestrateur

        Args:
            broken_locator_id: L'ID du locator cassé (ex: "btn_login_old")
            context_hint: Indice sur le rôle de l'élément
            test_file: Fichier de test à ré-exécuter pour validation
            auto_apply: Si True, tente d'appliquer le fix automatiquement

        Returns:
            Dict avec best_locator, corrected_code, validation_result
        """
        print("\n" + "="*60)
        print("  WORKFLOW : SELF-HEALING")
        print("="*60)
        print(f"   Locator cassé : {broken_locator_id}")
        if context_hint:
            print(f"   Contexte      : {context_hint}")

        # ── Étape 1 : Chercher les alternatives via MCP ────────────────────
        print("\n🔍 Étape 1/3 — Appel MCP: suggest_alternative_locators...")
        healing_data = await self._call_mcp_tool(
            "suggest_alternative_locators",
            {
                "broken_locator_id": broken_locator_id,
                "context_hint":      context_hint or ""
            }
        )

        if not healing_data.get("success"):
            return {
                "success": False,
                "error":   healing_data.get("error", "Échec suggest_alternative_locators"),
                "step":    "mcp_alternatives"
            }

        alternatives = healing_data.get("alternatives", [])
        print(f"   ✅ {len(alternatives)} alternative(s) trouvée(s)")
        if healing_data.get("recommendation"):
            print(f"   💡 Recommandation MCP : {healing_data['recommendation']}")

        if not alternatives:
            return {
                "success": False,
                "error":   "Aucune alternative trouvée pour ce locator",
                "broken_locator": broken_locator_id
            }

        # ── Étape 2 : Demander à Gemini de choisir + générer le fix ────────
        print("\n🤖 Étape 2/3 — Appel Gemini pour sélection et correction...")
        prompt = self._build_self_healing_prompt(
            broken_locator = broken_locator_id,
            alternatives   = alternatives,
            test_context   = f"Test file: {test_file}" if test_file else None
        )
        gemini_response = self._call_gemini(prompt)
        print("   ✅ Réponse Gemini reçue")

        # ── Étape 3 (optionnel) : Validation par ré-exécution du test ──────
        validation_result = None
        if test_file and auto_apply:
            print(f"\n🧪 Étape 3/3 — Validation : exécution de {test_file}...")
            validation_result = await self._call_mcp_tool(
                "execute_robot_test",
                {"test_file": test_file}
            )
            status = "✅ PASS" if validation_result.get("all_passed") else "❌ FAIL"
            print(f"   {status} — "
                  f"Passés: {validation_result.get('passed', 0)}, "
                  f"Échoués: {validation_result.get('failed', 0)}")
        else:
            print("\n⏭️  Étape 3/3 — Validation ignorée (auto_apply=False)")

        # ── Sauvegarde ─────────────────────────────────────────────────────
        saved_paths = _save_agent_results(
            workflow     = "self_healing",
            page         = f"locator_{broken_locator_id}",
            screen_data  = {"simulation": healing_data.get("simulation", False)},
            llm_response = gemini_response,
            robot_files  = {}
        )

        return {
            "success":           True,
            "workflow":          "self_healing",
            "broken_locator":    broken_locator_id,
            "alternatives_found": len(alternatives),
            "mcp_recommendation": healing_data.get("recommendation"),
            "gemini_analysis":   gemini_response,
            "validation":        validation_result,
            "saved_to":          saved_paths,
        }

    async def workflow_validate_test(
        self,
        test_file: str,
        test_tags: Optional[str] = None
    ) -> dict:
        """
        WORKFLOW 3 : Ré-exécution et validation d'un test Robot Framework.
        Utilisé après un self-healing pour confirmer que le fix fonctionne.

        Args:
            test_file: Chemin du fichier .robot
            test_tags: Tags à exécuter (optionnel)

        Returns:
            Dict avec passed/failed/all_passed et les logs.
        """
        print("\n" + "="*60)
        print("  WORKFLOW : VALIDATE TEST")
        print("="*60)
        print(f"   Fichier : {test_file}")
        if test_tags:
            print(f"   Tags    : {test_tags}")

        result = await self._call_mcp_tool(
            "execute_robot_test",
            {
                "test_file": test_file,
                "test_tags": test_tags or "",
            }
        )

        if result.get("success"):
            status = "✅ TOUS LES TESTS PASSENT" if result.get("all_passed") else "❌ ÉCHECS DÉTECTÉS"
            print(f"\n{status}")
            print(f"   Total   : {result.get('total', 0)}")
            print(f"   Passés  : {result.get('passed', 0)}")
            print(f"   Échoués : {result.get('failed', 0)}")
        else:
            print(f"\n❌ Erreur exécution : {result.get('error')}")

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
    Extrait les blocs de code Robot Framework de la réponse Gemini.
    Retourne un dict : nom_fichier → contenu.
    """
    blocks = {}

    # Pattern : blocs ```robot ... ``` ou ```robotframework ... ```
    pattern   = r'`{3}(?:robot|robotframework)?\n(.*?)`{3}'
    matches   = re.findall(pattern, text, re.DOTALL)
    filenames = re.findall(r'`([a-zA-Z0-9_\-]+\.robot)`', text)

    for i, content in enumerate(matches):
        content = content.strip()
        # Garder uniquement les vrais fichiers Robot Framework
        if content and ("*** " in content or "Keywords" in content):
            fname = filenames[i] if i < len(filenames) else f"generated_test_{i+1}.robot"
            blocks[fname] = content

    return blocks


def _save_agent_results(
    workflow:     str,
    page:         str,
    screen_data:  dict,
    llm_response: str,
    robot_files:  dict
) -> list[str]:
    """
    Sauvegarde les résultats de l'agent dans le dossier RESULTS_DIR.
    Retourne la liste des chemins créés.
    """
    now      = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(RESULTS_DIR) / f"{now}_{workflow}_{page}"
    out_path.mkdir(parents=True, exist_ok=True)
    saved   = []

    # 1. Réponse LLM complète
    llm_path = out_path / "llm_response.md"
    with open(llm_path, "w", encoding="utf-8") as f:
        f.write(f"# Agent Appium — Workflow: {workflow}\n")
        f.write(f"_Page: {page} | {datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n")
        f.write(llm_response)
    saved.append(str(llm_path))

    # 2. Contexte écran (sans screenshot pour la taille)
    ctx_export = {k: v for k, v in screen_data.items() if k != "screenshot"}
    ctx_path   = out_path / "screen_context.json"
    with open(ctx_path, "w", encoding="utf-8") as f:
        json.dump(ctx_export, f, indent=2, ensure_ascii=False)
    saved.append(str(ctx_path))

    # 3. Fichiers Robot Framework générés
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
    parser = argparse.ArgumentParser(
        description="Appium Agent — MyBiat Test Automation"
    )
    parser.add_argument(
        "--workflow",
        choices=["analyze", "self-healing", "validate"],
        default="analyze",
        help="Workflow à exécuter (défaut: analyze)"
    )
    parser.add_argument(
        "--locator",
        type=str,
        default=None,
        help="[self-healing] ID du locator cassé (ex: btn_login_old)"
    )
    parser.add_argument(
        "--context",
        type=str,
        default=None,
        help="[self-healing] Indice sur le rôle de l'élément"
    )
    parser.add_argument(
        "--test-file",
        type=str,
        default=None,
        help="[validate / self-healing] Chemin du fichier .robot"
    )
    parser.add_argument(
        "--tags",
        type=str,
        default=None,
        help="[validate] Tags Robot Framework à exécuter"
    )
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="[analyze] Ne pas inclure le screenshot dans le prompt"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Ne pas sauvegarder les résultats"
    )
    parser.add_argument(
        "--auto-apply",
        action="store_true",
        help="[self-healing] Appliquer et valider le fix automatiquement"
    )

    args  = parser.parse_args()
    agent = AppiumAgent()

    # ── Lancer le bon workflow ─────────────────────────────────────────────
    if args.workflow == "analyze":
        result = await agent.workflow_analyze_screen(
            include_screenshot = not args.no_screenshot,
            save_results       = not args.no_save
        )

    elif args.workflow == "self-healing":
        if not args.locator:
            print("❌ --locator requis pour le workflow self-healing")
            print("   Exemple : --locator btn_login_old --context 'bouton connexion'")
            return
        result = await agent.workflow_self_healing(
            broken_locator_id = args.locator,
            context_hint      = args.context,
            test_file         = args.test_file,
            auto_apply        = args.auto_apply
        )

    elif args.workflow == "validate":
        if not args.test_file:
            print("❌ --test-file requis pour le workflow validate")
            print("   Exemple : --test-file tests/login_test.robot")
            return
        result = await agent.workflow_validate_test(
            test_file = args.test_file,
            test_tags = args.tags
        )

    # ── Affichage du résumé final ──────────────────────────────────────────
    print("\n" + "="*60)
    print("  RÉSULTAT FINAL")
    print("="*60)
    print(json.dumps(
        {k: v for k, v in result.items() if k != "gemini_response"},
        indent=2,
        ensure_ascii=False,
        default=str
    ))


if __name__ == "__main__":
    asyncio.run(main())
