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

rootProject.name = "Contacts"

// The vcard library that the Contacts Android.bp lists as a static_lib. It is fetched next to the app
// by `losforgos.py fetch` (the `deps` of the contacts entry in apps.toml) and built here as a library
// module. Its legacy build.gradle (Groovy, `compile` configuration, no compileSdk) would be picked over
// the build.gradle.kts of this port, so the file is named.
include(":vcard")
project(":vcard").projectDir = file("libs/vcard")
project(":vcard").buildFileName = "build.gradle.kts"
