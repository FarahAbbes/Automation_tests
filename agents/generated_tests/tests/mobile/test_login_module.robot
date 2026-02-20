*** Settings ***
Library           AppiumLibrary
Resource          ../../resources/pages/LoginPage.robot
Suite Setup       Open Application
Suite Teardown    Close Application
Test Teardown     Capture Page Screenshot
Test Template     Login With Invalid Credentials And Verify Error

*** Variables ***
${APPIUM_SERVER}                    http://localhost:4723
${PLATFORM_NAME}                    Android
${DEVICE_NAME}                      emulator-5554    # Replace with your actual device name or emulator ID
${PLATFORM_VERSION}                 12
${APP_PACKAGE}                      com.example.mobile_app
${APP_ACTIVITY}                     .MainActivity

${VALID_USERNAME}                   usertest@biat.com.tn
${VALID_PASSWORD}                   Test@1234
${INVALID_PASSWORD}                 wrong_password
${EMPTY_STRING}                     ${EMPTY}

${ERROR_MESSAGE_INVALID_CREDENTIALS}    Identifiant ou mot de passe incorrect.
${ERROR_MESSAGE_EMPTY_USERNAME}         Veuillez saisir votre identifiant.
${ERROR_MESSAGE_EMPTY_PASSWORD}         Veuillez saisir votre mot de passe.

*** Keywords ***
Open Application
    [Documentation]    Opens the mobile application with specified capabilities.
    Open Application    ${APPIUM_SERVER}
    ...                 platformName=${PLATFORM_NAME}
    ...                 deviceName=${DEVICE_NAME}
    ...                 platformVersion=${PLATFORM_VERSION}
    ...                 appPackage=${APP_PACKAGE}
    ...                 appActivity=${APP_ACTIVITY}
    ...                 noReset=True

Login With Invalid Credentials And Verify Error
    [Arguments]    ${username}    ${password}    ${expected_error}
    [Documentation]    Performs a login attempt with given credentials and verifies the error message.
    Wait Until Login Screen Is Visible
    Perform Login    ${username}    ${password}
    Verify Error Message Is Displayed    ${expected_error}

*** Test Cases ***
TC_LOGIN_001 - Successful Login with Valid Credentials
    [Documentation]    Verifies that a user can successfully log in with valid credentials.
    [Tags]    login    smoke    regression
    Wait Until Login Screen Is Visible
    Perform Login    ${VALID_USERNAME}    ${VALID_PASSWORD}
    Verify Login Successful

TC_LOGIN_002 - Login with Invalid Password
    [Documentation]    Verifies that an error message is displayed when logging in with an invalid password.
    [Tags]    login    negative
    ${VALID_USERNAME}    ${INVALID_PASSWORD}    ${ERROR_MESSAGE_INVALID_CREDENTIALS}

TC_LOGIN_003 - Login with Empty Username
    [Documentation]    Verifies that an error message is displayed when attempting to log in with an empty username.
    [Tags]    login    negative
    ${EMPTY_STRING}    ${VALID_PASSWORD}    ${ERROR_MESSAGE_EMPTY_USERNAME}

TC_LOGIN_004 - Login with Empty Password
    [Documentation]    Verifies that an error message is displayed when attempting to log in with an empty password.
    [Tags]    login    negative
    ${VALID_USERNAME}    ${EMPTY_STRING}    ${ERROR_MESSAGE_EMPTY_PASSWORD}

TC_LOGIN_005 - Login Button Disabled with Empty Fields
    [Documentation]    Verifies that the login button is disabled when both username and password fields are empty.
    [Tags]    login    regression    edge
    Wait Until Login Screen Is Visible
    Input Username    ${EMPTY_STRING}
    Input Password    ${EMPTY_STRING}
    Verify Login Button State    disabled

TC_LOGIN_006 - Navigate to Forgot Password Screen
    [Documentation]    Verifies that clicking the 'Forgot Password?' link navigates to the correct screen.
    [Tags]    login    regression
    Wait Until Login Screen Is Visible
    Click Forgot Password Link
    Verify Forgot Password Screen Is Visible
