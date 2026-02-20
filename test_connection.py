"""
TEST RAPIDE — Connexion Appium device réel MyBiat
Valeurs hardcodées pour bypasser le problème .env
Placer ce fichier à la racine : FoodAppTest/test_connection.py
"""
from appium import webdriver
import xml.etree.ElementTree as ET
import base64, json
from pathlib import Path
from datetime import datetime

# ══════════════════════════════════════════════════════
# ▶ CONFIG — modifie si besoin
# ══════════════════════════════════════════════════════
APPIUM_URL       = "http://localhost:4723"
DEVICE_NAME      = "82403e660602"      # adb devices
PLATFORM_VERSION = "12"
APP_PACKAGE      = "com.example.mobile_app"
APP_ACTIVITY     = ".MainActivity"
GEMINI_API_KEY   = ""                  # laisse vide pour tester sans Gemini
GEMINI_MODEL     = "gemini-2.5-flash"
# ══════════════════════════════════════════════════════

# Essaie de charger la vraie clé Gemini depuis config/.env
try:
    from dotenv import load_dotenv
    import os
    _root = Path(__file__).parent
    for _p in [_root/"config"/".env", _root/".env"]:
        if _p.exists():
            load_dotenv(_p, override=True)
            GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
            print(f"✅ .env trouvé : {_p}")
            break
    else:
        # Cherche config même avec espace dans le nom
        for _item in _root.iterdir():
            if _item.is_dir() and "config" in _item.name.lower():
                _env = _item / ".env"
                if _env.exists():
                    load_dotenv(_env, override=True)
                    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
                    print(f"✅ .env trouvé : {_env}")
                    break
except Exception as e:
    print(f"⚠️  .env non chargé ({e}) — on utilise les valeurs hardcodées")

print(f"\n{'═'*55}")
print(f"  CONNEXION APPIUM — DEVICE RÉEL")
print(f"{'═'*55}")
print(f"  URL     : {APPIUM_URL}")
print(f"  Device  : {DEVICE_NAME}")
print(f"  Android : {PLATFORM_VERSION}")
print(f"  Package : {APP_PACKAGE}")
print(f"  Gemini  : {'✅ clé présente' if GEMINI_API_KEY else '⚠️  pas de clé (test sans IA)'}")
print(f"{'═'*55}\n")

# ── ÉTAPE 1 : Connexion ────────────────────────────────
print("⏳ Connexion au device...")
caps = {
    "platformName":              "Android",
    "appium:platformVersion":    PLATFORM_VERSION,
    "appium:deviceName":         DEVICE_NAME,
    "appium:appPackage":         APP_PACKAGE,
    "appium:appActivity":        APP_ACTIVITY,
    "appium:automationName":     "UiAutomator2",
    "appium:noReset":            True,
    "appium:autoGrantPermissions": True,
    "appium:newCommandTimeout":          120,
    # Android 12+ device réel : ignore l'erreur hidden_api_policy (SecurityException)
    "appium:ignoreHiddenApiPolicyError":  True,
    "appium:skipDeviceInitialization":    False,
    "appium:disableWindowAnimation":      True,
    "appium:skipUnlock":                  True,
}

try:
    from selenium.webdriver.common.options import ArgOptions

    class _AppiumCaps(ArgOptions):
        def __init__(self, caps):
            super().__init__()
            self._caps = caps
        def to_capabilities(self):
            return self._caps

    driver = webdriver.Remote(
        command_executor=APPIUM_URL,
        options=_AppiumCaps(caps)
    )
    print("✅ SESSION APPIUM CRÉÉE !\n")
except Exception as e:
    print(f"❌ Échec connexion : {e}")
    print("\n💡 Vérifications :")
    print("   1. MyBiat est ouvert sur ton téléphone")
    print("   2. appium tourne dans un autre terminal")
    print("   3. adb devices → 82403e660602 device")
    exit(1)

# ── ÉTAPE 2 : Capture de l'écran ──────────────────────
print("📸 Capture screenshot...")
try:
    scr_b64 = driver.get_screenshot_as_base64()
    scr_path = Path("screenshot_test.png")
    scr_path.write_bytes(base64.b64decode(scr_b64))
    print(f"✅ Screenshot sauvegardé : {scr_path.absolute()}")
except Exception as e:
    print(f"⚠️  Screenshot échoué : {e}")
    scr_b64 = None

