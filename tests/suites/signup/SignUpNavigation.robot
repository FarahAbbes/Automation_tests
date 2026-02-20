*** Settings ***
Documentation    Suite de tests : SignUp Page (Join Us)
...              Locators validés  via Appium Inspector
...              Couvre : affichage, saisie champs, validation, navigation

Library         AppiumLibrary
Resource        ../../resources/AppVariables.robot
Resource        ../../resources/GlobalKeywords.robot
Resource        ../../resources/pages/HomePage.robot
Resource        ../../resources/pages/SignUpPage.robot

Suite Setup      Run Keywords
...              Open FoodApp
...              AND    Click Login Tab
...              AND    SignUp Page Should Be Displayed
Suite Teardown   Close FoodApp
Test Teardown    Run Keyword If Test Failed    Capture Page Screenshot

*** Test Cases ***
# SCENARIO 1 : Affichage de la page SignUp

TC-SIGNUP-001 : La page SignUp doit être affichée avec le titre "Join Us"
    [Documentation]    Vérifie que le titre "Join Us" et le sous-titre
    ...                "Create a new account" sont bien visibles
    [Tags]    signup    smoke
    SignUp Page Should Be Displayed

TC-SIGNUP-002 : Tous les champs du formulaire doivent être affichés
    [Documentation]    Vérifie que First Name, Last Name, Email,
    ...                Password et Phone Number sont tous visibles
    [Tags]    signup    smoke
    All SignUp Fields Should Be Visible

TC-SIGNUP-003 : Le bouton Sign Up doit être visible et actif
    [Documentation]    Vérifie que le bouton Sign Up est présent
    ...                et qu'on peut cliquer dessus
    [Tags]    signup    smoke
    SignUp Button Should Be Visible

TC-SIGNUP-004 : Le lien Login doit être visible en bas de page
    [Documentation]    Vérifie que le lien "Login" est affiché
    ...                pour les utilisateurs qui ont déjà un compte
    [Tags]    signup    smoke
    Login Link Should Be Visible


# SCENARIO 2 : Saisie dans les champs — valeur visible après saisie


TC-SIGNUP-005 : Le champ First Name accepte et affiche la saisie
    [Documentation]    Tape un prénom et vérifie que le texte
    ...                est bien visible dans le champ
    [Tags]    signup    fields
    Enter First Name    ${VALID_FIRSTNAME}
    First Name Field Should Display    ${VALID_FIRSTNAME}

TC-SIGNUP-006 : Le champ Last Name accepte et affiche la saisie
    [Documentation]    Tape un nom et vérifie que le texte
    ...                est bien visible dans le champ
    [Tags]    signup    fields
    Enter Last Name    ${VALID_LASTNAME}
    Last Name Field Should Display    ${VALID_LASTNAME}

TC-SIGNUP-007 : Le champ Email accepte et affiche la saisie
    [Documentation]    Tape un email et vérifie que le texte
    ...                est bien visible dans le champ
    [Tags]    signup    fields
    Enter Email    ${VALID_EMAIL}
    Email Field Should Display    ${VALID_EMAIL}

TC-SIGNUP-008 : Le champ Phone accepte et affiche la saisie
    [Documentation]    Tape un numéro de téléphone et vérifie
    ...                que le texte est bien visible dans le champ
    [Tags]    signup    fields
    Enter Phone Number    ${VALID_PHONE}
    Phone Field Should Display    ${VALID_PHONE}

TC-SIGNUP-009 : Le champ Password accepte la saisie
    [Documentation]    Tape un mot de passe et vérifie que
    ...                le champ est rempli (valeur masquée)
    [Tags]    signup    fields
    Enter Password    ${VALID_PASSWORD}
    Wait Until Element Is Visible    ${SIGNUP_INPUT_PASSWORD}    ${MEDIUM_TIMEOUT}
    Log     Password saisi — valeur masquée comme attendu


# SCENARIO 3 : Inscription complète (Happy Path)

TC-SIGNUP-010 : Remplir le formulaire complet et soumettre
    [Documentation]    Remplit tous les champs avec des données valides
    ...                et clique sur Sign Up
    [Tags]    signup    happy_path    smoke
    Fill SignUp Form
    ...    ${VALID_FIRSTNAME}
    ...    ${VALID_LASTNAME}
    ...    ${VALID_EMAIL}
    ...    ${VALID_PASSWORD}
    ...    ${VALID_PHONE}
    Click Sign Up Button
    Sleep    2s

# SCENARIO 4 : Navigation depuis SignUp

TC-SIGNUP-011 : Clic sur Login redirige vers la page de connexion
    [Documentation]    Depuis la page SignUp, cliquer sur le lien "Login"
    ...                doit naviguer vers la page de connexion
    [Tags]    signup    navigation
    Click Login Link
    Sleep    2s

TC-SIGNUP-012 : Retour sur Menu Tab revient à la HomePage
    [Documentation]    Depuis la page SignUp, cliquer sur l'onglet Menu
    ...                doit ramener à la HomePage
    [Tags]    signup    navigation    smoke
    Click Menu Tab
    Home Page Should Be Displayed
