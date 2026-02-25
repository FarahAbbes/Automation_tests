# Agent Appium — Workflow: analyze
_Page: menu | 25/02/2026 02:20_

Bonjour ! En tant qu'expert en automatisation de tests mobiles, j'ai analysé la page "MENU" de votre application Android. Voici mon rapport détaillé et les fichiers d'automatisation demandés.

---

### 1. CONFIRMATION DE LA PAGE

La page affichée est bien la page **MENU**.
Sur cet écran, l'utilisateur peut explorer les différentes catégories de plats (ex: "All", "Pasta", "Pizza") ou rechercher des articles spécifiques. Il peut également consulter les détails des produits comme "tacos" ou "pasta" et les ajouter potentiellement à un panier, dont le contenu est indiqué par un compteur.

---

### 2. GÉNÉRATION PAGE OBJECT (POM)

Voici le fichier `menu_page.robot` structuré selon le modèle demandé, incluant les locators de la page et des mots-clés réutilisables. Pour les locators `missing` ou `fragile`, j'ai utilisé les informations disponibles (souvent des XPath génériques) comme base pour le POM, en attendant de proposer des alternatives plus robustes dans la section 4.

```robot
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
```

---

### 3. GÉNÉRATION TEST CASES

Voici le fichier `test_menu.robot` avec trois scénarios distincts, utilisant les mots-clés du Page Object.

```robot
# test_menu.robot
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
TC-MENU-01 Rechercher et ajouter un article au panier (Nominal)
    [Documentation]    Vérifie la recherche d'un article existant et son ajout au panier.
    [Tags]             menu    smoke    happy_path
    Open Menu Page
    Enter Search Text    pasta
    # Attendre que la liste des articles se mette à jour pour afficher 'pasta'
    Wait Until Page Contains Element    ${LOC_ITEM_PASTA_DETAILS}    timeout=${DEFAULT_TIMEOUT}
    Select Food Item     pasta
    # Ici, l'application devrait naviguer vers une page de détails ou afficher un modal.
    # Pour ce test, nous simulerons un retour au menu si l'ajout n'est pas sur une page dédiée.
    # Si l'ajout au panier est directement sur la page menu, nous pouvons directement cliquer sur "Add Item To Cart"
    # Supposons que l'ajout se fait sur la page actuelle sans navigation vers une page de détail complexe.
    Click Add To Cart Button For Item    pasta
    ${cart_count}=    Get Current Cart Count
    Should Be Equal As Integers    ${cart_count}    1    Panier devrait contenir 1 article.

TC-MENU-02 Recherche d'article inexistant (Cas d'erreur)
    [Documentation]    Vérifie le comportement de l'application lors de la recherche d'un article non existant.
    [Tags]             menu    error_case
    Open Menu Page
    Enter Search Text    nonexistent_item_xyz
    # Attendre un court instant pour que l'application traite la recherche
    Sleep    2s
    # Vérifier l'absence d'articles de produits ou la présence d'un message "aucun résultat"
    Page Should Not Contain Element    ${LOC_ANY_PRODUCT_ITEM}    timeout=5s    Les articles ne devraient pas être affichés.
    # Page Should Contain Element    ${LOC_NO_RESULTS_TEXT}    timeout=5s    # Décommenter si un message spécifique est affiché

TC-MENU-03 Recherche vide et navigation par catégorie (Cas limite)
    [Documentation]    Vérifie qu'une recherche vide ne casse pas l'affichage et que la navigation par catégorie fonctionne.
    [Tags]             menu    edge_case
    Open Menu Page
    Enter Search Text    ${EMPTY}    # Saisir une chaîne vide
    # Vérifier que la page affiche toujours les catégories et les articles par défaut.
    Wait Until Page Contains Element    ${LOC_CAT_ALL}    timeout=${DEFAULT_TIMEOUT}
    Wait Until Page Contains Element    ${LOC_ITEM_TACOS_DETAILS}    timeout=${DEFAULT_TIMEOUT}

    Select Category    Pizza
    # Attendre que la page se mette à jour pour afficher uniquement les pizzas
    Wait Until Page Contains Element    ${LOC_ITEM_NEPTUNE_PIZZA_DETAILS}    timeout=${DEFAULT_TIMEOUT}
    Page Should Not Contain Element    ${LOC_ITEM_TACOS_DETAILS}    timeout=5s    Les tacos ne devraient plus être visibles après le filtre Pizza.

*** Keywords ***
Open Application For Tests
    [Documentation]    Ouvre l'application mobile avec Appium.
    Open Application    ${APPIUM_URL}
    ...    platformName=Android
    ...    platformVersion=${PLATFORM_VERSION}
    ...    deviceName=${DEVICE_NAME}
    ...    appPackage=${APP_PACKAGE}
    ...    appActivity=${APP_ACTIVITY}
    ...    automationName=UiAutomator2
    ...    noReset=true
    ...    autoGrantPermissions=true
```

