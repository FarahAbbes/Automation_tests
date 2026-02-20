*** Settings ***
Documentation    Suite de tests : HomePage
...              Locators validés  via Appium Inspector
...              Couvre : affichage, catégories, recherche, navigation

Library         AppiumLibrary
Resource        ../../resources/AppVariables.robot
Resource        ../../resources/GlobalKeywords.robot
Resource        ../../resources/pages/HomePage.robot

Suite Setup      Open FoodApp
Suite Teardown   Close FoodApp
Test Teardown    Run Keyword If Test Failed    Capture Page Screenshot

*** Test Cases ***
# SCENARIO 1 : Affichage de la HomePage au lancement

TC-HOME-001 : HomePage doit être affichée au lancement
    [Documentation]    Vérifie que tous les éléments principaux sont visibles
    [Tags]    home    smoke
    Home Page Should Be Displayed

TC-HOME-002 : La barre de recherche doit être visible et active
    [Documentation]    Vérifie que la barre de recherche est présente et cliquable
    [Tags]    home    smoke
    Search Bar Should Be Visible

TC-HOME-003 : Les 4 catégories doivent être affichées
    [Documentation]    Vérifie All, Pasta, sandwich, pizza
    [Tags]    home    smoke
    All Categories Should Be Visible

TC-HOME-004 : La bottom navigation bar doit avoir Menu et Login
    [Documentation]    Vérifie les 2 onglets en bas de l'écran
    [Tags]    home    smoke
    Bottom Nav Bar Should Be Visible
# SCENARIO 2 : Clic sur les catégories

TC-HOME-005 : Clic sur la catégorie All
    [Documentation]    Vérifie que la catégorie All est cliquable
    [Tags]    home    categories
    Click Category All
    Home Page Should Be Displayed

TC-HOME-006 : Clic sur la catégorie Pasta
    [Documentation]    Vérifie que la catégorie Pasta est cliquable
    [Tags]    home    categories
    Click Category Pasta
    Home Page Should Be Displayed

TC-HOME-007 : Clic sur la catégorie sandwich
    [Documentation]    Vérifie que la catégorie sandwich est cliquable
    [Tags]    home    categories
    Click Category Sandwich
    Home Page Should Be Displayed

TC-HOME-008 : Clic sur la catégorie pizza
    [Documentation]    Vérifie que la catégorie pizza est cliquable
    [Tags]    home    categories
    Click Category Pizza
    Home Page Should Be Displayed

TC-HOME-009 : Retour sur All après avoir cliqué une catégorie
    [Documentation]    Vérifie que All réaffiche bien tous les plats
    [Tags]    home    categories
    Click Category Pasta
    Click Category All
    Home Page Should Be Displayed

# SCENARIO 3 : Barre de recherche

TC-HOME-010 : La barre de recherche accepte une saisie
    [Documentation]    Vérifie qu'on peut taper du texte dans la recherche
    [Tags]    home    search
    Search Food    tacos
    Search Bar Should Be Visible

TC-HOME-011 : La barre de recherche peut être vidée
    [Documentation]    Vérifie qu'on peut effacer la recherche
    [Tags]    home    search
    Search Food    pasta
    Clear Search Bar
    Search Bar Should Be Visible

# SCENARIO 4 : Navigation vers Login

TC-HOME-012 : Clic sur Login Tab affiche la page "Join Us"
    [Documentation]    Clique sur Login et vérifie que
    ...                "Join Us" devient visible à l'écran
    [Tags]    home    navigation    smoke
    Click Login Tab
    Join Us Should Be Visible

TC-HOME-013 : Retour sur Menu Tab revient à la HomePage
    [Documentation]    Vérifie que l'onglet Menu ramène à la HomePage
    [Tags]    home    navigation    smoke
    Click Menu Tab
    Home Page Should Be Displayed
