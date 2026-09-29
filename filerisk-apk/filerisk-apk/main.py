"""FileRisk Scanner - Android/PC UI (Kivy). Uses filerisk.py as the engine."""
import os, time, threading
from functools import partial
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform
import filerisk

COLORS = {"Clean": (.2, .6, .3, 1), "Low": (.6, .6, .1, 1), "Medium": (.85, .5, .1, 1),
          "High": (.8, .2, .2, 1), "Critical": (.55, .05, .3, 1), "Error": (.4, .4, .4, 1)}


def request_storage():
    """Ask for storage access; on Android 11+ open the 'All files access' screen."""
    if platform != "android":
        return
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
        from jnius import autoclass
        if autoclass("android.os.Build$VERSION").SDK_INT >= 30:
            if not autoclass("android.os.Environment").isExternalStorageManager():
                Intent = autoclass("android.content.Intent")
                Settings = autoclass("android.provider.Settings")
                Uri = autoclass("android.net.Uri")
                act = autoclass("org.kivy.android.PythonActivity").mActivity
                i = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                i.setData(Uri.parse("package:" + act.getPackageName()))
                act.startActivity(i)
    except Exception as e:
        print("permission error:", e)


class FileRiskApp(App):
    title = "FileRisk Scanner"

    def build(self):
        Window.clearcolor = (.08, .09, .11, 1)
        root = BoxLayout(orientation="vertical", padding=10, spacing=8)
        root.add_widget(Label(text="FileRisk Scanner", font_size="22sp", size_hint_y=None, height=44, bold=True))
        default = "/storage/emulated/0/Download" if platform == "android" else os.path.expanduser("~")
        self.path = TextInput(text=default, multiline=False, size_hint_y=None, height=44)
        root.add_widget(self.path)
        row = BoxLayout(size_hint_y=None, height=44, spacing=8)
        self.allbox = CheckBox(size_hint_x=None, width=44)
        row.add_widget(self.allbox)
        row.add_widget(Label(text="Scan all file types", halign="left"))
        self.btn = Button(text="SCAN", size_hint_x=.4, bold=True)
        self.btn.bind(on_release=self.start)
        row.add_widget(self.btn)
        root.add_widget(row)
        self.status = Label(text="Choose a folder and tap SCAN.", size_hint_y=None, height=70,
                            halign="left", valign="middle")
        self.status.bind(size=lambda w, s: setattr(w, "text_size", s))
        root.add_widget(self.status)
        sv = ScrollView()
        self.grid = GridLayout(cols=1, spacing=4, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        sv.add_widget(self.grid)
        root.add_widget(sv)
        return root

    def on_start(self):
        request_storage()

    def start(self, *_):
        if not os.path.exists(self.path.text):
            self.status.text = "Path not found. On Android, allow 'All files access' and check the path."
            return
        self.btn.disabled = True
        self.grid.clear_widgets()
        threading.Thread(target=self.work, args=(self.path.text, self.allbox.active), daemon=True).start()

    def work(self, target, scan_all):
        t0, results = time.time(), []
        for p in filerisk.collect(target, True, scan_all):
            results.append(filerisk.scan_file(p))
            Clock.schedule_once(partial(self.set_status, f"Scanned {len(results)} files...\n{os.path.basename(p)}"))
        st = filerisk.stats(results, time.time() - t0)
        Clock.schedule_once(partial(self.show, results, st))

    def set_status(self, text, *_):
        self.status.text = text

    def show(self, results, st, *_):
        self.btn.disabled = False
        lv = st["by_level"]
        line = "  ".join(f"{k}: {lv[k]['count']} ({lv[k]['percent']}%)"
                         for k in ("Critical", "High", "Medium", "Low", "Clean") if k in lv)
        self.status.text = f"Done: {st['total_files']} files in {st['seconds']}s\n{line or 'No files found.'}"
        for r in sorted(results, key=lambda x: -x["score"])[:300]:
            b = Button(text=f"[{r['level'].upper()}] {r['score']}  {r['name']}", size_hint_y=None, height=52,
                       background_normal="", background_color=COLORS.get(r["level"], (.3, .3, .3, 1)),
                       halign="left", shorten=True)
            b.bind(on_release=partial(self.detail, r))
            self.grid.add_widget(b)

    def detail(self, r, *_):
        why = "\n".join(f"+{f['points']}  {f['message']}" for f in r["findings"]) or "No risk indicators found."
        txt = (f"{r['path']}\n\nType: {r['kind']}   Size: {r['size']:,} B\nEntropy: {r['entropy']}\n"
               f"SHA-256:\n{r['sha256']}\n\nScore: {r['score']}/100 ({r['level']})\n\n{why}\n\n"
               "Static checks give risk indicators, not a guarantee of safety.")
        lab = Label(text=txt, size_hint_y=None, halign="left", valign="top")
        lab.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
        lab.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        sv = ScrollView(); sv.add_widget(lab)
        Popup(title=r["name"], content=sv, size_hint=(.95, .85)).open()


if __name__ == "__main__":
    FileRiskApp().run()
