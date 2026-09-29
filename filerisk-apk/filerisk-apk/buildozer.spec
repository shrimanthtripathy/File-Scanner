[app]
title = FileRisk Scanner
package.name = filerisk
package.domain = org.filerisk
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0
orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
