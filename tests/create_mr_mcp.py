"""
Script pour créer une Merge Request de test dans GitLab
Simule des changements UI Android pour tester le MCP Server
VERSION FINALE - Gère l'espace invisible dans le nom du dossier
"""

import os
import sys
import gitlab
from dotenv import load_dotenv
from pathlib import Path

# ============================================================================
# CHARGER LES VARIABLES D'ENVIRONNEMENT (avec gestion de l'espace invisible)
# ============================================================================

print("🔧 Chargement de la configuration...")
project_root = Path(__file__).resolve().parent.parent

print(f"📁 Répertoire du projet: {project_root}")

# Chercher TOUS les dossiers pour debug
print(f"\n📂 Recherche du dossier config...")
config_dir = None

for item in project_root.iterdir():
    if item.is_dir():
        # Afficher tous les dossiers avec leur nom exact (pour voir les espaces)
        print(f"  Examen: '{item.name}' → {item}")

        # Chercher "config" de manière flexible (ignore espaces et casse)
        if "config" in item.name.lower().strip():
            config_dir = item
            print(f"\n✅ Dossier config trouvé: '{item.name}'")
            break

# Si pas trouvé avec la méthode flexible, essayer avec l'espace exact
if config_dir is None:
    # Essayer avec un espace au début
    config_with_space = project_root / " config"
    if config_with_space.exists():
        config_dir = config_with_space
        print(f"\n✅ Dossier config trouvé (avec espace): {config_dir}")

# Charger le .env
env_loaded = False

if config_dir:
    env_path = config_dir / ".env"
    if env_path.exists():
        print(f"✅ Fichier .env trouvé: {env_path}")
        load_dotenv(env_path)
        env_loaded = True
        print(f"✅ Variables chargées depuis: {env_path}")
    else:
        print(f"⚠️ Fichier .env introuvable dans {config_dir}")

# Essayer aussi à la racine
if not env_loaded:
    print("⚠️ Tentative de chargement depuis la racine...")
    env_root = project_root / ".env"
    if env_root.exists():
        load_dotenv(env_root)
        env_loaded = True
        print(f"✅ Variables chargées depuis la racine: {env_root}")
    else:
        load_dotenv()  # Dernière tentative avec variables système

# Configuration GitLab
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

# Afficher les variables chargées (sans le token complet)
print(f"\n📊 Variables d'environnement:")
print(f"  • GITLAB_URL: {GITLAB_URL if GITLAB_URL else '❌ NON DÉFINIE'}")
print(f"  • GITLAB_TOKEN: {'✅ Défini (' + GITLAB_TOKEN[:15] + '...)' if GITLAB_TOKEN else '❌ NON DÉFINI'}")
print(f"  • GITLAB_PROJECT_ID: {PROJECT_ID if PROJECT_ID else '❌ NON DÉFINI'}")

# Vérifications
if not GITLAB_TOKEN:
    print("\n❌ GITLAB_TOKEN manquant!")
    print("\n💡 Solutions possibles:")
    print("  1. Vérifiez que le fichier .env contient bien:")
    print("     GITLAB_TOKEN=glpat-votre-token")
    print("  2. Ou créez un .env à la racine du projet")

    if config_dir:
        env_file = config_dir / ".env"
        if env_file.exists():
            print(f"\n📄 Aperçu de {env_file}:")
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[:10], 1):
                    # Masquer les tokens
                    if "TOKEN" in line.upper() and "=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2 and parts[1].strip():
                            print(f"  {i}. {parts[0]}=***masqué***")
                        else:
                            print(f"  {i}. {parts[0]}= ⚠️ VIDE!")
                    else:
                        print(f"  {i}. {line.rstrip()}")
    sys.exit(1)

if not PROJECT_ID:
    print("\n❌ GITLAB_PROJECT_ID manquant!")
    print("  Ajoutez dans .env: GITLAB_PROJECT_ID=79349939")
    sys.exit(1)

print(f"\n✅ Configuration OK")

# Connexion à GitLab
print(f"\n🔗 Connexion à GitLab...")
gl = gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)

try:
    project = gl.projects.get(PROJECT_ID)
    print(f"✅ Projet trouvé: {project.name}")
except Exception as e:
    print(f"❌ Erreur de connexion: {e}")
    sys.exit(1)

