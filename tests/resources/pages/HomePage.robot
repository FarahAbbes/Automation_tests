*** Settings ***
Documentation    Page Object : Écran d'accueil (HomePage)
...              Locators validés via Appium Inspector
...              Pattern POM — contient UNIQUEMENT les keywords de la HomePage

Library         AppiumLibrary
Resource        ../AppVariables.robot
Resource        ../GlobalKeywords.robot

*** Keywords ***

# VÉRIFICATIONS — Est-ce que la page est bien affichée ?

Home Page Should Be Displayed
    [Documentation]    Vérifie que la HomePage est bien affichée
    ...                en contrôlant les éléments principaux
    Wait Until Element Is Visible    ${HOME_SEARCH_BAR}       ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${HOME_NAV_MENU}         ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${HOME_NAV_LOGIN}        ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${HOME_CATEGORY_ALL}     ${MEDIUM_TIMEOUT}
    Log     HomePage affichée correctement

Search Bar Should Be Visible
    [Documentation]    Vérifie que la barre de recherche est visible et active
    Wait Until Element Is Visible    ${HOME_SEARCH_BAR}    ${MEDIUM_TIMEOUT}
    Element Should Be Enabled        ${HOME_SEARCH_BAR}
    Log     Barre de recherche visible et active

All Categories Should Be Visible
    [Documentation]    Vérifie que les 4 catégories sont toutes affichées
    Wait Until Element Is Visible    ${HOME_CATEGORY_ALL}        ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${HOME_CATEGORY_PASTA}      ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${HOME_CATEGORY_SANDWICH}   ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${HOME_CATEGORY_PIZZA}      ${MEDIUM_TIMEOUT}
    Log     Les 4 catégories sont affichées

Bottom Nav Bar Should Be Visible
    [Documentation]    Vérifie que les 2 onglets Menu et Login sont présents
    Wait Until Element Is Visible    ${HOME_NAV_MENU}     ${MEDIUM_TIMEOUT}
    Wait Until Element Is Visible    ${HOME_NAV_LOGIN}    ${MEDIUM_TIMEOUT}
    Log     Bottom navigation bar affichée

# ============================================================================
# ACTIONS — Ce qu'on peut faire sur la HomePage
# ============================================================================

Click Category
    [Arguments]    ${category_locator}
    [Documentation]    Clique sur une catégorie donnée
    Wait Until Element Is Visible    ${category_locator}    ${MEDIUM_TIMEOUT}
    Click Element                    ${category_locator}
    Log     Catégorie cliquée

Click Category All
    [Documentation]    Clique sur la catégorie "All"
    Click Category    ${HOME_CATEGORY_ALL}

Click Category Pasta
    [Documentation]    Clique sur la catégorie "Pasta"
    Click Category    ${HOME_CATEGORY_PASTA}

Click Category Sandwich
    [Documentation]    Clique sur la catégorie "sandwich"
    Click Category    ${HOME_CATEGORY_SANDWICH}

Click Category Pizza
    [Documentation]    Clique sur la catégorie "pizza"
    Click Category    ${HOME_CATEGORY_PIZZA}

Click Login Tab
    [Documentation]    Clique sur l'onglet Login (bottom nav bar)
    Wait Until Element Is Visible    ${HOME_NAV_LOGIN}    ${MEDIUM_TIMEOUT}
    Click Element                    ${HOME_NAV_LOGIN}
    Log     Onglet Login cliqué

Click Menu Tab
    [Documentation]    Clique sur l'onglet Menu (bottom nav bar)
    Wait Until Element Is Visible    ${HOME_NAV_MENU}    ${MEDIUM_TIMEOUT}
    Click Element                    ${HOME_NAV_MENU}
    Log    Onglet Menu cliqué

Search Food
    [Arguments]    ${food_name}
    [Documentation]    Tape un terme dans la barre de recherche
    Wait Until Element Is Visible    ${HOME_SEARCH_BAR}    ${MEDIUM_TIMEOUT}
    Click Element                    ${HOME_SEARCH_BAR}
    Input Text                       ${HOME_SEARCH_BAR}    ${food_name}
    Hide Keyboard
    Log     Recherche effectuée : ${food_name}

Clear Search Bar
    [Documentation]    Efface le contenu de la barre de recherche
    Wait Until Element Is Visible    ${HOME_SEARCH_BAR}    ${MEDIUM_TIMEOUT}
    Clear Text                       ${HOME_SEARCH_BAR}
    Log    Barre de recherche vidée
Join Us Should Be Visible
    [Documentation]    Vérifie que "Join Us" est visible après clic sur Login
    Wait Until Element Is Visible    ${LOGIN_JOIN_US}    ${MEDIUM_TIMEOUT}
    Log    "Join Us" visible — page Login bien affichée