// Gradle build for the LineageOS Messaging app, which upstream only builds with Soong (Android.bp).
// Overlaid on the upstream tree by scripts/losforgos.py. The helper libraries Android.bp lists as
// static_libs are modules under libs/ (see settings.gradle.kts); the app sources, resources and
// assets are upstream's own.

plugins {
    id("com.android.application") version "8.13.0"
}

android {
    // Upstream's package name, kept so that the Java sources and R keep working; the installed
    // application id is renamed below by scripts/losforgos.py.
    namespace = "com.android.messaging"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.losforgos.messaging"
        minSdk = 33
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        ndk {
            abiFilters += setOf("arm64-v8a", "armeabi-v7a", "x86_64", "x86")
        }
        externalNativeBuild {
            cmake {
                arguments += listOf("-DANDROID_STL=c++_static", "-DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON")
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("CMakeLists.txt")
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets {
        getByName("main") {
            manifest.srcFile("AndroidManifest.xml")
            java.setSrcDirs(listOf("src"))
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
        jniLibs {
            // Extracted libraries are not needed; the APK keeps them page aligned.
            useLegacyPackaging = false
        }
    }
}

// Collect every error instead of stopping at the first hundred.
tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.addAll(listOf("-Xmaxerrs", "5000", "-Xmaxwarns", "5000"))
}

dependencies {
    implementation(project(":colorpicker"))
    implementation(project(":chips"))
    implementation(project(":photoviewer"))
    implementation(project(":vcard"))

    implementation("androidx.activity:activity:1.9.3")
    implementation("androidx.annotation:annotation:1.9.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.collection:collection:1.4.5")
    implementation("androidx.core:core:1.15.0")
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    implementation("androidx.fragment:fragment:1.8.5")
    implementation("androidx.media:media:1.7.0")
    implementation("androidx.palette:palette:1.0.0")
    implementation("androidx.preference:preference:1.2.1")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.viewpager:viewpager:1.0.0")
    implementation("com.google.android.material:material:1.12.0")

    implementation("com.google.guava:guava:33.2.1-android")
    implementation("com.googlecode.libphonenumber:libphonenumber:9.0.41")
}
