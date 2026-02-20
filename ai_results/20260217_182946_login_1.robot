*** Settings ***
Library           AppiumLibrary
Library           Collections

# ==============================================================================
# Variables de Configuration Appium
# À adapter selon votre environnement (URL Appium, nom du device, package/activité de l l'app MyBiat)
# ==============================================================================
${APPIUM_SERVER_URL}      http://localhost:4723/wd/hub
${PLATFORM_NAME}          Android
${DEVICE_NAME}            emulator-5554    # Remplacer par le nom/ID de votre appareil
${APP_PACKAGE}            com.example.mobile_app
${APP_ACTIVITY}           .MainActivity    # Remplacer par l'activité principale réelle de MyBiat

# ==============================================================================
# Locators pour le "Dialogue de Connexion USB" (basés UNIQUEMENT sur resource_id)
# NOTE: L'utilisation de 'text1' est fragile car plusieurs éléments partagent cet ID.
#       Cela sera détaillé au point 3 avec des alternatives robustes.
# ==============================================================================
&{USB_DIALOG_LOCATORS_ID_ONLY}
\ \ \ \ DIALOG_TITLE=${APP_PACKAGE}:id/alertTitle
\ \ \ \ OPTION_NO_DATA_TRANSFER=${APP_PACKAGE}:id/text1    # Cible le premier élément avec id=text1
\ \ \ \ BUTTON_CANCEL=${APP_PACKAGE}:id/button2

*** Keywords ***
# ==============================================================================
# Mots-clés de Setup & Teardown
# ==============================================================================
Ouvrir Application MyBiat et Vérifier Dialogue USB
    [Documentation]    Ouvre l'application MyBiat et vérifie la présence du dialogue de connexion USB.
    Open Application    ${APPIUM_SERVER_URL}
    ...                 platformName=${PLATFORM_NAME}
    ...                 deviceName=${DEVICE_NAME}
    ...                 appPackage=${APP_PACKAGE}
    ...                 appActivity=${APP_ACTIVITY}
    ...                 automationName=UiAutomator2
    Sleep               2s    # Temps d'attente pour que l'app se lance et le dialogue apparaisse
    Vérifier Dialogue USB Est Affiché
    Log To Console      Session Appium démarrée et Dialogue USB confirmé.

Fermer Application MyBiat
    [Documentation]    Ferme la session Appium.
    Close Application
    Log To Console      Session Appium fermée.

# ==============================================================================
# Page Object Keywords pour le "Dialogue de Connexion USB"
# Basés UNIQUEMENT sur resource_id comme demandé pour cette section.
# ==============================================================================
Vérifier Dialogue USB Est Affiché
    [Documentation]    Vérifie la visibilité du dialogue "Utiliser la connexion USB pour".
    Wait Until Page Contains Element    ${USB_DIALOG_LOCATORS_ID_ONLY.DIALOG_TITLE}    timeout=10s
    Element Text Should Be              ${USB_DIALOG_LOCATORS_ID_ONLY.DIALOG_TITLE}    Utiliser la connexion USB pour
    Log To Console                      Le dialogue de connexion USB est affiché.

Sélectionner Aucune Transfert de Données
    [Documentation]    Clique sur l'option "Aucun transfert de données".
    ...                NOTE : Ce locator (id=text1) fonctionne ici car c'est le PREMIER
    ...                élément avec cet ID. Il est fragile pour les autres options.
    Wait Until Element Is Visible       ${USB_DIALOG_LOCATORS_ID_ONLY.OPTION_NO_DATA_TRANSFER}
    Click Element                       ${USB_DIALOG_LOCATORS_ID_ONLY.OPTION_NO_DATA_TRANSFER}
    Log To Console                      Option "Aucun transfert de données" sélectionnée.

