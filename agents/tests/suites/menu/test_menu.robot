*** Settings ***
Library           AppiumLibrary
Resource          menu_page.robot
Test Setup        Open Application For Tests
Test Teardown     Close Application

*** Variables ***
${APPIUM_URL}         http://localhost:4723
${DEVICE_NAME}        82403e660602
${APP_PACKAGE}        com.example.mobile_app
${APP_ACTIVITY}       .MainActivity
${PLATFORM_VERSION}   12
${DEFAULT_TIMEOUT}    10s

*** Test Cases ***
TC-MENU-01 Rechercher et sélectionner un article (Nominal)
    [Documentation]    Vérifie qu'une recherche sur "pasta" affiche bien l'article pasta
    ...                et que l'on peut cliquer dessus.
    [Tags]             menu    smoke    happy_path
    Open Menu Page
    Enter Search Text    pasta
    Wait Until Page Contains Element    ${LOC_ITEM_PASTA_DETAILS}    timeout=${DEFAULT_TIMEOUT}
    Select Food Item    pasta

TC-MENU-02 Recherche d article inexistant (Cas d erreur)
    [Documentation]    Vérifie qu une recherche sans résultat masque tous les articles connus.
    [Tags]             menu    error_case
    Open Menu Page
    Enter Search Text    nonexistent_item_xyz
    Sleep    2s
    Page Should Not Contain Element    ${LOC_ANY_PRODUCT_ITEM}

TC-MENU-03 Recherche vide et navigation par categorie (Cas limite)
    [Documentation]    Vérifie qu une recherche vide conserve tous les articles
    ...                et que le filtre categorie Pizza fonctionne correctement.
    [Tags]             menu    edge_case
    Open Menu Page
    Enter Search Text    ${EMPTY}
    Wait Until Page Contains Element    ${LOC_CAT_ALL}              timeout=${DEFAULT_TIMEOUT}
    Wait Until Page Contains Element    ${LOC_ITEM_TACOS_DETAILS}   timeout=${DEFAULT_TIMEOUT}
    Select Category    Pizza
    Wait Until Page Contains Element    ${LOC_ITEM_NEPTUNE_PIZZA_DETAILS}    timeout=${DEFAULT_TIMEOUT}
    Page Should Not Contain Element     ${LOC_ITEM_TACOS_DETAILS}

*** Keywords ***
Open Application For Tests
    [Documentation]    Ouvre l application mobile avec Appium.
    Open Application    ${APPIUM_URL}
    ...    platformName=Android
    ...    platformVersion=${PLATFORM_VERSION}
    ...    deviceName=${DEVICE_NAME}
    ...    appPackage=${APP_PACKAGE}
    ...    appActivity=${APP_ACTIVITY}
    ...    automationName=UiAutomator2
    ...    noReset=true
    ...    autoGrantPermissions=true
