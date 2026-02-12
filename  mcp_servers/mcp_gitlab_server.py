"""
MCP GitLab Server for MyBiat Test Automation
Expose GitLab context (MRs, diffs, XML files) to AI agents via MCP Protocol
VERSION CORRIGÉE - Gère correctement les attributs des MRs
"""

import os
import re
from typing import Any, Optional
import gitlab
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("GitLab Context Server")

# GitLab configuration
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

# Initialize GitLab client
gl = gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)


@mcp.tool()
def get_merge_requests(state: str = "opened", max_results: int = 10) -> dict[str, Any]:
    """
    Liste les Merge Requests actives du projet.

    Args:
        state: État des MRs ('opened', 'closed', 'merged', 'all')
        max_results: Nombre maximum de résultats à retourner

    Returns:
        Dict contenant la liste des MRs avec leurs métadonnées
    """
    try:
        project = gl.projects.get(PROJECT_ID)
        merge_requests = project.mergerequests.list(state=state, per_page=max_results)

        mrs_data = []
        for mr in merge_requests:
            # CORRECTION: Faire un get() pour avoir tous les attributs
            mr_full = project.mergerequests.get(mr.iid)

            mrs_data.append({
                "id": mr_full.iid,
                "title": mr_full.title,
                "description": mr_full.description,
                "state": mr_full.state,
                "author": mr_full.author.get("name"),
                "source_branch": mr_full.source_branch,
                "target_branch": mr_full.target_branch,
                "created_at": mr_full.created_at,
                "updated_at": mr_full.updated_at,
                "web_url": mr_full.web_url,
                "has_conflicts": mr_full.has_conflicts,
                "changes_count": getattr(mr_full, 'changes_count', 'N/A')  # Utiliser getattr pour éviter l'erreur
            })

        return {
            "success": True,
            "count": len(mrs_data),
            "merge_requests": mrs_data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "merge_requests": []
        }


@mcp.tool()
def get_mr_changes(mr_iid: int) -> dict[str, Any]:
    """
    Récupère les changements (diffs) d'une Merge Request spécifique.

    Args:
        mr_iid: ID de la Merge Request

    Returns:
        Dict contenant tous les fichiers modifiés avec leurs diffs
    """
    try:
        project = gl.projects.get(PROJECT_ID)
        mr = project.mergerequests.get(mr_iid)
        changes = mr.changes()

        files_changed = []
        for change in changes.get("changes", []):
            files_changed.append({
                "old_path": change.get("old_path"),
                "new_path": change.get("new_path"),
                "new_file": change.get("new_file"),
                "renamed_file": change.get("renamed_file"),
                "deleted_file": change.get("deleted_file"),
                "diff": change.get("diff")
            })

        return {
            "success": True,
            "mr_id": mr_iid,
            "mr_title": mr.title,
            "files_count": len(files_changed),
            "changes": files_changed
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "changes": []
        }


@mcp.tool()
def get_file_content(file_path: str, ref: str = "main") -> dict[str, Any]:
    """
    Lit le contenu d'un fichier spécifique depuis GitLab.

    Args:
        file_path: Chemin du fichier dans le repository
        ref: Branch ou commit SHA (default: 'main')

    Returns:
        Dict contenant le contenu du fichier
    """
    try:
        project = gl.projects.get(PROJECT_ID)
        file_content = project.files.get(file_path=file_path, ref=ref)

        # Decode content (GitLab returns base64 encoded content)
        import base64
        decoded_content = base64.b64decode(file_content.content).decode('utf-8')

        return {
            "success": True,
            "file_path": file_path,
            "ref": ref,
            "content": decoded_content,
            "size": file_content.size,
            "encoding": file_content.encoding
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": None
        }


