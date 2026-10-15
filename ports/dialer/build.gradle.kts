// Gradle build for the LineageOS Dialer, which upstream only builds with Soong (Android.bp).
// Overlaid on the upstream tree by scripts/losforgos.py. The resource directories and the
// per-package R classes are read from upstream's Android.bp so that this stays in sync.

plugins {
    id("com.android.application") version "8.13.0"
    id("com.google.protobuf") version "0.9.4"
}

val androidBp = file("Android.bp").readText()

// The first android_app module lists the overlay resource directories, in order.
val resDirs: List<String> = Regex("resource_dirs:\\s*\\[(.*?)]", RegexOption.DOT_MATCHES_ALL)
    .find(androidBp)!!.groupValues[1]
    .let { block -> Regex("\"([^\"]+)\"").findAll(block).map { it.groupValues[1] }.toList() }

android {
    namespace = "com.android.dialer"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.losforgos.dialer"
        minSdk = 34
        targetSdk = 35
        versionCode = 1
        versionName = "23.0"
    }

    buildFeatures {
        aidl = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets {
        getByName("main") {
            manifest.srcFile("AndroidManifest.xml")
            java.setSrcDirs(listOf("java"))
            aidl.setSrcDirs(listOf("java"))
            res.setSrcDirs(resDirs)
            assets.setSrcDirs(listOf("assets"))
        }
    }

    buildTypes {
        getByName("release") {
            // Keep shrinking off: with it on, calls and Recents broke (classes that the Dialer loads
            // by name, via reflection and Dagger, were removed). Revisit with proper keep rules.
            isMinifyEnabled = false
            isShrinkResources = false
            proguardFiles(
                getDefaultProguardFile("proguard-android.txt"),
                "java/com/android/dialer/common/proguard.flags",
                "java/com/android/dialer/proguard/proguard.flags",
                "java/com/android/dialer/proguard/proguard_base.flags",
                "java/com/android/dialer/proguard/proguard_release.flags",
                "java/com/android/incallui/answer/impl/proguard.flags",
                "java/com/android/voicemail/impl/proguard.flags",
                "proguard.flags",
            )
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

protobuf {
    protoc {
        artifact = "com.google.protobuf:protoc:3.25.5"
    }
    generateProtoTasks {
        all().forEach { task ->
            task.builtins {
                create("java") { option("lite") }
            }
        }
    }
}

// Collect every error instead of stopping at the first hundred.
tasks.withType<JavaCompile>().configureEach {
    // The annotation processor sources live in :rootprocessor, not in the app.
    exclude("**/rootcomponentgenerator/*.java")
    options.compilerArgs.addAll(listOf("-Xmaxerrs", "5000", "-Xmaxwarns", "5000"))
}

dependencies {
    implementation("androidx.activity:activity:1.9.3")
    implementation("androidx.annotation:annotation:1.9.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.cardview:cardview:1.0.0")
    implementation("androidx.collection:collection:1.4.5")
    implementation("androidx.coordinatorlayout:coordinatorlayout:1.2.0")
    implementation("androidx.core:core:1.15.0")
    implementation("androidx.dynamicanimation:dynamicanimation:1.0.0")
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    implementation("androidx.fragment:fragment:1.8.5")
    implementation("androidx.interpolator:interpolator:1.0.0")
    implementation("androidx.loader:loader:1.1.0")
    implementation("androidx.localbroadcastmanager:localbroadcastmanager:1.1.0")
    implementation("androidx.preference:preference:1.2.1")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.viewpager:viewpager:1.0.0")
    implementation("com.google.android.material:material:1.12.0")

    implementation("com.google.guava:guava:33.2.1-android")
    implementation("com.googlecode.libphonenumber:libphonenumber:9.0.41")
    implementation("com.googlecode.libphonenumber:geocoder:3.41")
    implementation("com.android.volley:volley:1.2.1")
    implementation("org.apache.commons:commons-compress:1.27.1")
    implementation("com.google.protobuf:protobuf-javalite:3.25.5")
    implementation(files(
        "prebuilts/apache-mime4j-core-0.8.9.jar",
        "prebuilts/apache-mime4j-dom-0.8.9.jar",
    ))

    implementation("javax.inject:javax.inject:1")
    implementation("com.google.code.findbugs:jsr305:3.0.2")
    implementation("com.google.errorprone:error_prone_annotations:2.36.0")

    implementation("com.google.dagger:dagger:2.51.1")
    annotationProcessor("com.google.dagger:dagger-compiler:2.51.1")

    compileOnly("com.google.auto.value:auto-value-annotations:1.10.4")
    annotationProcessor("com.google.auto.value:auto-value:1.10.4")

    implementation("com.github.bumptech.glide:glide:4.16.0")
    annotationProcessor("com.github.bumptech.glide:compiler:4.16.0")

    annotationProcessor(project(":rootprocessor"))
}