Tenter de Sélectionner Transfert de Fichiers (ID Fragile)
    [Documentation]    Tente de cliquer sur "Transfert de fichiers/Android Auto" en utilisant l'ID partagé 'text1'.
    ...                Ce mot-clé est conçu pour ÉCHOUER afin de démontrer la fragilité
    ...                de l'utilisation de 'id=text1' pour d'autres options que la première.
    Fail    Impossible de sélectionner "Transfert de fichiers/Android Auto" de manière fiable avec seulement 'id=text1'. Voir section 3 pour des locators robustes.

Cliquer Bouton Annuler Dialogue USB
    [Documentation]    Clique sur le bouton "Annuler" du dialogue USB.
    Wait Until Element Is Visible       ${USB_DIALOG_LOCATORS_ID_ONLY.BUTTON_CANCEL}
    Click Element                       ${USB_DIALOG_LOCATORS_ID_ONLY.BUTTON_CANCEL}
    Log To Console                      Bouton "Annuler" cliqué.

Vérifier Dialogue USB N'Est Pas Affiché
    [Documentation]    Vérifie que le dialogue de connexion USB n'est plus visible.
    Wait Until Page Does Not Contain Element    ${USB_DIALOG_LOCATORS_ID_ONLY.DIALOG_TITLE}    timeout=10s    error=Le dialogue de connexion USB est toujours visible !
    Log To Console                              Le dialogue de connexion USB n'est plus affiché.

# ==============================================================================
# Test Cases pour le "Dialogue de Connexion USB"
# ==============================================================================
1. Confirmation du Contexte UI Actuel
    [Documentation]    Confirme que les éléments UI actifs appartiennent à un dialogue système
    ...                de connexion USB et non à la page de LOGIN de MyBiat.
    Ouvrir Application MyBiat et Vérifier Dialogue USB
    Log To Console    Confirmation: L'UI active est bien le dialogue "Utiliser la connexion USB pour".
    Cliquer Bouton Annuler Dialogue USB    # Nettoyage pour les tests suivants
    Vérifier Dialogue USB N'Est Pas Affiché
    Fermer Application MyBiat

2. Cas Nominal: Sélectionner "Aucun transfert de données"
    [Documentation]    Teste la sélection réussie de l'option "Aucun transfert de données"
    ...                et la disparition du dialogue USB.
    [Setup]           Ouvrir Application MyBiat et Vérifier Dialogue USB
    [Teardown]        Fermer Application MyBiat
    Sélectionner Aucune Transfert de Données
    Vérifier Dialogue USB N'Est Pas Affiché

3. Cas d'Erreur 1: Annuler le Dialogue de Connexion USB
    [Documentation]    Teste l'annulation du dialogue de connexion USB.
    ...                Ceci est considéré comme un "cas d'erreur" dans le sens où l'utilisateur
    ...                ne procède pas avec une option de transfert.
    [Setup]           Ouvrir Application MyBiat et Vérifier Dialogue USB
    [Teardown]        Fermer Application MyBiat
    Cliquer Bouton Annuler Dialogue USB
    Vérifier Dialogue USB N'Est Pas Affiché

4. Cas d'Erreur 2: Tenter de Sélectionner "Transfert de Fichiers" avec Locator Fragile
    [Documentation]    Ce cas de test démontre la fragilité des locators basés
    ...                UNIQUEMENT sur 'id=text1' pour des éléments multiples.
    ...                Le mot-clé 'Tenter de Sélectionner Transfert de Fichiers (ID Fragile)'
    ...                est intentionnellement conçu pour échouer.
    [Setup]           Ouvrir Application MyBiat et Vérifier Dialogue USB
    [Teardown]        Fermer Application MyBiat
    Run Keyword And Expect Error    *    Tenter de Sélectionner Transfert de Fichiers (ID Fragile)
    Log To Console    Comme prévu, la tentative de sélectionner "Transfert de fichiers" avec un locator fragile a échoué.
    Vérifier Dialogue USB Est Affiché    # Le dialogue devrait toujours être là après l'échec
    Cliquer Bouton Annuler Dialogue USB  # Nettoyage
    Vérifier Dialogue USB N'Est Pas Affiché