# Contenu d'un fichier XML Android avec un nouveau bouton
NEW_BUTTON_XML = """<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="16dp"
    android:background="#FFFFFF">

    <!-- En-tête de connexion -->
    <TextView
        android:id="@+id/text_login_title"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Bienvenue sur MyBiat"
        android:textSize="24sp"
        android:textStyle="bold"
        android:gravity="center"
        android:layout_marginBottom="30dp"/>

    <!-- Nouveau bouton Login ajouté pour tester la détection UI -->
    <Button
        android:id="@+id/btn_login_new"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Se connecter"
        android:textSize="16sp"
        android:textColor="#FFFFFF"
        android:background="#4CAF50"
        android:layout_marginTop="20dp"/>

    <!-- Nouveau champ Email -->
    <EditText
        android:id="@+id/edit_email_new"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="Email"
        android:inputType="textEmailAddress"
        android:layout_marginTop="10dp"
        android:padding="12dp"/>

    <!-- Nouveau champ Password -->
    <EditText
        android:id="@+id/edit_password_new"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="Mot de passe"
        android:inputType="textPassword"
        android:layout_marginTop="10dp"
        android:padding="12dp"/>

    <!-- Checkbox "Se souvenir de moi" -->
    <CheckBox
        android:id="@+id/checkbox_remember"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Se souvenir de moi"
        android:layout_marginTop="10dp"/>

</LinearLayout>
"""

