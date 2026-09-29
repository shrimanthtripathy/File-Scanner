# FileRisk Scanner - build the APK without installing anything

1. Create a free account at github.com and make a **new repository** (any name).
2. Click **Add file > Upload files**, drag in EVERYTHING from this folder
   (main.py, filerisk.py, buildozer.spec, README.md and the hidden `.github` folder), then Commit.
   Tip: if the hidden .github folder won't upload, use **Add file > Create new file**, type
   `.github/workflows/build.yml` as the name and paste the contents of that file.
3. Open the **Actions** tab. "Build APK" runs automatically (first build takes ~20-40 min).
4. When it turns green, open the run, scroll to **Artifacts**, download **FileRisk-APK**, unzip it.
5. Copy the .apk to your phone, open it, allow "Install unknown apps", install.
6. On first launch, allow **All files access**, then tap SCAN.

Notes: debug-signed APK for personal use. The app works fully offline (no cloud hash lookup).
