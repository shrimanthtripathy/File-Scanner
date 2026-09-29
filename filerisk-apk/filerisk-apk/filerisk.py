#!/usr/bin/env python3
"""
FileRisk - local static file risk scanner (Python 3.8+, standard library only).
Runs on Windows / macOS / Linux / Android (Termux, Chaquopy, Kivy).

Usage:
  python filerisk.py <file-or-folder> [-r] [--all] [--json out.json] [--csv out.csv]
                     [--blocklist hashes.txt] [--vt] [-v]
  --vt uses env VT_API_KEY; only the SHA-256 hash is sent, never the file.

Library use:  from filerisk import scan_file;  scan_file("x.apk")
Note: static analysis gives risk indicators, not a guarantee of safety.
"""
import argparse, csv, hashlib, json, math, mmap, os, re, struct, sys, time, zipfile
import urllib.request, urllib.error
from collections import Counter

SUPPORTED = {"apk", "pdf", "ppt", "pptx", "png", "jpg", "jpeg", "mp4", "mp3", "avi", "mov"}
EXT_KINDS = {"pdf": {"pdf"}, "png": {"png"}, "jpg": {"jpg"}, "jpeg": {"jpg"},
             "mp4": {"mp4", "mov"}, "mov": {"mov", "mp4"}, "avi": {"avi"}, "mp3": {"mp3"},
             "apk": {"apk"}, "pptx": {"pptx"}, "ppt": {"ole"}}
EXEC_KINDS = {"exe", "elf", "script", "dex"}
NOENTROPY = {"mp4", "mov", "avi", "mp3", "jpg", "png", "zip", "apk", "pptx", "pdf", "docx", "xlsx", "jar"}
DOUBLE_EXT = re.compile(r"\.(jpe?g|png|pdf|pptx?|mp[34]|avi|mov|docx?|xlsx?|txt)\."
                        r"(exe|scr|bat|cmd|com|js|vbs|apk|jar|msi|ps1|lnk)$", re.I)
APK_PERMS = {"SEND_SMS": 10, "READ_SMS": 10, "RECEIVE_SMS": 8, "BIND_ACCESSIBILITY_SERVICE": 15,
             "BIND_DEVICE_ADMIN": 15, "SYSTEM_ALERT_WINDOW": 10, "REQUEST_INSTALL_PACKAGES": 10,
             "BIND_NOTIFICATION_LISTENER_SERVICE": 12, "READ_CALL_LOG": 6, "MANAGE_EXTERNAL_STORAGE": 5,
             "READ_CONTACTS": 4, "RECORD_AUDIO": 4, "CALL_PHONE": 4, "READ_PHONE_STATE": 3,
             "CAMERA": 3, "ACCESS_FINE_LOCATION": 3, "RECEIVE_BOOT_COMPLETED": 2}
MAX_READ = 64 * 1024 * 1024


class Scan:
    def __init__(self):
        self.findings = []

    def add(self, pts, code, msg):
        self.findings.append({"points": pts, "code": code, "message": msg})


def level_of(score, critical=False):
    if critical or score >= 100: return "Critical"
    if score >= 71: return "High"
    if score >= 46: return "Medium"
    if score >= 21: return "Low"
    return "Clean"