def create_test_branch_and_mr():
    """Crée une branche de test avec un fichier XML modifié et une MR"""

    branch_name = "feature/test-ui-detection"
    file_path = "app/src/main/res/layout/activity_login_test.xml"

    print(f"\n🌿 Création de la branche '{branch_name}'...")

    # Vérifier si la branche existe déjà
    try:
        existing_branch = project.branches.get(branch_name)
        print(f"⚠️  La branche {branch_name} existe déjà, suppression...")
        project.branches.delete(branch_name)
        print(f"✅ Ancienne branche supprimée")
    except:
        print(f"✅ Branche {branch_name} n'existe pas encore")

    # Créer la nouvelle branche depuis main
    try:
        branch = project.branches.create({
            'branch': branch_name,
            'ref': 'main'
        })
        print(f"✅ Branche créée: {branch_name}")
    except Exception as e:
        print(f"❌ Erreur création branche: {e}")
        return False

    # Créer/modifier le fichier XML
    print(f"\n📝 Ajout du fichier XML: {file_path}")

    try:
        # Vérifier si le fichier existe
        try:
            existing_file = project.files.get(file_path=file_path, ref=branch_name)
            # Fichier existe, on le met à jour
            existing_file.content = NEW_BUTTON_XML
            existing_file.save(branch=branch_name, commit_message="🎨 Ajout nouveaux éléments UI (bouton login, 2 champs, checkbox)")
            print(f"✅ Fichier mis à jour")
        except:
            # Fichier n'existe pas, on le crée
            project.files.create({
                'file_path': file_path,
                'branch': branch_name,
                'content': NEW_BUTTON_XML,
                'commit_message': '🎨 Ajout nouveaux éléments UI (bouton login, 2 champs, checkbox)'
            })
            print(f"✅ Fichier créé: {file_path}")
    except Exception as e:
        print(f"❌ Erreur création fichier: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Créer la Merge Request
    print(f"\n🔀 Création de la Merge Request...")

    try:
        # Vérifier si une MR existe déjà pour cette branche
        existing_mrs = project.mergerequests.list(
            source_branch=branch_name,
            state='opened'
        )

        if existing_mrs:
            mr = existing_mrs[0]
            print(f"⚠️  MR existe déjà: #{mr.iid}")
            print(f"🔗 URL: {mr.web_url}")
        else:
            mr = project.mergerequests.create({
                'source_branch': branch_name,
                'target_branch': 'main',
                'title': '🤖 [TEST MCP] Ajout écran de login avec nouveaux éléments UI',
                'description': """
## 🎯 Objectif de cette MR de test

Cette Merge Request a été créée **automatiquement** pour tester le **MCP GitLab Server**.

### 📱 Changements UI détectables :

| Élément | Type | ID Android | Fonction |
|---------|------|------------|----------|
| 🔘 Bouton Login | Button | `btn_login_new` | Connexion utilisateur |
| 📧 Champ Email | EditText | `edit_email_new` | Saisie email |
| 🔒 Champ Password | EditText | `edit_password_new` | Saisie mot de passe |
| ☑️ Checkbox | CheckBox | `checkbox_remember` | Se souvenir de moi |

### 🧪 Tests attendus par le MCP Server :

Le système devrait **automatiquement détecter** :
1. ✅ **4 nouveaux éléments UI** (1 bouton, 2 champs, 1 checkbox)
2. ✅ **Générer des recommandations** :
   - Créer tests de clic sur le bouton
   - Créer tests de saisie pour email/password
   - Créer tests de validation (champs vides, format email)
   - Créer tests de la checkbox

### 🤖 Agents MCP concernés :

- **Agent GitLab** : Détection automatique des changements XML
- **Agent Test Generator** : Génération des tests Robot Framework
- **Orchestrateur Gemini** : Coordination et analyse contextuelle

### 📊 Résultat attendu du test :

```python
analyze_mr_for_ui_changes(mr_iid=1)
# Résultat attendu :
{
  "has_ui_changes": True,
  "xml_files_modified": ["activity_login_test.xml"],
  "new_ui_elements": [
    {"type": "button", "id": "btn_login_new"},
    {"type": "edittext", "id": "edit_email_new"},
    {"type": "edittext", "id": "edit_password_new"},
    {"type": "checkbox", "id": "checkbox_remember"}
  ],
  "recommendation": "✓ 1 nouveaux boutons → Créer tests de clic\\n✓ 2 nouveaux champs → Créer tests de saisie/validation"
}
```

---

> ⚠️ **Ceci est une MR de test pour validation du PFE.**  
> **Ne pas merger dans main sans validation QA.**
                """
            })
            print(f"✅ Merge Request créée: #{mr.iid}")
            print(f"🔗 URL: {mr.web_url}")

        print(f"\n📋 Résumé de la création:")
        print(f"  • Branche source: {branch_name}")
        print(f"  • Branche cible: main")
        print(f"  • MR ID: #{mr.iid}")
        print(f"  • Fichier XML: {file_path}")
        print(f"  • Éléments UI: 4 (1 bouton, 2 champs, 1 checkbox)")

        return True

    except Exception as e:
        print(f"❌ Erreur création MR: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_existing_mrs():
    """Liste les MRs existantes"""
    print(f"\n📋 Merge Requests actuellement ouvertes:")

    try:
        mrs = project.mergerequests.list(state='opened', per_page=10)

        if not mrs:
            print("  ❌ Aucune MR ouverte")
            return 0
        else:
            for mr in mrs:
                print(f"  • MR #{mr.iid}: {mr.title}")
                print(f"    Branch: {mr.source_branch} → {mr.target_branch}")
                print(f"    URL: {mr.web_url}")
            return len(mrs)
    except Exception as e:
        print(f"  ❌ Erreur lors de la récupération des MRs: {e}")
        return 0


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 CRÉATION DE MERGE REQUEST DE TEST POUR MCP GITLAB SERVER")
    print("="*70)

    # Lister les MRs existantes
    existing_count = list_existing_mrs()

    # Créer la MR de test
    print(f"\n" + "="*70)
    print("CRÉATION DE LA NOUVELLE MR DE TEST")
    print("="*70)

    success = create_test_branch_and_mr()

    print("\n" + "="*70)

    if success:
        print("\n🎉 🎉 🎉 SUCCÈS COMPLET! 🎉 🎉 🎉")
        print("\n✅ Une Merge Request de test a été créée dans GitLab")
        print("\n📖 Prochaines étapes:")
        print("  1️⃣  Ouvrez un nouveau terminal")
        print("  2️⃣  Relancez: python tests\\test_mcp_gitlab.py")
        print("  3️⃣  Résultats attendus:")
        print("     ✅ TEST 1 (get_merge_requests): 1 MR trouvée")
        print("     ✅ TEST 2 (get_mr_changes): 1 fichier modifié détecté")
        print("     ✅ TEST 4 (analyze_mr_for_ui_changes): 4 éléments UI détectés")
        print("\n🔍 Vérification sur GitLab:")
        print("  • Allez sur https://gitlab.com/votre-projet")
        print("  • Onglet 'Merge Requests'")
        print("  • Vous devriez voir: '🤖 [TEST MCP] Ajout écran de login'")
        print("\n" + "="*70)
    else:
        print("\n❌ Échec de la création de la MR")
        print("\n🔍 Vérifications à faire:")
        print("  • Le token GitLab a-t-il les permissions 'api' ?")
        print("  • Le projet ID est-il correct ?")
        print("  • La branche 'main' existe-t-elle dans le projet ?")
        print("\n" + "="*70)