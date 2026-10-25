import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    kotlin("android")
    id("com.chaquo.python")
}
kotlin { compilerOptions { jvmTarget.set(JvmTarget.JVM_17) } }
android {
    namespace = "org.sumuww.wallet"
    compileSdk = 35
    ndkVersion = "27.2.12479018"
    packaging { jniLibs { useLegacyPackaging = true; keepDebugSymbols += setOf("**/libtor.so", "**/libi2pd_exec.so") } }
    externalNativeBuild { cmake { path = file("src/main/cpp/CMakeLists.txt"); version = "3.22.1" } }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    defaultConfig {
        // A separate sandbox preserves the withdrawn wallet and its data.
        // Its original signing key is not present in this workspace.
        applicationId = "org.sumuww.wallet.current"
        minSdk = 26
        targetSdk = 35
        versionCode = 17
        versionName = "1.1.6"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildTypes { getByName("release") { isMinifyEnabled = false } }
    testOptions { unitTests.isIncludeAndroidResources = true }
    // Allows the signed release APK to be exercised on a physical device.
    if (providers.gradleProperty("releaseAudit").isPresent) testBuildType = "release"
}
chaquopy { defaultConfig {
    version = "3.13"
    buildPython(System.getenv("DORA_BUILD_PYTHON") ?: "python")
    pip {
        install("cryptography==42.0.8")
        install("py-ecc==8.0.0")
        install("eth-utils==2.3.1")
        install("eth-typing==3.5.2")
        install("cytoolz==1.0.0")
        install("PyNaCl==1.5.0")
    }
} }
dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
    implementation("com.google.zxing:core:3.5.3")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
}