@mcp.tool()
def analyze_mr_for_ui_changes(mr_iid: int) -> dict[str, Any]:
    """
    Analyse une MR pour détecter les changements UI (fichiers XML Android).
    Identifie les nouveaux boutons, champs, activités modifiées.

    Args:
        mr_iid: ID de la Merge Request

    Returns:
        Dict contenant l'analyse des changements UI détectés
    """
    try:
        project = gl.projects.get(PROJECT_ID)
        mr = project.mergerequests.get(mr_iid)
        changes = mr.changes()

        ui_changes = {
            "xml_files_modified": [],
            "new_ui_elements": [],
            "modified_ui_elements": [],
            "activities_changed": []
        }

        for change in changes.get("changes", []):
            file_path = change.get("new_path")
            diff = change.get("diff", "")

            # Détecter les fichiers XML de layout
            if file_path and file_path.endswith('.xml') and '/layout/' in file_path:
                ui_changes["xml_files_modified"].append(file_path)

                # Analyser le diff pour trouver les nouveaux éléments
                new_elements = _extract_ui_elements_from_diff(diff, added=True)
                modified_elements = _extract_ui_elements_from_diff(diff, added=False)

                ui_changes["new_ui_elements"].extend(new_elements)
                ui_changes["modified_ui_elements"].extend(modified_elements)

            # Détecter les fichiers Activity/Fragment modifiés
            if file_path and (file_path.endswith('Activity.java') or
                            file_path.endswith('Activity.kt') or
                            file_path.endswith('Fragment.java') or
                            file_path.endswith('Fragment.kt')):
                ui_changes["activities_changed"].append({
                    "file": file_path,
                    "type": "activity" if "Activity" in file_path else "fragment"
                })

        return {
            "success": True,
            "mr_id": mr_iid,
            "mr_title": mr.title,
            "has_ui_changes": len(ui_changes["xml_files_modified"]) > 0,
            "ui_changes": ui_changes,
            "recommendation": _generate_test_recommendation(ui_changes)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ui_changes": None
        }


def _extract_ui_elements_from_diff(diff: str, added: bool = True) -> list[dict]:
    """
    Extrait les éléments UI (Button, EditText, etc.) d'un diff XML.

    Args:
        diff: Le contenu du diff
        added: Si True, cherche les lignes ajoutées (+), sinon les modifiées

    Returns:
        Liste des éléments UI trouvés
    """
    elements = []
    prefix = "+" if added else "-"

    # Patterns pour détecter les éléments Android courants
    patterns = {
        "button": r'<(Button|androidx\.appcompat\.widget\.AppCompatButton)',
        "edittext": r'<(EditText|androidx\.appcompat\.widget\.AppCompatEditText)',
        "textview": r'<(TextView|androidx\.appcompat\.widget\.AppCompatTextView)',
        "imageview": r'<(ImageView|androidx\.appcompat\.widget\.AppCompatImageView)',
        "recyclerview": r'<(RecyclerView|androidx\.recyclerview\.widget\.RecyclerView)',
        "checkbox": r'<(CheckBox|androidx\.appcompat\.widget\.AppCompatCheckBox)',
        "switch": r'<(Switch|androidx\.appcompat\.widget\.SwitchCompat)'
    }

    for line in diff.split('\n'):
        if line.startswith(prefix):
            for element_type, pattern in patterns.items():
                if re.search(pattern, line):
                    # Extraire l'ID si présent
                    id_match = re.search(r'android:id="@\+id/([^"]+)"', line)
                    element_id = id_match.group(1) if id_match else "no_id"

                    # Extraire le text si présent
                    text_match = re.search(r'android:text="([^"]+)"', line)
                    text = text_match.group(1) if text_match else ""

                    elements.append({
                        "type": element_type,
                        "id": element_id,
                        "text": text,
                        "raw_line": line.strip()
                    })
                    break

    return elements