def detect(h):
    if h.startswith(b"%PDF-"): return "pdf"
    if h.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if h[:3] == b"\xff\xd8\xff": return "jpg"
    if h[:2] == b"MZ": return "exe"
    if h[:4] == b"\x7fELF": return "elf"
    if h[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": return "ole"
    if h[:4] == b"dex\n": return "dex"
    if h[:4] == b"RIFF" and h[8:12] == b"AVI ": return "avi"
    if h[4:8] == b"ftyp": return "mov" if h[8:12] == b"qt  " else "mp4"
    if h[:2] == b"PK" and h[2:4] in (b"\x03\x04", b"\x05\x06"): return "zip"
    if h[:2] == b"#!": return "script"
    if h[:3] == b"ID3" or (len(h) > 1 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0): return "mp3"
    return "unknown"


def entropy(data):
    if not data: return 0.0
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in Counter(data).values())


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def vt_lookup(sha, key):
    req = urllib.request.Request(f"https://www.virustotal.com/api/v3/files/{sha}", headers={"x-apikey": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)["data"]["attributes"]["last_analysis_stats"]
    except urllib.error.HTTPError as e:
        return {"unknown": True} if e.code == 404 else None
    except Exception:
        return None


def trailing_check(s, m, end, size, label):
    extra = size - end
    if extra <= 0: return
    tail = bytes(m[end:end + 4096])
    if tail.startswith((b"MZ", b"\x7fELF", b"PK\x03\x04", b"#!")) or b"This program cannot" in tail \
            or b"<script" in tail.lower() or b"powershell" in tail.lower():
        s.add(40, "HIDDEN_PAYLOAD", f"{label}: {extra:,} bytes of executable/script-like data appended after end of file")
    elif extra > 1024:
        s.add(15, "APPENDED_DATA", f"{label}: {extra:,} unexplained bytes appended after end of file")


# ---------------- analyzers ----------------
def an_pdf(s, m, size):
    data = bytes(m[:min(size, 32 * 1024 * 1024)])
    js = re.search(rb"/(JavaScript|JS)\b", data)
    auto = re.search(rb"/(OpenAction|AA)\b", data)
    if js: s.add(25, "PDF_JS", "Contains embedded JavaScript")
    if auto: s.add(15 if js else 5, "PDF_AUTOACTION", "Has an action that runs automatically on open")
    if re.search(rb"/Launch\b", data): s.add(35, "PDF_LAUNCH", "Can launch external programs (/Launch)")
    if re.search(rb"/EmbeddedFile\b", data): s.add(20, "PDF_EMBEDDED", "Contains embedded file(s)")
    if re.search(rb"/(RichMedia|XFA)\b", data): s.add(15, "PDF_ACTIVE", "Uses RichMedia/XFA (legacy active content)")
    n = len(re.findall(rb"/URI\b", data))
    if n > 10: s.add(10, "PDF_MANYURI", f"{n} external links")
    if b"%%EOF" not in bytes(m[max(0, size - 1024):]): s.add(10, "PDF_TRUNC", "Missing %%EOF marker (truncated or malformed)")


def an_ole(s, m, size):
    data = bytes(m[:min(size, 32 * 1024 * 1024)])
    if b"V\x00B\x00A\x00" in data or b"_VBA_PROJECT" in data or b"Macros" in data:
        s.add(30, "OLE_MACRO", "Legacy Office file contains macro (VBA) markers")


def zip_common(s, z):
    infos = z.infolist()
    total = sum(i.file_size for i in infos)
    comp = sum(i.compress_size for i in infos) or 1
    if total > 1 << 30 or (total > 100 << 20 and total / comp > 200):
        s.add(30, "ZIP_BOMB", f"Extreme compression ratio ({total/comp:.0f}x): possible zip bomb")
    if any(i.filename.startswith("/") or ".." in i.filename.split("/") for i in infos):
        s.add(20, "ZIP_PATH", "Archive has path-traversal entry names")
    return infos


def an_pptx(s, z, infos):
    names = [i.filename for i in infos]
    low = [n.lower() for n in names]
    if any("vbaproject.bin" in n for n in low): s.add(40, "PPT_MACRO", "Contains VBA macros")
    if any("/embeddings/" in n for n in low): s.add(20, "PPT_EMBED", "Contains embedded objects (OLE/packages)")
    if any(n.endswith((".exe", ".dll", ".bat", ".js", ".vbs", ".ps1")) for n in low):
        s.add(40, "PPT_EXEC", "Contains an executable/script file inside the package")
    for i in infos:
        if i.filename.endswith(".rels") and i.file_size < 2_000_000:
            t = z.read(i.filename)
            if re.search(rb'TargetMode="External"', t) and re.search(rb"(oleObject|attachedTemplate|externalLink|package)", t):
                s.add(25, "PPT_EXTLINK", f"External non-hyperlink reference in {i.filename}")
                break


def an_apk(s, z, infos, m, size):
    names = [i.filename for i in infos]
    man = z.read("AndroidManifest.xml") if "AndroidManifest.xml" in names else b""
    found = {}
    for p, w in APK_PERMS.items():
        tag = "android.permission." + p
        if tag.encode() in man or tag.encode("utf-16le") in man: found[p] = w
    if found:
        pts = min(35, sum(found.values()))
        s.add(pts, "APK_PERMS", "Sensitive permissions: " + ", ".join(sorted(found)))
    if "READ_SMS" in found and "BIND_ACCESSIBILITY_SERVICE" in found:
        s.add(10, "APK_COMBO", "SMS + accessibility combination is typical of banking trojans")
    signed = any(re.match(r"META-INF/.+\.(RSA|DSA|EC)$", n, re.I) for n in names) or b"APK Sig Block 42" in bytes(m[-(1 << 20):])
    if not signed: s.add(20, "APK_UNSIGNED", "No signing certificate found")
    for n in names:
        if re.match(r"META-INF/.+\.(RSA|DSA|EC)$", n, re.I) and b"Android Debug" in z.read(n):
            s.add(25, "APK_DEBUGCERT", "Signed with an Android debug certificate")
    dex_hits = set()
    for i in infos:
        if re.fullmatch(r"classes\d*\.dex", i.filename) and i.file_size <= MAX_READ:
            d = z.read(i.filename)
            if b"dalvik/system/DexClassLoader" in d: dex_hits.add("DexClassLoader")
            if re.search(rb"https?://\d{1,3}(\.\d{1,3}){3}", d): dex_hits.add("hardcoded IP URL")
    if "DexClassLoader" in dex_hits: s.add(10, "APK_DYNLOAD", "Loads code dynamically at runtime (DexClassLoader)")
    if "hardcoded IP URL" in dex_hits: s.add(10, "APK_IPURL", "Contains hardcoded IP-address URLs")
    if any(re.search(r"^assets/.*\.(apk|dex|jar|so)$", n, re.I) for n in names):
        s.add(15, "APK_PAYLOAD", "Ships another APK/DEX/JAR inside assets (possible dropper)")
    if not any(re.fullmatch(r"classes\d*\.dex", n) for n in names):
        s.add(15, "APK_NODEX", "No classes.dex found: unusual for an APK")


def an_image(s, m, size, kind):
    if kind == "jpg":
        i = m.rfind(b"\xff\xd9")
        if i < 0: s.add(15, "IMG_TRUNC", "JPEG end marker missing")
        else: trailing_check(s, m, i + 2, size, "JPEG")
    else:
        i = m.rfind(b"IEND")
        if i < 0: s.add(15, "IMG_TRUNC", "PNG IEND chunk missing")
        else: trailing_check(s, m, i + 8, size, "PNG")
    low = bytes(m[:min(size, 16 * 1024 * 1024)]).lower()
    if b"<script" in low or b"<?php" in low:
        s.add(40, "IMG_SCRIPT", "Script code (HTML/PHP) found inside image data")


def an_mp4(s, m, size):
    pos, boxes = 0, []
    while pos + 8 <= size and len(boxes) < 20000:
        sz, typ = struct.unpack(">I4s", bytes(m[pos:pos + 8]))
        hdr = 8
        if sz == 1:
            if pos + 16 > size: break
            sz, hdr = struct.unpack(">Q", bytes(m[pos + 8:pos + 16]))[0], 16
        elif sz == 0: sz = size - pos
        if sz < hdr or not re.fullmatch(rb"[ -~\xa9]{4}", typ):
            s.add(25, "MEDIA_MALFORMED", f"Invalid MP4/MOV box structure at byte {pos:,}")
            trailing_check(s, m, pos, size, "MP4/MOV")
            return
        boxes.append(typ); pos += sz
    if pos > size: s.add(5, "MEDIA_TRUNC", "File is shorter than its header claims (truncated)")
    elif len(boxes) < 20000: trailing_check(s, m, pos, size, "MP4/MOV")
    if b"moov" not in boxes and b"moof" not in boxes: s.add(10, "MEDIA_NOMOOV", "No movie metadata box (moov)")


def an_avi(s, m, size):
    riff = struct.unpack("<I", bytes(m[4:8]))[0] + 8
    if size > riff: trailing_check(s, m, riff, size, "AVI")
    elif size < riff: s.add(5, "MEDIA_TRUNC", "AVI is shorter than declared (truncated)")


def an_mp3(s, m, size):
    pos = 0
    if bytes(m[:3]) == b"ID3" and size >= 10:
        b = bytes(m[6:10]); pos = 10 + ((b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3])
    win = bytes(m[pos:pos + 4096])
    if not re.search(rb"\xff[\xe0-\xff]", win):
        s.add(25, "MEDIA_MALFORMED", "No valid MP3 audio frame found after header")


# ---------------- main scan ----------------
def scan_file(path, vt_key=None, blocklist=frozenset()):
    r = {"path": path, "name": os.path.basename(path), "size": 0, "ext": "", "kind": "unknown",
         "sha256": "", "entropy": 0.0, "score": 0, "level": "Clean", "findings": []}
    s = Scan(); critical = False
    try:
        size = os.path.getsize(path); r["size"] = size
        name = r["name"]; ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        r["ext"] = ext
        r["sha256"] = sha256_of(path)
        if r["sha256"] in blocklist:
            s.add(100, "HASH_BLOCKLIST", "Hash is on your malware blocklist"); critical = True
        if vt_key:
            st = vt_lookup(r["sha256"], vt_key)
            if st is None: s.add(0, "VT_ERROR", "VirusTotal lookup failed (offline or rate-limited)")
            elif st.get("unknown"): s.add(0, "VT_UNKNOWN", "Hash not known to VirusTotal (not proof of safety)")
            elif st.get("malicious", 0) >= 3:
                s.add(100, "VT_MALICIOUS", f"{st['malicious']} engines flag this file as malicious"); critical = True
            elif st.get("malicious", 0) >= 1:
                s.add(40, "VT_SUSPICIOUS", f"{st['malicious']} engine(s) flag this file")
        if RLO in name: s.add(30, "RLO_NAME", "Filename uses a right-to-left override character to hide its true extension")
        if DOUBLE_EXT.search(name): s.add(30, "DOUBLE_EXT", "Double extension (e.g. photo.jpg.exe) disguises the real file type")
        if size == 0:
            s.add(0, "EMPTY", "File is empty")
        else:
            with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                kind = detect(bytes(m[:32]))
                z = infos = None
                if kind == "zip":
                    try:
                        z = zipfile.ZipFile(path); infos = zip_common(s, z)
                        names = [i.filename for i in infos]
                        if "AndroidManifest.xml" in names: kind = "apk"
                        elif any(n.startswith("ppt/") for n in names): kind = "pptx"
                        elif any(n.startswith("word/") for n in names): kind = "docx"
                        elif any(n.startswith("xl/") for n in names): kind = "xlsx"
                        elif any(n.endswith(".class") for n in names): kind = "jar"
                    except zipfile.BadZipFile:
                        s.add(20, "ZIP_BAD", "Corrupt or malformed ZIP structure")
                r["kind"] = kind
                if ext in EXT_KINDS and kind not in EXT_KINDS[ext]:
                    s.add(30, "TYPE_MISMATCH", f"Extension .{ext} but content is really '{kind}'")
                    if kind in EXEC_KINDS: s.add(40, "DISGUISED_EXEC", "An executable is disguised as a document/media file")
                elif kind in ("exe", "elf") and ext not in ("exe", "dll", "so", "elf", ""):
                    s.add(40, "DISGUISED_EXEC", "An executable is disguised as another file type")
                elif kind in ("exe", "elf"):
                    s.add(25, "EXECUTABLE", "File is a native executable")
                if kind not in ("exe", "elf", "apk", "zip", "jar", "dex") and ext in SUPPORTED \
                        and m.find(b"This program cannot be run in DOS mode") > 0:
                    s.add(40, "EMBEDDED_EXE", "A Windows executable is embedded inside this file")
                if kind == "pdf": an_pdf(s, m, size)
                elif kind == "ole": an_ole(s, m, size)
                elif kind == "pptx": an_pptx(s, z, infos)
                elif kind == "apk": an_apk(s, z, infos, m, size)
                elif kind in ("jpg", "png"): an_image(s, m, size, kind)
                elif kind in ("mp4", "mov"): an_mp4(s, m, size)
                elif kind == "avi": an_avi(s, m, size)
                elif kind == "mp3": an_mp3(s, m, size)
                elif kind == "unknown" and ext in EXT_KINDS:
                    s.add(20, "UNRECOGNIZED", f"Content does not match any known .{ext} format")
                if z: z.close()
                if kind not in NOENTROPY:
                    e = entropy(bytes(m[:1 << 20])); r["entropy"] = round(e, 2)
                    if e > 7.5 and size > 4096: s.add(15, "HIGH_ENTROPY", f"Very high entropy ({e:.2f}/8): packed or encrypted content")
                else:
                    r["entropy"] = round(entropy(bytes(m[:1 << 20])), 2)
    except Exception as ex:
        r["level"] = "Error"; s.add(0, "ERROR", f"Could not scan: {ex}")
        r["findings"] = s.findings
        return r
    r["score"] = min(100, sum(f["points"] for f in s.findings))
    r["level"] = level_of(r["score"], critical)
    r["findings"] = s.findings
    return r


RLO = "\u202e"


def collect(target, recursive, scan_all):
    if os.path.isfile(target):
        yield target; return
    for root, dirs, files in os.walk(target):
        for f in files:
            p = os.path.join(root, f)
            if os.path.islink(p): continue
            if scan_all or f.rsplit(".", 1)[-1].lower() in SUPPORTED: yield p
        if not recursive: break


def stats(results, secs):
    total = len(results) or 1
    lv = Counter(r["level"] for r in results)
    bt = {}
    for r in results:
        d = bt.setdefault(r["kind"], {"count": 0, "score_sum": 0})
        d["count"] += 1; d["score_sum"] += r["score"]
    return {"total_files": len(results), "total_bytes": sum(r["size"] for r in results),
            "seconds": round(secs, 2),
            "by_level": {k: {"count": v, "percent": round(100 * v / total, 1)} for k, v in lv.items()},
            "by_type": {k: {"count": v["count"], "avg_score": round(v["score_sum"] / v["count"], 1)} for k, v in bt.items()},
            "top_risky": [{"path": r["path"], "score": r["score"], "level": r["level"]}
                          for r in sorted(results, key=lambda x: -x["score"])[:10] if r["score"] > 0]}


def main():
    ap = argparse.ArgumentParser(description="Local static file risk scanner")
    ap.add_argument("target"); ap.add_argument("-r", "--recursive", action="store_true")
    ap.add_argument("--all", action="store_true", help="scan every file, not just supported types")
    ap.add_argument("--json"); ap.add_argument("--csv"); ap.add_argument("--blocklist")
    ap.add_argument("--vt", action="store_true"); ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    bl = set()
    if a.blocklist:
        with open(a.blocklist) as f: bl = {l.strip().lower() for l in f if l.strip()}
    key = os.environ.get("VT_API_KEY") if a.vt else None
    if a.vt and not key: print("VT_API_KEY not set; skipping cloud lookup", file=sys.stderr)
    t0 = time.time(); results = []
    for p in collect(a.target, a.recursive, a.all):
        r = scan_file(p, key, bl); results.append(r)
        if a.verbose or r["level"] != "Clean":
            print(f"[{r['level'].upper():8}] {r['score']:3}  {p}  ({r['kind']}, {r['size']:,} B)")
            for f in r["findings"]: print(f"            +{f['points']:<3} {f['message']}")
    st = stats(results, time.time() - t0)
    print(f"\n=== Summary: {st['total_files']} files, {st['total_bytes']/1e6:.1f} MB, {st['seconds']}s ===")
    for lvl in ("Critical", "High", "Medium", "Low", "Clean", "Error"):
        if lvl in st["by_level"]:
            d = st["by_level"][lvl]; print(f"{lvl:9}{d['count']:6}  {d['percent']:5.1f}%  {'#' * int(d['percent'] / 2)}")
    print("\nBy type:", ", ".join(f"{k}: {v['count']} (avg {v['avg_score']})" for k, v in st["by_type"].items()))
    print("\nNo threats found does not mean 'guaranteed safe': static checks can miss new malware.")
    if a.json:
        with open(a.json, "w") as f: json.dump({"stats": st, "results": results}, f, indent=2)
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["path", "kind", "size", "sha256", "entropy", "score", "level", "reasons"])
            for r in results: w.writerow([r["path"], r["kind"], r["size"], r["sha256"], r["entropy"], r["score"],
                                          r["level"], " | ".join(x["message"] for x in r["findings"])])


if __name__ == "__main__":
    main()
