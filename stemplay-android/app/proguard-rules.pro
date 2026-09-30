# StemPlay Android - ProGuard Rules
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.stemplay.library.** { *; }
-dontwarn com.google.zxing.**