---

### 4. RECOMMANDATIONS SELF-HEALING

Voici des propositions de locators alternatifs plus robustes pour chaque élément identifié comme `fragile` ou `missing`, en privilégiant la stabilité et l'unicité.

1.  **Élément**: Bouton Hamburger (haut gauche)
    *   **Locator actuel (fragile)**: `${LOC_BTN_HAMBURGER_MENU} xpath=(//android.widget.ImageView)[1]`
    *   **Problème**: Basé sur l'index générique d'une `ImageView`, très sensible aux changements dans la structure UI.
    *   **Recommandation**:
        *   **Idéal (à vérifier avec les développeurs / Appium Inspector)**: `accessibility id="Open navigation drawer"` ou `accessibility id="Menu"`
        *   **Alternative (si un `resource-id` est disponible)**: `id=com.example.mobile_app:id/menu_icon`
        *   **XPath plus robuste (si les deux précédents manquent)**: `xpath=//android.widget.Toolbar/android.widget.ImageView[1]` (si c'est dans une barre d'outils) ou `xpath=//android.view.ViewGroup/android.view.ViewGroup/android.widget.ImageView[1]` (en utilisant un parent plus stable).

2.  **Élément**: Bouton Cloche (Notifications, haut droite)
    *   **Locator actuel (fragile)**: `${LOC_BTN_NOTIFICATIONS} xpath=(//android.widget.ImageView)[2]`
    *   **Problème**: Similaire au bouton Hamburger, basé sur un index générique.
    *   **Recommandation**:
        *   **Idéal (à vérifier)**: `accessibility id="Notifications"` ou `accessibility id="Alerts"`
        *   **Alternative (si un `resource-id` est disponible)**: `id=com.example.mobile_app:id/notification_bell_icon`
        *   **XPath plus robuste**: `xpath=//android.widget.Toolbar/android.widget.ImageView[last()]` ou `xpath=//android.view.ViewGroup/android.view.ViewGroup/android.widget.ImageView[last()]`.

3.  **Élément**: Champ de recherche ("What would you like to have?")
    *   **Locator actuel (fragile)**: `${LOC_INPUT_SEARCH} xpath=//android.widget.EditText`
    *   **Problème**: Très générique, pourrait cibler d'autres champs `EditText` si la page en contient. Le message `reason` "Basé sur le texte visible — sensible aux traductions" est erroné ici, car le locator est juste basé sur la classe.
    *   **Recommandation**:
        *   **Idéal**: `accessibility id="What would you like to have?"` (le texte de placeholder est souvent exposé comme `accessibility id`).
        *   **Alternative (si un `resource-id` est disponible)**: `id=com.example.mobile_app:id/search_input_field`
        *   **XPath plus robuste**: `xpath=//android.widget.EditText[@text='What would you like to have?']` (si le placeholder est dans l'attribut `text` après inspection) ou `xpath=//android.widget.EditText[contains(@content-desc, 'what would you like')]`.

4.  **Élément**: Bouton "Ajouter au panier" pour "tacos" (icône fourchette/couteau)
    *   **Locator actuel (fragile)**: `${LOC_BTN_ADD_TACOS} xpath=(//android.widget.Button)[1]`
    *   **Problème**: Basé sur un index générique, très susceptible de changer et non spécifique à l'article "tacos".
    *   **Recommandation**:
        *   **Idéal**: `accessibility id="Add Tacos to cart"` ou `accessibility id="Add to cart for Tacos"`
        *   **Alternative (si un `resource-id` est disponible)**: `id=com.example.mobile_app:id/add_tacos_button`
        *   **XPath plus robuste (relatif à l'article "tacos")**: `xpath=//android.view.ViewGroup[contains(@content-desc, 'tacos\ntacos chaneb')]//android.widget.Button` (en supposant que le bouton est enfant de la carte d'article).

5.  **Élément**: Bouton "Ajouter au panier" pour "pasta" (icône fourchette/couteau)
    *   **Locator actuel (fragile)**: `${LOC_BTN_ADD_PASTA} xpath=(//android.widget.Button)[2]`
    *   **Problème**: Similaire au bouton "tacos", basé sur un index générique.
    *   **Recommandation**:
        *   **Idéal**: `accessibility id="Add Pasta to cart"` ou `accessibility id="Add to cart for Pasta"`
        *   **Alternative (si un `resource-id` est disponible)**: `id=com.example.mobile_app:id/add_pasta_button`
        *   **XPath plus robuste (relatif à l'article "pasta")**: `xpath=//android.view.ViewGroup[contains(@content-desc, 'pasta\npastacosi')]//android.widget.Button`.

Ces recommandations nécessitent une inspection manuelle des éléments avec Appium Inspector (ou un outil similaire) pour vérifier la disponibilité des `resource-id`, `content-desc` ou des attributs `text` précis pour construire les locators les plus robustes possible.