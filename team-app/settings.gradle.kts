// The Sunbird team app (Android): rings when a traveller starts a chat on the website, and the team answers here.
// README.md in this folder says how to build it and put it on a phone.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "SunbirdTeam"
include(":app")
