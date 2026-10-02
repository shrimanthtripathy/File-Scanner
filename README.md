<img width="400" height="400" alt="ss1 (3)" src="https://github.com/user-attachments/assets/82c5100b-5369-4403-b500-240c1a297a61" />
<img width="400" height="400" alt="ss1 (4)" src="https://github.com/user-attachments/assets/0519eda6-0643-4980-b16e-22784ebbf814" />
<img width="400" height="400" alt="ss1 (2)" src="https://github.com/user-attachments/assets/3b5a0069-9de6-4601-9b81-c2ee5f60abf5" />
<img width="400" height="400" alt="ss1 (1)" src="https://github.com/user-attachments/assets/913d3402-c41e-4d16-9d89-135615159f5e" />

**A free, offline file risk scanner for Android and PC.**
Pick a folder, and FileRisk checks each file's real contents and gives it a risk score from 0 to 100 with plain-language reasons.

> **Status:** early release. FileRisk is a static analysis tool: it reports *risk indicators*, not a guarantee of safety. It is not a replacement for a full antivirus.

---

## ✨ Features

- **Detects the real file type** from the file's first bytes, not its extension, so `invoice.pdf` that is really an `.exe` gets caught.
- **Risk score (0-100)** with levels: Clean, Low, Medium, High, Critical.
- **Reasons for every finding**, so you can see *why* a file was flagged.
- **Summary statistics:** counts and percentages per risk level, breakdown by file type, and the top 10 riskiest files.
- **Works offline.** Your files never leave your device.
- **Export reports** to JSON or CSV (command-line version).
- **Optional hash lookup** on VirusTotal (command-line version, only the SHA-256 hash is sent, never the file).

## 📂 Supported file types

| Type | What is checked |
|---|---|
| **APK** | Dangerous permission combinations (SMS, accessibility, device admin, overlay), missing or debug signing, dynamic code loading, hardcoded IP URLs, APK/DEX files hidden in assets |
| **PDF** | Embedded JavaScript, auto-run and launch actions, embedded files, truncated or malformed structure |
| **PPT / PPTX** | VBA macros, embedded objects, external references, executables inside the package, zip-bomb patterns |
| **PNG / JPG / JPEG** | Data appended after the image ends, embedded executables or scripts |
| **MP4 / MOV / AVI / MP3** | Broken container structure, hidden or appended payloads |
| **Any file** | Extension mismatch, double extensions (`photo.jpg.exe`), right-to-left filename tricks, entropy (packed or encrypted data), SHA-256 hash |

## 📊 How scoring works

Each finding adds points, and the total is capped at 100.

| Score | Level |
|---|---|
| 0-20 | 🟢 Clean |
| 21-45 | 🟡 Low |
| 46-70 | 🟠 Medium |
| 71-99 | 🔴 High |
| 100 / known-bad hash | ⛔ Critical |

Examples: a file whose type doesn't match its extension adds +30, a disguised executable adds +40, and embedded PDF JavaScript adds +25.

## 📱 Install on Android

1. Open the **Actions** tab of this repository and choose the latest successful **Build APK** run.
2. Download the **FileRisk-APK** artifact at the bottom of the page and unzip it.
3. Copy the `.apk` to your phone and open it. Allow **Install unknown apps** when asked.
4. On first launch, allow **All files access**, then tap **SCAN**.

> The APK is debug-signed and intended for personal use, so Play Protect may show a warning.

## 💻 Use on PC (command line)

Requires Python 3.8+ and no extra packages.

```bash
python filerisk.py <file-or-folder> -r --csv report.csv --json report.json
```

| Option | Meaning |
|---|---|
| `-r` | Scan subfolders |
| `--all` | Scan every file, not just the supported types |
| `--blocklist hashes.txt` | Flag files whose SHA-256 is in your list |
| `--vt` | Look up hashes on VirusTotal (needs the `VT_API_KEY` environment variable) |
| `-v` | Show clean files too |

## 🧱 Project structure

```
├── filerisk.py        # Scanning engine (pure Python, standard library only)
├── main.py            # Kivy app: the Android/PC interface
├── buildozer.spec     # Android build settings
└── .github/workflows/build.yml   # Builds the APK automatically on GitHub
```

## 🔨 Build the APK yourself

Push to this repository: the **Build APK** workflow compiles the app with Buildozer on GitHub's servers (about 10-25 minutes) and attaches the APK to the run.

## 🔒 Privacy

- All scanning runs **locally** on your device.
- No files are uploaded. The Android app makes no network requests.
- The optional VirusTotal lookup (command line only) sends only a file's hash.

## ⚠️ Limitations

- Static analysis can miss new or heavily obfuscated malware, and can flag harmless files. Treat results as a guide.
- "No threats found" does **not** mean "guaranteed safe."
- The scanner does not delete or quarantine files.
- Not yet tested across a wide range of Android devices.

## 🗺️ Roadmap

- [ ] Quarantine risky files (move, don't delete)
- [ ] Automatically scan new downloads in the background
- [ ] Export reports from the Android app
- [ ] App icon and charts
- [ ] Optional machine-learning model for structure-based detection

## 🤝 Contributing

Issues and pull requests are welcome. If you find a false positive or a file type that should be checked, open an issue with the finding code shown in the report (for example, `TYPE_MISMATCH` or `PDF_JS`).

