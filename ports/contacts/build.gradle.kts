// Gradle build for the LineageOS Contacts app, which upstream only builds with Soong (Android.bp).
// Overlaid on the upstream tree by scripts/losforgos.py. The app sources (Java and Kotlin), resources
// and assets are upstream's own. Of the static_libs of Android.bp, vcard is a module under libs/ (see
// settings.gradle.kts); the three small classes taken from PhoneCommon and frameworks/ex are copied
// into libs-src/ by prepare.py; the rest are the published androidx, material, guava and
// libphonenumber artifacts.

plugins {
    id("com.android.application") version "8.13.0"
    id("org.jetbrains.kotlin.android") version "2.2.20"
}

android {
    // Upstream's package name, kept so that the Java sources and R keep working; the installed
    // application id is renamed below by scripts/losforgos.py.
    namespace = "com.android.contacts"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.losforgos.contacts"
        minSdk = 34
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets {
        getByName("main") {
            manifest.srcFile("AndroidManifest.xml")
            java.setSrcDirs(listOf("src", "src-bind", "libs-src"))
            res.setSrcDirs(listOf("res"))
            assets.setSrcDirs(listOf("assets"))
        }
    }

    buildTypes {
        getByName("release") {
            // Shrinking stays off while the port is experimental (it broke the Dialer, which
            // loads classes by name). Revisit with upstream's proguard.flags once it works.
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }

    lint {
        abortOnError = false
        checkReleaseBuilds = false
    }

    packaging {
        resources.excludes += setOf("META-INF/DEPENDENCIES", "META-INF/LICENSE*", "META-INF/NOTICE*")
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

// Collect every error instead of stopping at the first hundred.
tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.addAll(listOf("-Xmaxerrs", "5000", "-Xmaxwarns", "5000"))
}

dependencies {
    implementation(project(":vcard"))

    implementation("androidx.annotation:annotation:1.9.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.cardview:cardview:1.0.0")
    implementation("androidx.core:core:1.15.0")
    implementation("androidx.legacy:legacy-support-v13:1.0.0")
    implementation("androidx.legacy:legacy-support-v4:1.0.0")
    implementation("androidx.localbroadcastmanager:localbroadcastmanager:1.1.0")
    implementation("androidx.palette:palette:1.0.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.transition:transition:1.5.1")
    implementation("com.google.android.material:material:1.12.0")

    implementation("com.google.code.findbugs:jsr305:3.0.2")
    implementation("com.google.guava:guava:33.2.1-android")
    implementation("com.googlecode.libphonenumber:libphonenumber:9.0.41")
    implementation("com.googlecode.libphonenumber:geocoder:3.41")
}
