# Agent Appium — Workflow: analyze
_Page: login | 25/02/2026 01:32_

Salut l'équipe,

En tant qu'expert en automatisation avec Robot Framework et Appium, j'ai analysé la page **LOGIN** de l'application "MyBiat Retail". Voici mon rapport détaillé et les fichiers d'automatisation demandés.

---

### 1. CONFIRMATION DE LA PAGE

L'identification de la page comme `LOGIN` est **confirmée**.
Sur cet écran, l'utilisateur peut s'authentifier en fournissant ses identifiants et mot de passe, ou demander une réinitialisation de son mot de passe s'il l'a oublié.

### 2. GÉNÉRATION PAGE OBJECT (POM)

Voici le fichier `login_page.robot` pour gérer les éléments de la page de connexion.

```robot
*** Settings ***
Library           AppiumLibrary

*** Variables ***
${LOC_USERNAME_FIELD}           id=com.example.mobile_app:id/edit_username
${LOC_PASSWORD_FIELD}           id=com.example.mobile_app:id/edit_password
${LOC_REMEMBER_ME_CHECKBOX}     id=com.example.mobile_app:id/cb_remember_me
${LOC_LOGIN_BUTTON}             id=com.example.mobile_app:id/btn_login
${LOC_FORGOT_PASSWORD_LINK}     id=com.example.mobile_app:id/tv_forgot_password
${LOC_ERROR_MESSAGE_EMPTY_FIELDS}     xpath=//*[@text='Veuillez renseigner tous les champs.']
${LOC_ERROR_MESSAGE_INVALID_CREDENTIALS}    xpath=//*[@text='Identifiants ou mot de passe incorrects.']
${LOC_SUCCESS_MESSAGE_HOME_PAGE}    xpath=//*[@text='Bienvenue sur votre espace.']


*** Keywords ***
Open Login Page
    [Documentation]    Attend que la page de connexion soit affichée.
    Wait Until Page Contains Element    ${LOC_LOGIN_BUTTON}    timeout=10s    error=La page de connexion n'a pas été trouvée.

Enter Username
    [Documentation]    Saisit un nom d'utilisateur dans le champ dédié.
    [Arguments]    ${username}
    Input Text    ${LOC_USERNAME_FIELD}    ${username}

Enter Password
    [Documentation]    Saisit un mot de passe dans le champ dédié.
    [Arguments]    ${password}
    Input Text    ${LOC_PASSWORD_FIELD}    ${password}

Check Remember Me
    [Documentation]    Clique sur la case "Se souvenir de moi".
    Click Element    ${LOC_REMEMBER_ME_CHECKBOX}

Click Login Button
    [Documentation]    Clique sur le bouton "Se connecter".
    Click Element    ${LOC_LOGIN_BUTTON}

Click Forgot Password Link
    [Documentation]    Clique sur le lien "Mot de passe oublié ?".
    Click Element    ${LOC_FORGOT_PASSWORD_LINK}

Login With Credentials
    [Documentation]    Effectue une tentative de connexion avec le nom d'utilisateur et le mot de passe fournis.
    [Arguments]    ${username}    ${password}
    Enter Username    ${username}
    Enter Password    ${password}
    Click Login Button

Verify Login Failed With Message
    [Documentation]    Vérifie qu'un message d'erreur spécifique est affiché après une tentative de connexion.
    [Arguments]    ${expected_message_locator}
    Wait Until Page Contains Element    ${expected_message_locator}    timeout=5s    error=Le message d'erreur attendu n'a pas été trouvé.

Verify Login Successful
    [Documentation]    Vérifie que l'utilisateur est redirigé vers la page d'accueil après une connexion réussie.
    Wait Until Page Contains Element    ${LOC_SUCCESS_MESSAGE_HOME_PAGE}    timeout=10s    error=La page d'accueil n'a pas été affichée après connexion.
```

### 3. GÉNÉRATION TEST CASES

Voici le fichier `test_login.robot` avec les scénarios demandés.

