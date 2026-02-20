*** Settings ***
Documentation    Keywords globaux réutilisables dans tous les tests
...              Setup/Teardown, navigation, utilitaires

Library         AppiumLibrary
Resource        AppVariables.robot

*** Keywords ***

# SETUP & TEARDOWN

Open FoodApp
    [Documentation]    Lance l'application FoodApp sur le device Android
    Open Application    ${APPIUM_URL}
    ...                 platformName=${PLATFORM_NAME}
    ...                 platformVersion=${PLATFORM_VERSION}
    ...                 deviceName=${DEVICE_NAME}
    ...                 appPackage=${APP_PACKAGE}
    ...                 appActivity=${APP_ACTIVITY}
    ...                 automationName=${AUTOMATION_NAME}
    ...                 noReset=${NO_RESET}
    ...                 skipServerInstallation=${True}
    ...                 skipDeviceInitialization=${True}
    ...                 ignoreHiddenApiPolicyError=${True}
    ...                 enforceXPath1=${True}

Close FoodApp
    [Documentation]    Ferme la session Appium proprement
    Close Application

Reset And Open FoodApp
    [Documentation]    Ferme et relance l'app (utile entre les tests)
    Run Keyword And Ignore Error    Close Application
    Open Application    ${APPIUM_URL}
    ...                 platformName=${PLATFORM_NAME}
    ...                 platformVersion=${PLATFORM_VERSION}
    ...                 deviceName=${DEVICE_NAME}
    ...                 appPackage=${APP_PACKAGE}
    ...                 appActivity=${APP_ACTIVITY}
    ...                 automationName=${AUTOMATION_NAME}
    ...                 noReset=${False}
    ...                 skipServerInstallation=${True}
    ...                 skipDeviceInitialization=${True}
    ...                 ignoreHiddenApiPolicyError=${True}
    ...                 enforceXPath1=${True}

# NAVIGATION GLOBALE


Navigate To Login Tab
    [Documentation]    Clique sur l'onglet "Login" dans la bottom nav bar
    Wait Until Element Is Visible    ${HOME_NAV_LOGIN}    ${MEDIUM_TIMEOUT}
    Click Element                    ${HOME_NAV_LOGIN}

Navigate To Menu Tab
    [Documentation]    Clique sur l'onglet "Menu" dans la bottom nav bar
    Wait Until Element Is Visible    ${HOME_NAV_MENU}    ${MEDIUM_TIMEOUT}
    Click Element                    ${HOME_NAV_MENU}

Go Back
    [Documentation]    Appuie sur le bouton retour Android
    Press Keycode    4

# ============================================================================
# VÉRIFICATIONS COMMUNES
# ============================================================================

Page Should Show Element
    [Arguments]    ${locator}    ${timeout}=${MEDIUM_TIMEOUT}
    [Documentation]    Vérifie qu'un élément est visible sur la page
    Wait Until Element Is Visible    ${locator}    ${timeout}
    Element Should Be Visible        ${locator}

Page Should Not Show Element
    [Arguments]    ${locator}    ${timeout}=${SHORT_TIMEOUT}
    [Documentation]    Vérifie qu'un élément n'est PAS visible
    Run Keyword And Expect Error    *    Element Should Be Visible    ${locator}

Element Should Be Enabled And Clickable
    [Arguments]    ${locator}
    [Documentation]    Vérifie qu'un élément est visible ET actif
    Element Should Be Visible    ${locator}
    Element Should Be Enabled    ${locator}

# ============================================================================
# UTILITAIRES
# ============================================================================

Clear And Input Text
    [Arguments]    ${locator}    ${text}
    [Documentation]    Efface le champ puis saisit le texte
    Wait Until Element Is Visible    ${locator}    ${MEDIUM_TIMEOUT}
    Clear Text                       ${locator}
    Input Text                       ${locator}    ${text}

Take Screenshot On Failure
    [Documentation]    Capture d'écran automatique en cas d'échec
    Capture Page Screenshot

Hide Keyboard If Visible
    [Documentation]    Masque le clavier si affiché
    Run Keyword And Ignore Error    Hide Keyboard

Scroll Down
    [Documentation]    Scroll vers le bas de l'écran
    Swipe    540    1200    540    400    500

Scroll Up
    [Documentation]    Scroll vers le haut de l'écran
    Swipe    540    400    540    1200    500

Wait For Page Load
    [Documentation]    Attend que la page soit chargée (pause courte)
    Sleep    1s
