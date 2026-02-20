"""
Agent Test Generator - MyBiat AI Testing
=========================================
Genere automatiquement des tests Robot Framework (pattern POM)
a partir du contexte UI fourni par les MCP Servers GitLab et Appium.

SDK : google-genai (nouveau, remplace google-generativeai)
Modele : gemini-2.5-flash (configurable via GEMINI_MODEL dans .env)

Usage:
    from agents.test_generator_agent import TestGeneratorAgent

    agent = TestGeneratorAgent()
    result = agent.generate_from_ui_elements(elements, screen_name="LoginScreen")
    result = agent.generate_from_mr_changes(mr_analysis)
    result = agent.generate_from_appium_hierarchy(hierarchy)
"""

import os
import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Chargement .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    _loaded = False
    for _d in _root.iterdir():
        if _d.is_dir() and "config" in _d.name.lower():
            _env = _d / ".env"
            if _env.exists():
                load_dotenv(_env)
                _loaded = True
                break
    if not _loaded:
        load_dotenv(_root / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Nouveau SDK google-genai
# ---------------------------------------------------------------------------
try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    raise ImportError(
        "SDK manquant. Lancez :\n"
        "  pip uninstall google-generativeai -y\n"
        "  pip install google-genai"
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
APP_PACKAGE    = os.getenv("APP_PACKAGE", "com.example.mobile_app")

# Client global (instancie une seule fois)
_client: Optional[genai.Client] = None
if GEMINI_API_KEY:
    _client = genai.Client(api_key=GEMINI_API_KEY)
else:
    print("GEMINI_API_KEY manquant dans le .env")


# ---------------------------------------------------------------------------
# Dataclass resultat
# ---------------------------------------------------------------------------

@dataclass
class GeneratedTest:
    """Resultat de generation : un POM + un fichier de test."""
    screen_name:      str
    page_object_file: str   # contenu du fichier POM .robot
    test_file:        str   # contenu du fichier de test .robot
    page_object_path: str   # chemin suggere (ex: resources/pages/LoginPage.robot)
    test_path:        str   # chemin suggere (ex: tests/mobile/test_login.robot)
    elements_used:    list
    generation_notes: str


# ---------------------------------------------------------------------------
# Few-shot examples - style du projet
# ---------------------------------------------------------------------------

FEW_SHOT_PAGE_OBJECT = """
*** Settings ***
Library    AppiumLibrary

*** Variables ***
${LOCATOR_USERNAME}    id=com.example.mobile_app:id/edit_username
${LOCATOR_PASSWORD}    id=com.example.mobile_app:id/edit_password
${LOCATOR_BTN_LOGIN}   id=com.example.mobile_app:id/btn_login
${LOCATOR_TV_TITLE}    id=com.example.mobile_app:id/tv_title

*** Keywords ***
Open Login Screen
    [Documentation]    Lance l'application et attend l'ecran de connexion
    Wait Until Element Is Visible    ${LOCATOR_TV_TITLE}    timeout=15s

Enter Username
    [Arguments]    ${username}
    [Documentation]    Saisit l'identifiant dans le champ utilisateur
    Clear Element Text    ${LOCATOR_USERNAME}
    Input Text            ${LOCATOR_USERNAME}    ${username}

Enter Password
    [Arguments]    ${password}
    [Documentation]    Saisit le mot de passe (masque)
    Clear Element Text    ${LOCATOR_PASSWORD}
    Input Text            ${LOCATOR_PASSWORD}    ${password}

Click Login Button
    [Documentation]    Clique sur le bouton Se connecter
    Click Element    ${LOCATOR_BTN_LOGIN}

Login With Credentials
    [Arguments]    ${username}    ${password}
    [Documentation]    Keyword composite : saisie complete + soumission
    Enter Username    ${username}
    Enter Password    ${password}
    Click Login Button
"""

FEW_SHOT_TEST_FILE = """
*** Settings ***
Library           AppiumLibrary
Resource          ../../resources/pages/LoginPage.robot
Suite Setup       Open Application    http://localhost:4723
...               platformName=Android
...               deviceName=82403e660602
...               platformVersion=12
...               appPackage=com.example.mobile_app
...               appActivity=.MainActivity
...               noReset=True
Suite Teardown    Close Application
Test Teardown     Capture Page Screenshot

*** Variables ***
${VALID_USER}        usertest@biat.com.tn
${VALID_PASSWORD}    Test@1234

*** Test Cases ***
TC_LOGIN_001 - Connexion reussie avec identifiants valides
    [Documentation]    Verifie la connexion avec des identifiants corrects
    [Tags]    login    smoke    regression
    Open Login Screen
    Login With Credentials    ${VALID_USER}    ${VALID_PASSWORD}
    Wait Until Element Is Visible    id=com.example.mobile_app:id/dashboard_root    timeout=10s

TC_LOGIN_002 - Message d'erreur avec mot de passe incorrect
    [Documentation]    Verifie l'affichage d'une erreur pour un mauvais mot de passe
    [Tags]    login    negative
    Open Login Screen
    Login With Credentials    ${VALID_USER}    wrong_password
    Element Should Be Visible    id=com.example.mobile_app:id/tv_error_message
"""

# ---------------------------------------------------------------------------
# Prompts systeme
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_POM = f"""Tu es un expert en automatisation de tests mobiles Android avec Robot Framework et Appium.
Tu generes des fichiers Robot Framework selon le pattern Page Object Model (POM) strict.

CONVENTIONS OBLIGATOIRES :
1. Structure POM : fichier Page Object (resources/pages/) SEPARE du fichier de test (tests/mobile/)
2. Locators : toujours utiliser id=PACKAGE:id/ELEMENT_ID -- package = {APP_PACKAGE}
3. Keywords : noms en anglais, verbeux, avec [Documentation] sur chaque keyword
4. Variables : prefixe ${{LOCATOR_}} pour les locators, ${{VALID_}} pour les donnees de test
5. Tags : toujours inclure [Tags] avec le module + type (smoke/regression/negative)
6. Suite Setup : configurer AppiumLibrary avec les capabilities du device
7. Timeouts : timeout=15s pour Wait Until, timeout=10s pour les elements post-action
8. Data-driven : utiliser [Template] pour les tests parametres quand applicable

FORMAT DE REPONSE :
Reponds UNIQUEMENT en JSON valide avec cette structure exacte :
{{
  "page_object_content": "contenu complet du fichier POM .robot",
  "test_file_content": "contenu complet du fichier de test .robot",
  "page_object_filename": "NomPage.robot",
  "test_filename": "test_nom_module.robot",
  "generation_notes": "explication des choix faits"
}}
Ne mets RIEN avant ni apres le JSON. Pas de markdown, pas de backticks.
"""

SYSTEM_PROMPT_ANALYZE = """Tu es un analyste expert en tests mobiles.
A partir d'une hierarchie UI Android, identifie :
- L'ecran courant (nom probable)
- Tous les elements interactifs avec leur role fonctionnel
- Les scenarios de test prioritaires (positif, negatif, validation)

Reponds UNIQUEMENT en JSON :
{
  "screen_name": "nom de l'ecran",
  "screen_purpose": "description courte",
  "interactive_elements": [
    {"id": "resource_id", "type": "Button|EditText|...", "role": "role fonctionnel", "priority": "high|medium|low"}
  ],
  "suggested_test_scenarios": [
    {"name": "TC_NOM_001", "type": "positive|negative|validation", "description": "description"}
  ]
}
"""


# ---------------------------------------------------------------------------
# Agent principal
# ---------------------------------------------------------------------------

class TestGeneratorAgent:
    """
    Agent IA pour la generation automatique de tests Robot Framework (POM).

    Methodes principales :
        generate_from_ui_elements()      -> depuis une liste d'elements UI
        generate_from_mr_changes()       -> depuis l'analyse d'une Merge Request
        generate_from_appium_hierarchy() -> depuis la hierarchie Appium brute
        analyze_screen()                 -> analyse uniquement, sans generation
    """

    def __init__(self, model_name: str = GEMINI_MODEL):
        self.model_name  = model_name
        self.app_package = APP_PACKAGE
        self._client     = _client  # reutilise le client global

    def _get_client(self) -> genai.Client:
        """Retourne le client Gemini, leve une erreur si non configure."""
        if not self._client:
            raise RuntimeError(
                "GEMINI_API_KEY manquant. Ajoutez-le dans config/.env"
            )
        return self._client

    # -----------------------------------------------------------------------
    # Methode 1 : Generation depuis elements UI explicites
    # -----------------------------------------------------------------------

    def generate_from_ui_elements(
        self,
        elements: list,
        screen_name: str,
        existing_tests_context: Optional[str] = None
    ) -> GeneratedTest:
        """
        Genere un POM + test Robot Framework depuis une liste d'elements UI.

        Args:
            elements:    Liste de dicts {resource_id, text, content_desc, class, clickable}
            screen_name: Nom logique de l'ecran (ex: "LoginScreen", "TransferScreen")
            existing_tests_context: Extrait de tests existants pour respecter le style

        Returns:
            GeneratedTest avec les deux fichiers prets a ecrire sur disque
        """
        elements_summary = self._format_elements(elements)

        prompt = f"""
## Contexte du projet
Application : MyBiat (application bancaire mobile Android)
Package : {self.app_package}
Device : Android 12, appActivity=.MainActivity

## Ecran a tester
Nom de l'ecran : {screen_name}

## Elements UI detectes sur cet ecran
{elements_summary}

## Exemple de style POM existant dans le projet
### Page Object type :
{FEW_SHOT_PAGE_OBJECT}

### Fichier de test type :
{FEW_SHOT_TEST_FILE}

{f"## Tests existants dans le projet (pour respecter le style) :{chr(10)}{existing_tests_context}" if existing_tests_context else ""}

## Tache
Genere un Page Object complet et un fichier de test complet pour l'ecran "{screen_name}".
- Couvre les scenarios positifs ET negatifs
- Utilise [Template] si plusieurs cas similaires
- Inclus au moins 3 cas de test
- Genere les cas edge case si pertinents (champs vides, caracteres speciaux, etc.)
"""
        return self._call_gemini_and_parse(prompt, screen_name, elements)

    # -----------------------------------------------------------------------
    # Methode 2 : Generation depuis l'analyse d'une MR GitLab
    # -----------------------------------------------------------------------

    def generate_from_mr_changes(self, mr_analysis: dict) -> GeneratedTest:
        """
        Genere des tests bases sur l'analyse des changements d'une Merge Request.

        Args:
            mr_analysis: Resultat de analyze_mr_for_ui_changes() du MCP GitLab Server

        Returns:
            GeneratedTest avec les fichiers generes
        """
        new_elements = mr_analysis.get("ui_changes", {}).get("new_ui_elements", [])
        mod_elements = mr_analysis.get("ui_changes", {}).get("modified_ui_elements", [])
        activities   = mr_analysis.get("ui_changes", {}).get("activities_changed", [])
        mr_title     = mr_analysis.get("mr_title", "Unknown MR")
        xml_files    = mr_analysis.get("ui_changes", {}).get("xml_files_modified", [])

        screen_name = self._infer_screen_name(xml_files, activities, mr_title)

        elements = []
        for elem in new_elements + mod_elements:
            elements.append({
                "resource_id": f"{self.app_package}:id/{elem.get('id', 'unknown')}",
                "text":        elem.get("text", ""),
                "class":       self._elem_type_to_class(elem.get("type", "")),
                "clickable":   elem.get("type") in ("button", "checkbox", "switch"),
                "is_new":      elem in new_elements
            })

        prompt = f"""
## Contexte
Application : MyBiat (bancaire Android)
Package : {self.app_package}
Merge Request : "{mr_title}"

## Changements UI detectes dans la MR
Fichiers XML modifies : {', '.join(xml_files) if xml_files else 'Aucun'}
Ecrans/Activities modifies : {json.dumps(activities, indent=2)}

## Nouveaux elements UI (a couvrir en priorite)
{self._format_elements([e for e in elements if e.get("is_new")])}

## Elements modifies (verifier regression)
{self._format_elements([e for e in elements if not e.get("is_new")])}

## Style POM de reference
{FEW_SHOT_PAGE_OBJECT}

## Tache
1. Genere les tests pour les NOUVEAUX elements (nouveaux keywords + nouveaux TCs)
2. Genere les tests de regression pour les elements MODIFIES
3. Nomme le fichier POM d'apres l'ecran : {screen_name}Page.robot
4. Inclus des commentaires # NEW - MR: {mr_title} sur les nouveaux elements
"""
        return self._call_gemini_and_parse(prompt, screen_name, elements)

    # -----------------------------------------------------------------------
    # Methode 3 : Generation depuis hierarchie Appium brute
    # -----------------------------------------------------------------------

    def generate_from_appium_hierarchy(
        self,
        hierarchy: dict,
        screen_name: Optional[str] = None
    ) -> GeneratedTest:
        """
        Genere des tests depuis la hierarchie UI retournee par get_ui_hierarchy(flatten=True).

        Args:
            hierarchy:   Resultat de get_ui_hierarchy() du MCP Appium Server
            screen_name: Nom optionnel (auto-detecte si None)

        Returns:
            GeneratedTest avec les fichiers generes
        """
        elements = hierarchy.get("elements", [])
        if not screen_name:
            screen_name = self._detect_screen_from_elements(elements)
        return self.generate_from_ui_elements(elements, screen_name)

    # -----------------------------------------------------------------------
    # Methode 4 : Analyse seule (sans generation)
    # -----------------------------------------------------------------------

    def analyze_screen(self, elements: list) -> dict:
        """
        Analyse les elements UI et retourne un rapport structure
        sans generer de code de test.
        """
        if not GEMINI_API_KEY:
            return {"success": False, "error": "GEMINI_API_KEY manquant"}

        client = self._get_client()
        prompt = f"Analyse ces elements UI Android (package: {self.app_package}) :\n\n{self._format_elements(elements)}"

        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT_ANALYZE,
                    temperature=0.1,
                    max_output_tokens=2048,
                ),
            )
            raw = response.text.strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            return {"success": True, "analysis": json.loads(raw)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -----------------------------------------------------------------------
    # Methode utilitaire : ecrire les fichiers sur disque
    # -----------------------------------------------------------------------

    def save_generated_test(
        self,
        generated: GeneratedTest,
        output_base_dir: str = "."
    ) -> dict:
        """
        Ecrit les fichiers generes sur disque selon la structure POM.

        Structure creee :
            output_base_dir/
              resources/pages/{NomPage}.robot
              tests/mobile/{test_nom_module}.robot
        """
        base      = Path(output_base_dir)
        pom_path  = base / "resources" / "pages" / generated.page_object_path.split("/")[-1]
        test_path = base / "tests"     / "mobile" / generated.test_path.split("/")[-1]

        pom_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.parent.mkdir(parents=True, exist_ok=True)

        pom_path.write_text(generated.page_object_file,  encoding="utf-8")
        test_path.write_text(generated.test_file,         encoding="utf-8")

        return {
            "success":           True,
            "page_object_saved": str(pom_path),
            "test_saved":        str(test_path),
            "screen_name":       generated.screen_name,
            "notes":             generated.generation_notes,
        }

    # -----------------------------------------------------------------------
    # Helpers prives
    # -----------------------------------------------------------------------

    def _call_gemini_and_parse(
        self,
        prompt: str,
        screen_name: str,
        elements: list
    ) -> GeneratedTest:
        """Appelle Gemini (nouveau SDK) et parse la reponse JSON."""
        client = self._get_client()

        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT_POM,
                    temperature=0.2,
                    max_output_tokens=8192,
                ),
            )
            raw = response.text.strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)

            return GeneratedTest(
                screen_name=screen_name,
                page_object_file=data.get("page_object_content", ""),
                test_file=data.get("test_file_content", ""),
                page_object_path=f"resources/pages/{data.get('page_object_filename', f'{screen_name}Page.robot')}",
                test_path=f"tests/mobile/{data.get('test_filename', f'test_{screen_name.lower()}.robot')}",
                elements_used=elements,
                generation_notes=data.get("generation_notes", ""),
            )

        except json.JSONDecodeError as e:
            return GeneratedTest(
                screen_name=screen_name,
                page_object_file=f"# ERREUR PARSING JSON: {e}\n# Reponse brute:\n{raw[:2000]}",
                test_file="",
                page_object_path=f"resources/pages/{screen_name}Page.robot",
                test_path=f"tests/mobile/test_{screen_name.lower()}.robot",
                elements_used=elements,
                generation_notes=f"Erreur parsing: {e}",
            )
        except Exception as e:
            return GeneratedTest(
                screen_name=screen_name,
                page_object_file=f"# ERREUR GEMINI: {e}",
                test_file="",
                page_object_path=f"resources/pages/{screen_name}Page.robot",
                test_path=f"tests/mobile/test_{screen_name.lower()}.robot",
                elements_used=elements,
                generation_notes=f"Erreur: {e}",
            )

    def _format_elements(self, elements: list) -> str:
        """Formate les elements en texte lisible pour le prompt."""
        if not elements:
            return "Aucun element fourni."
        lines = []
        for i, elem in enumerate(elements, 1):
            rid   = elem.get("resource_id", "")
            text  = elem.get("text", "")
            desc  = elem.get("content_desc", "")
            cls   = elem.get("class", "").split(".")[-1]
            click = "cliquable" if elem.get("clickable") else ""
            new   = "NOUVEAU"   if elem.get("is_new")   else ""
            lines.append(
                f"  {i}. [{cls}] id={rid!r}  text={text!r}  desc={desc!r}  {click} {new}"
            )
        return "\n".join(lines)

    def _infer_screen_name(self, xml_files: list, activities: list, mr_title: str) -> str:
        """Deduit le nom de l'ecran depuis les fichiers modifies."""
        for f in xml_files:
            name = Path(f).stem
            for kw in ("activity_", "fragment_", "layout_"):
                if name.startswith(kw):
                    name = name[len(kw):]
                    break
            return "".join(w.capitalize() for w in name.split("_")) + "Screen"

        for act in activities:
            fname = Path(act.get("file", "")).stem
            if fname:
                return fname

        words = re.findall(r"\b[A-Za-z]+\b", mr_title)[:3]
        return "".join(w.capitalize() for w in words) + "Screen"

    def _detect_screen_from_elements(self, elements: list) -> str:
        """Auto-detecte le nom de l'ecran depuis les elements UI."""
        for elem in elements:
            rid = elem.get("resource_id", "")
            for kw in ("tv_title", "tv_header", "toolbar_title", "screen_title"):
                if kw in rid:
                    text = elem.get("text", "")
                    if text:
                        return "".join(w.capitalize() for w in text.split()[:2]) + "Screen"

        all_ids = " ".join(elem.get("resource_id", "") for elem in elements)
        for keyword, screen in [
            ("login",     "LoginScreen"),
            ("transfer",  "TransferScreen"),
            ("account",   "AccountScreen"),
            ("payment",   "PaymentScreen"),
            ("profile",   "ProfileScreen"),
            ("home",      "HomeScreen"),
            ("dashboard", "DashboardScreen"),
            ("register",  "RegisterScreen"),
        ]:
            if keyword in all_ids.lower():
                return screen
        return "UnknownScreen"

    @staticmethod
    def _elem_type_to_class(elem_type: str) -> str:
        """Convertit un type MR (button, edittext...) en classe Android."""
        mapping = {
            "button":       "android.widget.Button",
            "edittext":     "android.widget.EditText",
            "textview":     "android.widget.TextView",
            "imageview":    "android.widget.ImageView",
            "recyclerview": "androidx.recyclerview.widget.RecyclerView",
            "checkbox":     "android.widget.CheckBox",
            "switch":       "android.widget.Switch",
        }
        return mapping.get(elem_type.lower(), f"android.widget.{elem_type.capitalize()}")


