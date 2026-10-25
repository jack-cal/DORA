import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins { id("com.android.application"); kotlin("android"); id("com.chaquo.python") }

kotlin { compilerOptions { jvmTarget.set(JvmTarget.JVM_17) } }

android {

    namespace="org.sumuww.miner"; compileSdk=35

    ndkVersion="27.2.12479018"

    packaging { jniLibs { useLegacyPackaging = true; keepDebugSymbols += setOf("**/libtor.so", "**/libi2pd_exec.so") } }

    externalNativeBuild { cmake { path=file("src/main/cpp/CMakeLists.txt"); version="3.22.1" } }

    compileOptions { sourceCompatibility=JavaVersion.VERSION_17; targetCompatibility=JavaVersion.VERSION_17 }

    defaultConfig {

        applicationId="org.sumuww.miner"; minSdk=26; targetSdk=35

        versionCode=156; versionName="0.6.96"

        ndk { abiFilters += listOf("arm64-v8a","x86_64") }

        testInstrumentationRunner="androidx.test.runner.AndroidJUnitRunner"

    }

    buildTypes {

        getByName("release") { isMinifyEnabled=false }

        create("compatible") {

            initWith(getByName("release")); isDebuggable=false

            signingConfig=signingConfigs.getByName("debug")

            matchingFallbacks += listOf("release")

        }

    }

    testBuildType="compatible"
    testOptions { unitTests.isIncludeAndroidResources = true }

}

chaquopy { defaultConfig {

    version="3.13"; buildPython(System.getenv("SUMUWW_BUILD_PYTHON") ?: "python")

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

    androidTestImplementation("androidx.test:runner:1.6.2")

    androidTestImplementation("androidx.test.ext:junit:1.2.1")

}


// Isolated verification package only when explicitly requested by the audit build.
if (providers.gradleProperty("sumuwwAudit").orNull == "true") {
    android.buildTypes.getByName("compatible") { applicationIdSuffix = ".audit" }
}
