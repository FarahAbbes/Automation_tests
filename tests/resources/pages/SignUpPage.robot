*** Settings ***
Documentation    Page Object : Écran SignUp (Join Us)
...              Locators validés via Appium Inspector ✅
...              Pattern POM — contient UNIQUEMENT les keywords de la SignUpPage

Library         AppiumLibrary
Resource        ../AppVariables.robot
Resource        ../GlobalKeywords.robot

*** Keywords ***

# ============================================================================
# VÉRIFICATIONS — Est-ce que la page est bien affichée ?
# ============================================================================

SignUp Page Should Be Displayed
    [Documentation]    Vérifie que la page SignUp est bien affichée
    ...                en contrôlant le titre, sous-titre et les champs
    Wait Until Element Is Visible    ${SIGNUP_TITLE}              ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${SIGNUP_SUBTITLE}           ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${SIGNUP_LABEL_FIRSTNAME}    ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${SIGNUP_LABEL_LASTNAME}     ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${SIGNUP_BTN_SIGNUP}         ${MEDIUM_TIMEOUT}
    Log     SignUp Page affichée correctement

All SignUp Fields Should Be Visible
    [Documentation]    Vérifie que tous les champs du formulaire sont affichés
    Wait Until Element Is Visible    ${SIGNUP_LABEL_FIRSTNAME}    ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${SIGNUP_LABEL_LASTNAME}     ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${SIGNUP_LABEL_EMAIL}        ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${SIGNUP_LABEL_PASSWORD}     ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${SIGNUP_LABEL_PHONE}        ${MEDIUM_TIMEOUT}
    Log     Tous les champs du formulaire sont visibles

SignUp Button Should Be Visible
    [Documentation]    Vérifie que le bouton Sign Up est visible et cliquable
    Wait Until Element Is Visible    ${SIGNUP_BTN_SIGNUP}    ${MEDIUM_TIMEOUT}
    Expect Element                   ${SIGNUP_BTN_SIGNUP}    enabled=True
    Log     Bouton Sign Up visible et actif

Login Link Should Be Visible
    [Documentation]    Vérifie que le lien "Login" est visible en bas de page
    Wait Until Element Is Visible    ${SIGNUP_LINK_LOGIN}    ${MEDIUM_TIMEOUT}
    Log     Lien Login visible

# ============================================================================
# ACTIONS — Saisie dans les champs du formulaire
# ============================================================================

Enter First Name
    [Arguments]    ${firstname}
    [Documentation]    Saisit le prénom dans le champ First Name
    Wait Until Element Is Visible    ${SIGNUP_INPUT_FIRSTNAME}    ${MEDIUM_TIMEOUT}
    Click Element                    ${SIGNUP_INPUT_FIRSTNAME}
    Input Text                       ${SIGNUP_INPUT_FIRSTNAME}    ${firstname}
    Hide Keyboard
    Log     First Name saisi : ${firstname}

Enter Last Name
    [Arguments]    ${lastname}
    [Documentation]    Saisit le nom dans le champ Last Name
    Wait Until Element Is Visible    ${SIGNUP_INPUT_LASTNAME}    ${MEDIUM_TIMEOUT}
    Click Element                    ${SIGNUP_INPUT_LASTNAME}
    Input Text                       ${SIGNUP_INPUT_LASTNAME}    ${lastname}
    Hide Keyboard
    Log     Last Name saisi : ${lastname}

Enter Email
    [Arguments]    ${email}
    [Documentation]    Saisit l'email dans le champ Email Address
    Wait Until Element Is Visible    ${SIGNUP_INPUT_EMAIL}    ${MEDIUM_TIMEOUT}
    Click Element                    ${SIGNUP_INPUT_EMAIL}
    Input Text                       ${SIGNUP_INPUT_EMAIL}    ${email}
    Hide Keyboard
    Log     Email saisi : ${email}

Enter Password
    [Arguments]    ${password}
    [Documentation]    Saisit le mot de passe dans le champ Password
    Wait Until Element Is Visible    ${SIGNUP_INPUT_PASSWORD}    ${MEDIUM_TIMEOUT}
    Click Element                    ${SIGNUP_INPUT_PASSWORD}
    Input Text                       ${SIGNUP_INPUT_PASSWORD}    ${password}
    Hide Keyboard
    Log     Password saisi

Enter Phone Number
    [Arguments]    ${phone}
    [Documentation]    Saisit le numéro de téléphone dans le champ Phone Number
    Wait Until Element Is Visible    ${SIGNUP_INPUT_PHONE}    ${MEDIUM_TIMEOUT}
    Click Element                    ${SIGNUP_INPUT_PHONE}
    Input Text                       ${SIGNUP_INPUT_PHONE}    ${phone}
    Hide Keyboard
    Log     Phone saisi : ${phone}

Fill SignUp Form
    [Arguments]    ${firstname}    ${lastname}    ${email}    ${password}    ${phone}
    [Documentation]    Remplit tous les champs du formulaire en une seule action
    Enter First Name      ${firstname}
    Enter Last Name       ${lastname}
    Enter Email           ${email}
    Enter Password        ${password}
    Enter Phone Number    ${phone}
    Log     Formulaire complet rempli

Click Sign Up Button
    [Documentation]    Clique sur le bouton Sign Up
    Wait Until Element Is Visible    ${SIGNUP_BTN_SIGNUP}    ${MEDIUM_TIMEOUT}
    Click Element                    ${SIGNUP_BTN_SIGNUP}
    Log    Bouton Sign Up cliqué

Click Login Link
    [Documentation]    Clique sur le lien "Login" en bas de page
    ...                (Already have an account? Login)
    Wait Until Element Is Visible    ${SIGNUP_LINK_LOGIN}    ${MEDIUM_TIMEOUT}
    Click Element                    ${SIGNUP_LINK_LOGIN}
    Log     Lien Login cliqué

# ============================================================================
# VÉRIFICATIONS CHAMPS — Valider la saisie visible
# ============================================================================

Field Should Display Value
    [Arguments]    ${input_locator}    ${expected_value}
    [Documentation]    Vérifie qu'un champ affiche bien la valeur saisie
    Wait Until Element Is Visible    ${input_locator}    ${MEDIUM_TIMEOUT}
    ${actual}=    Get Element Attribute    ${input_locator}    text
    Should Be Equal As Strings    ${actual}    ${expected_value}
    ...    msg= Le champ affiche "${actual}" au lieu de "${expected_value}"
    Log     Le champ affiche bien : "${expected_value}"

First Name Field Should Display
    [Arguments]    ${expected_value}
    Field Should Display Value    ${SIGNUP_INPUT_FIRSTNAME}    ${expected_value}

Last Name Field Should Display
    [Arguments]    ${expected_value}
    Field Should Display Value    ${SIGNUP_INPUT_LASTNAME}    ${expected_value}

Email Field Should Display
    [Arguments]    ${expected_value}
    Field Should Display Value    ${SIGNUP_INPUT_EMAIL}    ${expected_value}

Phone Field Should Display
    [Arguments]    ${expected_value}
    Field Should Display Value    ${SIGNUP_INPUT_PHONE}    ${expected_value}