# ---------------------------------------------------------------------------
# CLI rapide - test direct sans orchestrateur
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("\n" + "=" * 60)
    print("TEST GENERATOR AGENT - MODE TEST DIRECT")
    print(f"Modele : {GEMINI_MODEL}")
    print("=" * 60)

    if not GEMINI_API_KEY:
        print("\nGEMINI_API_KEY manquant - ajoutez-le dans config/.env")
        sys.exit(1)

    # Elements UI simules (comme ceux retournes par Appium MCP Server)
    mock_elements = [
        {"resource_id": f"{APP_PACKAGE}:id/tv_title",           "text": "Nouveau Virement",        "class": "android.widget.TextView",  "content_desc": "",                  "clickable": False},
        {"resource_id": f"{APP_PACKAGE}:id/edit_amount",        "text": "",                         "class": "android.widget.EditText",  "content_desc": "Montant du virement","clickable": True},
        {"resource_id": f"{APP_PACKAGE}:id/edit_beneficiary",   "text": "",                         "class": "android.widget.EditText",  "content_desc": "RIB du beneficiaire","clickable": True},
        {"resource_id": f"{APP_PACKAGE}:id/spinner_account",    "text": "Choisir compte debiteur",  "class": "android.widget.Spinner",   "content_desc": "Compte source",      "clickable": True},
        {"resource_id": f"{APP_PACKAGE}:id/btn_confirm_transfer","text": "Confirmer le virement",   "class": "android.widget.Button",    "content_desc": "",                  "clickable": True},
    ]

    agent = TestGeneratorAgent()
    print(f"\nGeneration pour l'ecran : TransferScreen ({len(mock_elements)} elements)")

    result = agent.generate_from_ui_elements(mock_elements, "TransferScreen")

    print(f"\nGENERATION TERMINEE")
    print(f"  Screen   : {result.screen_name}")
    print(f"  POM      : {result.page_object_path}")
    print(f"  Test     : {result.test_path}")
    print(f"  Notes    : {result.generation_notes[:200]}")
    print("\n--- PAGE OBJECT (extrait) ---")
    print(result.page_object_file[:800])
    print("\n--- TEST FILE (extrait) ---")
    print(result.test_file[:800])

    save_result = agent.save_generated_test(result, output_base_dir="generated_tests")
    print(f"\nFichiers sauvegardes : {save_result}")
    print("=" * 60)