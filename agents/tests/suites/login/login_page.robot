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