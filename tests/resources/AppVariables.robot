*** Settings ***
Documentation    Variables globales : locators UI et données de test
...              App: FoodApp (com.example.mobile_app)
...              Basé sur les screenshots réels de l'application

*** Variables ***
# ============================================================================
# CONFIGURATION APPIUM
# ============================================================================
${APPIUM_URL}           http://localhost:4723
${PLATFORM_NAME}        Android
${PLATFORM_VERSION}     12
${DEVICE_NAME}          82403e660602
${APP_PACKAGE}          com.example.mobile_app
${APP_ACTIVITY}         .MainActivity
${AUTOMATION_NAME}      UiAutomator2
${NO_RESET}             ${True}

# ============================================================================
# TIMEOUTS
# ============================================================================
${SHORT_TIMEOUT}        5s
${MEDIUM_TIMEOUT}       10s
${LONG_TIMEOUT}         20s

# ============================================================================
# PAGE HOME — Locators validés via Appium Inspector ✅
# ============================================================================

# Barre de recherche
${HOME_SEARCH_BAR}              xpath=//android.widget.EditText

# Catégories
${HOME_CATEGORY_ALL}            accessibility_id=All
${HOME_CATEGORY_PASTA}          accessibility_id=Pasta
${HOME_CATEGORY_SANDWICH}       accessibility_id=sandwich
${HOME_CATEGORY_PIZZA}          accessibility_id=pizza

# Bottom Navigation Bar
${HOME_NAV_MENU}                accessibility_id=Menu\nTab 1 of 2
${HOME_NAV_LOGIN}               accessibility_id=Login\nTab 2 of 2

# ============================================================================
# PAGE SIGNUP (JOIN US) — Locators validés via Appium Inspector ✅
# ============================================================================

# Titre et sous-titre
${SIGNUP_TITLE}                 accessibility_id=Join Us
${SIGNUP_SUBTITLE}              accessibility_id=Create a new account

# Labels des champs (android.view.View — pour vérifier l'affichage)
${SIGNUP_LABEL_FIRSTNAME}       accessibility_id=First Name
${SIGNUP_LABEL_LASTNAME}        accessibility_id=Last Name
${SIGNUP_LABEL_EMAIL}           accessibility_id=Email Address
${SIGNUP_LABEL_PASSWORD}        accessibility_id=Password
${SIGNUP_LABEL_PHONE}           accessibility_id=Phone Number

# Champs de saisie (android.widget.EditText — pour taper du texte)
${SIGNUP_INPUT_FIRSTNAME}       xpath=//android.widget.ScrollView/android.widget.EditText[1]
${SIGNUP_INPUT_LASTNAME}        xpath=//android.widget.ScrollView/android.widget.EditText[2]
${SIGNUP_INPUT_EMAIL}           xpath=//android.widget.ScrollView/android.widget.EditText[3]
${SIGNUP_INPUT_PASSWORD}        xpath=//android.widget.ScrollView/android.widget.EditText[4]
${SIGNUP_INPUT_PHONE}           xpath=//android.widget.ScrollView/android.widget.EditText[5]

# Bouton et lien
${SIGNUP_BTN_SIGNUP}            accessibility_id=Sign Up
${SIGNUP_LINK_LOGIN}            accessibility_id=Login

# ============================================================================
# DONNÉES DE TEST
# ============================================================================
${VALID_EMAIL}                  testuser@foodapp.com
${VALID_PASSWORD}               Test@1234
${VALID_FIRSTNAME}              Ahmed
${VALID_LASTNAME}               Ben Ali
${VALID_PHONE}                  58829251
${INVALID_EMAIL}                invalid_email_format
${WRONG_PASSWORD}               WrongPass@999

# Termes de recherche
${SEARCH_TERM_VALID}            tacos
${SEARCH_TERM_PASTA}            pasta
${SEARCH_TERM_NO_RESULT}        xyzabc123
