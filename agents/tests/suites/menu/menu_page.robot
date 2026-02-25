# menu_page.robot
*** Settings ***
Library           AppiumLibrary

*** Variables ***
# Locators des éléments interactifs
# Missing/Fragile locators (à améliorer en priorité)
${LOC_BTN_HAMBURGER_MENU}       xpath=(//android.widget.ImageView)[1]
${LOC_BTN_NOTIFICATIONS}        xpath=(//android.widget.ImageView)[2]
${LOC_INPUT_SEARCH}             xpath=//android.widget.EditText
${LOC_BTN_ADD_TACOS}            xpath=(//android.widget.Button)[1]
${LOC_BTN_ADD_PASTA}            xpath=(//android.widget.Button)[2]

# Robust locators
${LOC_CAT_ALL}                  accessibility id=All
${LOC_CAT_PASTA}                accessibility id=Pasta
${LOC_CAT_SANDWICH}             accessibility id=sandwich
${LOC_CAT_PIZZA}                accessibility id=pizza

${LOC_ITEM_TACOS_DETAILS}       accessibility id=tacos\ntacos chaneb\n4.5\n10.0 DT
${LOC_ITEM_PASTA_DETAILS}       accessibility id=pasta\npastacosi\n4.5\n10.0 DT
${LOC_ITEM_NEPTUNE_PIZZA_DETAILS}    accessibility id=neptune\npizza\n4.5\n10.0 DT

${LOC_BTN_CART_COUNTER}         accessibility id=0
${LOC_TAB_MENU}                 accessibility id=Menu\nTab 1 of 2
${LOC_TAB_LOGIN}                accessibility id=Login\nTab 2 of 2

# Locators pour la vérification des résultats de recherche ou messages d'erreur (à adapter si nécessaire)
${LOC_NO_RESULTS_TEXT}          xpath=//android.widget.TextView[contains(@text, 'No results found')]
${LOC_ANY_PRODUCT_ITEM}         xpath=//android.view.ViewGroup[contains(@content-desc, 'DT')]


*** Keywords ***
Open Menu Page
    [Documentation]    Vérifie que la page menu est affichée en attendant le champ de recherche.
    Wait Until Page Contains Element    ${LOC_INPUT_SEARCH}    timeout=10s

Click Hamburger Menu
    [Documentation]    Clique sur le bouton du menu hamburger.
    Click Element    ${LOC_BTN_HAMBURGER_MENU}

Enter Search Text
    [Arguments]    ${text}
    [Documentation]    Saisit du texte dans le champ de recherche.
    Input Text    ${LOC_INPUT_SEARCH}    ${text}

Select Category
    [Arguments]    ${category_name}
    [Documentation]    Clique sur une catégorie donnée (All, Pasta, Sandwich, Pizza).
    Run Keyword If    '${category_name}' == 'All'        Click Element    ${LOC_CAT_ALL}
    ...    ELSE IF    '${category_name}' == 'Pasta'      Click Element    ${LOC_CAT_PASTA}
    ...    ELSE IF    '${category_name}' == 'Sandwich'   Click Element    ${LOC_CAT_SANDWICH}
    ...    ELSE IF    '${category_name}' == 'Pizza'      Click Element    ${LOC_CAT_PIZZA}
    ...    ELSE                                          Fail    Catégorie non reconnue : ${category_name}

Select Food Item
    [Arguments]    ${item_name}
    [Documentation]    Clique sur un article alimentaire spécifique pour voir ses détails.
    Run Keyword If    '${item_name}' == 'tacos'         Click Element    ${LOC_ITEM_TACOS_DETAILS}
    ...    ELSE IF    '${item_name}' == 'pasta'         Click Element    ${LOC_ITEM_PASTA_DETAILS}
    ...    ELSE IF    '${item_name}' == 'neptune'       Click Element    ${LOC_ITEM_NEPTUNE_PIZZA_DETAILS}
    ...    ELSE                                         Fail    Article non reconnu : ${item_name}

Add Item To Cart
    [Arguments]    ${item_name}
    [Documentation]    Clique sur le bouton "Ajouter au panier" pour un article.
    Run Keyword If    '${item_name}' == 'tacos'         Click Element    ${LOC_BTN_ADD_TACOS}
    ...    ELSE IF    '${item_name}' == 'pasta'         Click Element    ${LOC_BTN_ADD_PASTA}
    ...    ELSE                                         Fail    Bouton d'ajout au panier non défini pour : ${item_name}

Get Current Cart Count
    [Documentation]    Récupère le nombre d'articles dans le panier.
    ${count}=    Get Text    ${LOC_BTN_CART_COUNTER}
    Return From Keyword    ${count}

Navigate To Login Tab
    [Documentation]    Clique sur l'onglet 'Login' en bas de l'écran.
    Click Element    ${LOC_TAB_LOGIN}