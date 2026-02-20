*** Settings ***
Library    AppiumLibrary

*** Variables ***
${LOCATOR_LOGIN_SCREEN_TITLE}       id=com.example.mobile_app:id/tv_title
${LOCATOR_USERNAME_FIELD}           id=com.example.mobile_app:id/edit_username
${LOCATOR_PASSWORD_FIELD}           id=com.example.mobile_app:id/edit_password
${LOCATOR_REMEMBER_ME_CHECKBOX}     id=com.example.mobile_app:id/cb_remember_me
${LOCATOR_LOGIN_BUTTON}             id=com.example.mobile_app:id/btn_login
${LOCATOR_FORGOT_PASSWORD_LINK}     id=com.example.mobile_app:id/tv_forgot_password
${LOCATOR_ERROR_MESSAGE}            id=com.example.mobile_app:id/tv_error_message
${LOCATOR_DASHBOARD_ROOT}           id=com.example.mobile_app:id/dashboard_root
${LOCATOR_FORGOT_PASSWORD_TITLE}    id=com.example.mobile_app:id/tv_forgot_password_title

*** Keywords ***
Wait Until Login Screen Is Visible
    [Documentation]    Waits until the login screen title is visible, indicating the screen is loaded.
    Wait Until Element Is Visible    ${LOCATOR_LOGIN_SCREEN_TITLE}    timeout=15s

Input Username
    [Arguments]    ${username}
    [Documentation]    Inputs the provided username into the username field.
    Wait Until Element Is Visible    ${LOCATOR_USERNAME_FIELD}    timeout=10s
    Clear Element Text               ${LOCATOR_USERNAME_FIELD}
    Input Text                       ${LOCATOR_USERNAME_FIELD}    ${username}

Input Password
    [Arguments]    ${password}
    [Documentation]    Inputs the provided password into the password field.
    Wait Until Element Is Visible    ${LOCATOR_PASSWORD_FIELD}    timeout=10s
    Clear Element Text               ${LOCATOR_PASSWORD_FIELD}
    Input Text                       ${LOCATOR_PASSWORD_FIELD}    ${password}

Click Login Button
    [Documentation]    Clicks the 'Se connecter' button.
    Wait Until Element Is Visible    ${LOCATOR_LOGIN_BUTTON}    timeout=10s
    Click Element                    ${LOCATOR_LOGIN_BUTTON}

Check Remember Me Checkbox
    [Documentation]    Checks the 'Se souvenir de moi' checkbox if not already checked.
    Wait Until Element Is Visible    ${LOCATOR_REMEMBER_ME_CHECKBOX}    timeout=10s
    Checkbox Should Be Unchecked     ${LOCATOR_REMEMBER_ME_CHECKBOX}
    Click Element                    ${LOCATOR_REMEMBER_ME_CHECKBOX}

Uncheck Remember Me Checkbox
    [Documentation]    Unchecks the 'Se souvenir de moi' checkbox if not already unchecked.
    Wait Until Element Is Visible    ${LOCATOR_REMEMBER_ME_CHECKBOX}    timeout=10s
    Checkbox Should Be Checked       ${LOCATOR_REMEMBER_ME_CHECKBOX}
    Click Element                    ${LOCATOR_REMEMBER_ME_CHECKBOX}

Click Forgot Password Link
    [Documentation]    Clicks the 'Mot de passe oublie ?' link.
    Wait Until Element Is Visible    ${LOCATOR_FORGOT_PASSWORD_LINK}    timeout=10s
    Click Element                    ${LOCATOR_FORGOT_PASSWORD_LINK}

Perform Login
    [Arguments]    ${username}    ${password}
    [Documentation]    Composite keyword to input username, password, and click login.
    Input Username    ${username}
    Input Password    ${password}
    Click Login Button

Verify Login Successful
    [Documentation]    Verifies that the user has successfully logged in by checking for the dashboard root element.
    Wait Until Element Is Visible    ${LOCATOR_DASHBOARD_ROOT}    timeout=15s
    Element Should Be Visible        ${LOCATOR_DASHBOARD_ROOT}

Verify Error Message Is Displayed
    [Arguments]    ${expected_message}
    [Documentation]    Verifies that an error message is displayed with the expected text.
    Wait Until Element Is Visible    ${LOCATOR_ERROR_MESSAGE}    timeout=10s
    Element Text Should Be           ${LOCATOR_ERROR_MESSAGE}    ${expected_message}

Verify Login Button State
    [Arguments]    ${expected_state}
    [Documentation]    Verifies if the login button is enabled or disabled.
    ...                Expected state can be 'enabled' or 'disabled'.
    Wait Until Element Is Visible    ${LOCATOR_LOGIN_BUTTON}    timeout=10s
    Run Keyword If                   '${expected_state}' == 'enabled'    Element Should Be Enabled    ${LOCATOR_LOGIN_BUTTON}
    Run Keyword If                   '${expected_state}' == 'disabled'   Element Should Be Disabled   ${LOCATOR_LOGIN_BUTTON}

Verify Forgot Password Screen Is Visible
    [Documentation]    Verifies that the Forgot Password screen is displayed.
    Wait Until Element Is Visible    ${LOCATOR_FORGOT_PASSWORD_TITLE}    timeout=15s
    Element Should Be Visible        ${LOCATOR_FORGOT_PASSWORD_TITLE}
