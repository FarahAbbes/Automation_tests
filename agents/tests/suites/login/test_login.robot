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