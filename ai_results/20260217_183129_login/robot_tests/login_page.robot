*** Settings ***
Library    AppiumLibrary
# Importer d'autres bibliothèques si nécessaire, par exemple SeleniumLibrary si c'est une application hybride,
# mais ici nous nous concentrons sur Appium pour le mobile natif.

*** Variables ***
${LOGIN_PAGE_TITLE}                  Login

# Locators des éléments robustes
&{LOGIN_PAGE_LOCATORS}
...    FORGOT_PASSWORD_LINK=accessibility id=Forgot Password?
...    SIGN_IN_BUTTON=accessibility id=Sign In
...    CREATE_ACCOUNT_BUTTON=accessibility id=Create Account

*** Keywords ***
Verify Login Page Is Displayed
    [Documentation]    Vérifie que la page de connexion est affichée.
    Wait Until Page Contains Element    ${LOGIN_PAGE_LOCATORS.SIGN_IN_BUTTON}    timeout=${GENERIC_TIMEOUT}
    Page Should Contain Text    Welcome Back
    Page Should Contain Text    Sign in to continue

# --- Keywords pour les éléments avec locators manquants (non implémentables sans locators) ---
# Enter Email Address    [email]
#     [Documentation]    Saisit l'adresse email dans le champ correspondant.
#     # IMPOSSIBLE : Le champ email n'a pas de locator fourni.

# Enter Password    [password]
#     [Documentation]    Saisit le mot de passe dans le champ correspondant.
#     # IMPOSSIBLE : Le champ mot de passe n'a pas de locator fourni.

# Click Back Button
#     [Documentation]    Clique sur le bouton de retour.
#     # IMPOSSIBLE : Le bouton de retour n'a pas de locator fourni.

# Toggle Password Visibility
#     [Documentation]    Clique sur l'icône pour masquer/afficher le mot de passe.
#     # IMPOSSIBLE : L'icône de visibilité du mot de passe (si elle est une entité séparée) n'a pas de locator fourni.
# -----------------------------------------------------------------------------------------

Click Sign In Button
    [Documentation]    Clique sur le bouton "Sign In".
    Click Element    ${LOGIN_PAGE_LOCATORS.SIGN_IN_BUTTON}

Click Forgot Password Link
    [Documentation]    Clique sur le lien "Forgot Password?".
    Click Element    ${LOGIN_PAGE_LOCATORS.FORGOT_PASSWORD_LINK}

Click Create Account Button
    [Documentation]    Clique sur le bouton "Create Account".
    Click Element    ${LOGIN_PAGE_LOCATORS.CREATE_ACCOUNT_BUTTON}

Verify Error Message    [expected_message]
    [Documentation]    Vérifie la présence d'un message d'erreur.
    # Ceci est un exemple générique. Le locator de l'erreur réelle dépend de l'implémentation de l'application.
    # Pour l'instant, on suppose une simple vérification de texte sur la page.
    Page Should Contain Text    ${expected_message}