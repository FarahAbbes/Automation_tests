*** Variables ***
# Configuration de l'environnement Appium
${REMOTE_APPIUM_URL}       http://localhost:4723/wd/hub
${PLATFORM_NAME}           Android
${ANDROID_VERSION}         11
${ANDROID_DEVICE_NAME}     emulator-5554
${APP_PATH}                ${CURDIR}/../apps/MyBiatRetail.apk  # Chemin vers votre APK
${AUTOMATION_NAME}         UiAutomator2
${APP_PACKAGE}             com.example.mobile_app  # Nom de package réel de l'application
${APP_ACTIVITY}            .MainActivity           # Activité de démarrage réelle de l'application
${NO_RESET}                True
${NEW_COMMAND_TIMEOUT}     60000

# Temps d'attente génériques
${GENERIC_TIMEOUT}         10s
${EXTENDED_TIMEOUT}        30s

# Variables pour les messages d'erreur attendus (à adapter selon l'application)
${ERROR_MESSAGE_EMPTY_FIELDS}      Email and password cannot be empty.
${ERROR_MESSAGE_INVALID_CREDENTIALS}  Invalid credentials.
${ERROR_MESSAGE_NETWORK_FAILURE}    Network connection failed.