def _generate_test_recommendation(ui_changes: dict) -> str:
    """
    Génère une recommandation pour les tests à créer/mettre à jour.

    Args:
        ui_changes: Dict contenant les changements UI détectés

    Returns:
        Recommandation sous forme de texte
    """
    recommendations = []

    if ui_changes["new_ui_elements"]:
        new_buttons = [e for e in ui_changes["new_ui_elements"] if e["type"] == "button"]
        new_inputs = [e for e in ui_changes["new_ui_elements"] if e["type"] == "edittext"]
        new_checkboxes = [e for e in ui_changes["new_ui_elements"] if e["type"] == "checkbox"]

        if new_buttons:
            recommendations.append(
                f"✓ {len(new_buttons)} nouveaux boutons détectés → Créer tests de clic"
            )
        if new_inputs:
            recommendations.append(
                f"✓ {len(new_inputs)} nouveaux champs détectés → Créer tests de saisie/validation"
            )
        if new_checkboxes:
            recommendations.append(
                f"✓ {len(new_checkboxes)} nouveaux checkbox détectés → Créer tests de sélection"
            )

    if ui_changes["modified_ui_elements"]:
        recommendations.append(
            f"⚠ {len(ui_changes['modified_ui_elements'])} éléments modifiés → Vérifier les tests existants"
        )

    if ui_changes["activities_changed"]:
        recommendations.append(
            f"📱 {len(ui_changes['activities_changed'])} écrans modifiés → Vérifier les Page Objects"
        )

    if not recommendations:
        return "Aucun changement UI majeur détecté"

    return "\n".join(recommendations)


@mcp.tool()
def get_test_files(directory: str = "tests/mobile") -> dict[str, Any]:
    """
    Liste tous les fichiers de test Robot Framework dans un répertoire.

    Args:
        directory: Chemin du répertoire contenant les tests

    Returns:
        Dict contenant la liste des fichiers de test
    """
    try:
        project = gl.projects.get(PROJECT_ID)

        # Récupérer l'arborescence du répertoire
        items = project.repository_tree(path=directory, recursive=True, all=True)

        test_files = []
        for item in items:
            if item['type'] == 'blob' and item['name'].endswith('.robot'):
                test_files.append({
                    "path": item['path'],
                    "name": item['name'],
                    "id": item['id']
                })

        return {
            "success": True,
            "directory": directory,
            "count": len(test_files),
            "test_files": test_files
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "test_files": []
        }


@mcp.tool()
def search_locator_in_tests(locator_id: str) -> dict[str, Any]:
    """
    Recherche un locator Android dans tous les tests pour évaluer l'impact.
    Utile pour le self-healing quand un locator change.

    Args:
        locator_id: ID du locator Android (ex: "btn_login")

    Returns:
        Dict contenant les fichiers de test utilisant ce locator
    """
    try:
        project = gl.projects.get(PROJECT_ID)

        # Rechercher dans le repository
        search_results = project.search('blobs', locator_id, per_page=50)

        affected_tests = []
        for result in search_results:
            if result['filename'].endswith('.robot'):
                affected_tests.append({
                    "file": result['path'],
                    "filename": result['filename'],
                    "ref": result['ref']
                })

        return {
            "success": True,
            "locator_id": locator_id,
            "affected_tests_count": len(affected_tests),
            "affected_tests": affected_tests
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "affected_tests": []
        }


if __name__ == "__main__":
    # Vérifier que les variables d'environnement sont configurées
    if not GITLAB_TOKEN:
        print("❌ GITLAB_TOKEN n'est pas configuré!")
        print("Exportez votre token: export GITLAB_TOKEN='your-token'")
        exit(1)

    if not PROJECT_ID:
        print("❌ GITLAB_PROJECT_ID n'est pas configuré!")
        print("Exportez l'ID du projet: export GITLAB_PROJECT_ID='12345'")
        exit(1)

    print("✅ MCP GitLab Server démarré")
    print(f"📊 Projet: {PROJECT_ID}")
    print(f"🔗 URL: {GITLAB_URL}")

    # Démarrer le serveur MCP
    mcp.run()