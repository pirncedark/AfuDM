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
        maven { url = uri("https://jitpack.io") }
    }
}

rootProject.name = "AfuTube"

include(":app")
include(":core")
include(":extractor")
include(":downloader")
include(":media")
include(":updater")
include(":feature:home")
include(":feature:formats")
include(":feature:downloads")
include(":feature:history")
include(":feature:settings")
