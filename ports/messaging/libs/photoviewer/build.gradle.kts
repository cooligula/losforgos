// Library module for the AOSP helper library fetched into this directory (see apps.toml).
plugins {
    id("com.android.library")
}

android {
    namespace = "com.android.ex.photo"
    compileSdk = 36

    defaultConfig {
        minSdk = 33
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets {
        getByName("main") {
            manifest.srcFile("AndroidManifest.xml")
            java.setSrcDirs(listOf("src", "activity/src"))
            res.setSrcDirs(listOf("res", "activity/res"))
        }
    }

    lint {
        abortOnError = false
    }
}

dependencies {
    implementation("androidx.annotation:annotation:1.9.1")
    implementation("androidx.collection:collection:1.4.5")
    implementation("androidx.core:core:1.15.0")
    implementation("androidx.fragment:fragment:1.8.5")
    implementation("androidx.loader:loader:1.1.0")
    implementation("androidx.viewpager:viewpager:1.0.0")
}