# ── ÉTAPE 3 : Extraction UI ────────────────────────────
print("\n🔎 Extraction hiérarchie UI...")
try:
    page_source = driver.page_source
    print(f"✅ Page source reçue ({len(page_source)} caractères)")

    root = ET.fromstring(page_source)

    # Extraire tous les éléments interactifs
    elements = []
    def walk(node):
        a = node.attrib
        rid   = a.get("resource-id", "")
        text  = a.get("text", "")
        desc  = a.get("content-desc", "")
        cls   = a.get("class", "").split(".")[-1]
        click = a.get("clickable", "false") == "true"
        if rid or (text and len(text) < 100) or click:
            elements.append({
                "class":    cls,
                "id":       rid.split("/")[-1] if "/" in rid else rid,
                "full_id":  rid,
                "text":     text,
                "desc":     desc,
                "click":    click,
                "enabled":  a.get("enabled","true") == "true",
                "bounds":   a.get("bounds",""),
            })
        for child in node:
            walk(child)
    walk(root)

    print(f"✅ {len(elements)} éléments UI extraits\n")

    # Affichage des éléments interactifs
    print("┌─ ÉLÉMENTS UI DÉTECTÉS ─────────────────────────────┐")
    for e in elements:
        icon = "🔘" if e["click"] else "📝" if "Edit" in e["class"] else "🏷️"
        state = "✅" if e["enabled"] else "🚫"
        label = e["text"] or e["desc"] or "(no text)"
        rid   = e["id"] or "(no id)"
        print(f"│ {state}{icon} [{rid}]  {label[:35]}")
    print("└────────────────────────────────────────────────────┘")

except Exception as e:
    print(f"❌ Extraction UI échouée : {e}")
    elements = []

# ── ÉTAPE 4 : Envoi à Gemini ──────────────────────────
if GEMINI_API_KEY and elements:
    print("\n🤖 Envoi à Gemini pour analyse...")
    try:
        from google import genai
        from google.genai import types as gtypes

        # Détecter la page
        all_ids = " ".join(e["id"] for e in elements).lower()
        all_txt = " ".join(e["text"] for e in elements).lower()
        combined = all_ids + " " + all_txt

        if any(k in combined for k in ["login","password","username","connexion","mot_de_passe"]):
            page_name = "LOGIN"
        elif any(k in combined for k in ["solde","compte","balance","dashboard"]):
            page_name = "DASHBOARD"
        elif any(k in combined for k in ["virement","transfer","montant"]):
            page_name = "TRANSFER"
        else:
            page_name = "UNKNOWN"

        print(f"   📄 Page détectée : {page_name}")

        # Construire le prompt
        elems_json = json.dumps([
            {"id": e["id"], "text": e["text"], "class": e["class"],
             "clickable": e["click"], "desc": e["desc"]}
            for e in elements
        ], ensure_ascii=False, indent=2)

        prompt = f"""Tu es expert Robot Framework + Appium pour l'app bancaire MyBiat (Android).

Page actuelle détectée : {page_name}
Package : {APP_PACKAGE}

Éléments UI extraits du device réel :
```json
{elems_json}
```

Ta mission :
1. Confirme la page détectée
2. Génère un fichier Robot Framework complet avec :
   - Page Object keywords pour cette page
   - 3 cas de test (happy path + 2 cas d'erreur)
   - Locators basés UNIQUEMENT sur les resource_id fournis ci-dessus
3. Identifie les locators fragiles et propose des alternatives XPath robustes
4. Donne 3 recommandations pour améliorer la maintenabilité des tests

Format : Robot Framework valide, 4 espaces d'indentation."""

        client = genai.Client(api_key=GEMINI_API_KEY)

        # Inclure le screenshot si disponible
        parts = [prompt]
        if scr_b64:
            parts.append(
                gtypes.Part.from_bytes(
                    data=base64.b64decode(scr_b64),
                    mime_type="image/png"
                )
            )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=parts
        )

        gemini_text = response.text
        print("✅ Réponse Gemini reçue !\n")

        # Sauvegarder
        out_dir = Path("ai_results")
        out_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        md_path = out_dir / f"{ts}_{page_name.lower()}_analysis.md"
        md_path.write_text(
            f"# Analyse Gemini — {page_name}\n\n{gemini_text}",
            encoding="utf-8"
        )
        print(f"💾 Analyse sauvegardée : {md_path}")

        # Extraire et sauvegarder les fichiers .robot
        import re
        robot_blocks = re.findall(r'```(?:robot|robotframework)?\n(.*?)```', gemini_text, re.DOTALL)
        for i, block in enumerate(robot_blocks):
            if "***" in block:
                robot_path = out_dir / f"{ts}_{page_name.lower()}_{i+1}.robot"
                robot_path.write_text(block.strip(), encoding="utf-8")
                print(f"🤖 Fichier Robot : {robot_path}")

        print("\n" + "─"*55)
        print("RÉPONSE GEMINI :")
        print("─"*55)
        print(gemini_text[:3000])
        if len(gemini_text) > 3000:
            print(f"\n... (+{len(gemini_text)-3000} caractères — voir {md_path})")

    except Exception as e:
        print(f"❌ Erreur Gemini : {type(e).__name__}: {e}")

elif not GEMINI_API_KEY:
    print("\n⚠️  Gemini ignoré (GEMINI_API_KEY manquant)")
    print("   Ajoute ta clé dans config/.env ou en haut de ce script")

# ── ÉTAPE 5 : Fermeture ───────────────────────────────
driver.quit()
print("\n✅ Session Appium fermée.")
print(f"{'═'*55}")
print("  TEST TERMINÉ")
print(f"{'═'*55}")