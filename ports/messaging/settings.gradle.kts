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

rootProject.name = "Messaging"

// The AOSP helper libraries the Messaging Android.bp lists as static_libs. They are fetched next to
// the app by `losforgos.py fetch` (the `deps` of the messaging entry in apps.toml) and built here
// as library modules, each with its own R class.
include(":colorpicker", ":chips", ":photoviewer", ":vcard")
project(":colorpicker").projectDir = file("libs/colorpicker")
project(":chips").projectDir = file("libs/chips")
project(":photoviewer").projectDir = file("libs/photoviewer")
project(":vcard").projectDir = file("libs/vcard")

// The fetched AOSP libraries ship their own legacy build.gradle (Groovy, `compile` configuration, no
// compileSdk), which Gradle would pick over the build.gradle.kts of this port. Name the file.
for (name in listOf("colorpicker", "chips", "photoviewer", "vcard")) {
    project(":$name").buildFileName = "build.gradle.kts"
}
