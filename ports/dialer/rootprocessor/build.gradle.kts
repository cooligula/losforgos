plugins {
    `java-library`
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

sourceSets {
    main {
        java {
            srcDir("../java")
            include(
                "com/android/dialer/rootcomponentgenerator/*.java",
                "com/android/dialer/inject/HasRootComponent.java",
                "com/android/dialer/inject/IncludeInDialerRoot.java",
                "com/android/dialer/inject/RootComponentGeneratorMetadata.java",
            )
        }
    }
}

dependencies {
    implementation("com.google.auto:auto-common:1.2.2")
    implementation("com.google.auto.service:auto-service-annotations:1.1.1")
    annotationProcessor("com.google.auto.service:auto-service:1.1.1")
    implementation("com.google.dagger:dagger:2.51.1")
    implementation("com.google.guava:guava:33.2.1-jre")
    implementation("com.squareup:javapoet:1.13.0")
    implementation("javax.inject:javax.inject:1")
}