```robot
*** Settings ***
Library           AppiumLibrary
Resource          login_page.robot

*** Variables ***
${APPIUM_URL}       http://localhost:4723
${DEVICE_NAME}      emulator-5554
${APP_PACKAGE}      com.example.mobile_app
${APP_ACTIVITY}     .MainActivity
${VALID_USERNAME}   testuser
${VALID_PASSWORD}   Password123!
${INVALID_USERNAME} invalid
${INVALID_PASSWORD} wrong

*** Test Cases ***
TC-LOGIN-01 Happy Path Login With Valid Credentials
    [Documentation]    Vérifie que l'utilisateur peut se connecter avec des identifiants valides.
    [Tags]             login    smoke    happy_path
    Open Application For Tests
    Open Login Page
    Login With Credentials    ${VALID_USERNAME}    ${VALID_PASSWORD}
    Verify Login Successful
    [Teardown]    Close Application

TC-LOGIN-02 Error Case Login With Empty Fields
    [Documentation]    Vérifie qu'un message d'erreur apparaît lorsque les champs sont laissés vides.
    [Tags]             login    error_case
    Open Application For Tests
    Open Login Page
    Click Login Button    # Tente de se connecter sans renseigner les champs
    Verify Login Failed With Message    ${LOC_ERROR_MESSAGE_EMPTY_FIELDS}
    [Teardown]    Close Application

TC-LOGIN-03 Error Case Login With Invalid Credentials
    [Documentation]    Vérifie qu'un message d'erreur apparaît avec des identifiants incorrects.
    [Tags]             login    error_case
    Open Application For Tests
    Open Login Page
    Login With Credentials    ${INVALID_USERNAME}    ${INVALID_PASSWORD}
    Verify Login Failed With Message    ${LOC_ERROR_MESSAGE_INVALID_CREDENTIALS}
    [Teardown]    Close Application

TC-LOGIN-04 Edge Case Login With Whitespace Only Username
    [Documentation]    Vérifie le comportement de la connexion avec un nom d'utilisateur composé uniquement d'espaces.
    [Tags]             login    edge_case
    Open Application For Tests
    Open Login Page
    Enter Username    ${SPACE * 5}    # 5 espaces
    Enter Password    ${VALID_PASSWORD}
    Click Login Button
    # Assumons que cela mènera au même message d'erreur que les champs vides ou invalides
    Verify Login Failed With Message    ${LOC_ERROR_MESSAGE_INVALID_CREDENTIALS}
    [Teardown]    Close Application

*** Keywords ***
Open Application For Tests
    Open Application    ${APPIUM_URL}
    ...    platformName=Android
    ...    deviceName=${DEVICE_NAME}
    ...    appPackage=${APP_PACKAGE}
    ...    appActivity=${APP_ACTIVITY}
    ...    automationName=UiAutomator2
    ...    noReset=true
```

### 4. RECOMMANDATIONS SELF-HEALING

L'analyse des éléments UI a révélé que tous les locators fournis ont une `locator_quality` de "robust". Cela signifie qu'ils sont basés sur des attributs stables comme `resource_id`, `accessibility id`, ou des textes exacts qui sont généralement fiables et moins susceptibles de changer fréquemment avec les évolutions de l'interface.

Par conséquent, **aucun locator fragile ou manquant n'a été détecté**, et il n'est pas nécessaire de proposer des locators alternatifs robustes pour le moment. La couverture des locators est de 100%, ce qui est excellent.

Si des locators fragiles avaient été identifiés (par exemple, des XPath basés sur des index ou des classes génériques), les recommandations auraient inclus :
*   **Prioriser `resource_id` ou `content-desc` (accessibility id)** : Ces attributs sont les plus stables sur Android.
*   **Utiliser le texte visible** : `xpath=//*[@text='Mon Texte']` est une bonne alternative si le texte est unique et constant.
*   **Combiner des attributs** : `xpath=//android.widget.TextView[@resource-id='some_id' and @text='Mon Texte']`.
*   **Naviguer par des relations (parent/enfant, frère/sœur)** : `xpath=//android.widget.LinearLayout[@resource-id='parent_id']/*[1]` si l'ordre est stable.

Pour l'instant, les locators sont optimaux pour la robustesse.