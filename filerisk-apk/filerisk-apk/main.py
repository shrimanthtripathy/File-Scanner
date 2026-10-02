"""FileRisk Scanner - Kivy UI (Android + PC). Engine: filerisk.py"""
import os, time, json, csv, shutil, threading
from functools import partial
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import DictProperty, StringProperty, BooleanProperty, NumericProperty, ListProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.utils import platform, get_color_from_hex as H
import filerisk

LIGHT = {k: H(v) for k, v in dict(bg="#F2F5F8", card="#FFFFFF", line="#E1E6EC", ink="#0F1B2D",
         mut="#566275", acc="#0B6E6E", onacc="#FFFFFF", track="#E1E6EC").items()}
DARK = {k: H(v) for k, v in dict(bg="#0E141B", card="#18212B", line="#2A3644", ink="#EAF0F6",
        mut="#9AA8B8", acc="#3CC4C4", onacc="#062B2B", track="#2A3644").items()}
LEVEL_HEX = {"Clean": "1F7A4D", "Low": "D4A017", "Medium": "E07B1F", "High": "C62828",
             "Critical": "8E2A66", "Error": "6B7785"}
DARK_TEXT = {"Low", "Medium"}


def lvl_rgba(l): return H(LEVEL_HEX.get(l, "6B7785"))
def lvl_text(l): return H("10151C") if l in DARK_TEXT else (1, 1, 1, 1)


class Btn(Button):
    bg = ListProperty([0, 0, 0, 1])
    fg = ListProperty([1, 1, 1, 1])
class NavBtn(Button):
    on = BooleanProperty(False)
class Badge(Label):
    bgc = ListProperty([0, 0, 0, 1])
class Pill(Label):
    bgc = ListProperty([0, 0, 0, 1])
class Row(ButtonBehavior, BoxLayout): pass
def center_text(cx, cy, text, col, size):
    if not text: return
    lb = CoreLabel(text=text, font_size=size, bold=True)
    lb.refresh()
    tex = lb.texture
    Color(*col)
    Rectangle(texture=tex, pos=(cx - tex.width / 2, cy - tex.height / 2), size=tex.size)


class Ring(Widget):
    value = NumericProperty(0)
    col = ListProperty([0, 0.5, 0.5, 1])
    tcol = ListProperty([0, 0, 0, 1])
    track = ListProperty([0.8, 0.8, 0.8, 1])
    text = StringProperty("")
    fs = NumericProperty(26)
    def __init__(self, **kw):
        super().__init__(**kw)
        for p in ("pos", "size", "value", "col", "tcol", "track", "text", "fs"):
            self.bind(**{p: self.draw})
    def draw(self, *a):
        self.canvas.clear()
        r = min(self.size) / 2 - dp(8)
        with self.canvas:
            Color(*self.track)
            Line(circle=(self.center_x, self.center_y, r), width=dp(8))
            Color(*self.col)
            Line(circle=(self.center_x, self.center_y, r, 0, max(1, 360 * self.value)), width=dp(8), cap="round")
            center_text(self.center_x, self.center_y, self.text, self.tcol, dp(self.fs))


class Bar(Widget):
    value = NumericProperty(0)


class Donut(Widget):
    segs = ListProperty([])
    center_text = StringProperty("")
    tcol = ListProperty([0, 0, 0, 1])
    def __init__(self, **kw):
        super().__init__(**kw)
        for p in ("pos", "size", "segs", "center_text", "tcol"):
            self.bind(**{p: self.draw})
    def draw(self, *a):
        self.canvas.clear()
        r, a0 = min(self.size) / 2 - dp(10), 0
        with self.canvas:
            for frac, col in self.segs:
                if frac <= 0: continue
                Color(*col)
                Line(circle=(self.center_x, self.center_y, r, a0, a0 + 360 * frac), width=dp(10))
                a0 += 360 * frac
            center_text(self.center_x, self.center_y, self.center_text, self.tcol, dp(24))


KV = """
#:import dp kivy.metrics.dp
<Txt@Label>:
    color: app.t['ink']
    halign: 'left'
    valign: 'middle'
    text_size: self.width, None
    size_hint_y: None
    height: max(self.texture_size[1], dp(20))
<Muted@Txt>:
    color: app.t['mut']
    font_size: '13sp'
<Name@Label>:
    color: app.t['ink']
    bold: True
    font_size: '15sp'
    halign: 'left'
    valign: 'middle'
    shorten: True
    shorten_from: 'right'
    text_size: self.size
<Line1@Label>:
    color: app.t['mut']
    font_size: '13sp'
    halign: 'left'
    valign: 'middle'
    shorten: True
    shorten_from: 'right'
    text_size: self.size
<Card@BoxLayout>:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(10)
    size_hint_y: None
    height: self.minimum_height
    canvas.before:
        Color:
            rgba: app.t['card']
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
        Color:
            rgba: app.t['line']
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
            width: 1
<Row>:
    size_hint_y: None
    height: dp(68)
    padding: dp(10)
    spacing: dp(12)
    canvas.before:
        Color:
            rgba: app.t['card']
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]
        Color:
            rgba: app.t['line']
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(14))
            width: 1
<Btn>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: self.fg
    bold: True
    font_size: '16sp'
    canvas.before:
        Color:
            rgba: self.bg
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]
<NavBtn>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    bold: True
    font_size: '13sp'
    color: app.t['acc'] if self.on else app.t['mut']
<Badge>:
    size_hint: None, None
    size: dp(48), dp(48)
    pos_hint: {'center_y': .5}
    bold: True
    font_size: '17sp'
    canvas.before:
        Color:
            rgba: self.bgc
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
<Pill>:
    size_hint: None, None
    size: self.texture_size[0] + dp(24), dp(30)
    bold: True
    font_size: '13sp'
    canvas.before:
        Color:
            rgba: self.bgc
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(15)]
<Ring>:
    tcol: app.t['ink']
    track: app.t['track']
<Donut>:
    tcol: app.t['ink']
<Bar>:
    size_hint_y: None
    height: dp(10)
    pos_hint: {'center_y': .5}
    canvas:
        Color:
            rgba: app.t['track']
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(5)]
        Color:
            rgba: app.t['acc']
        RoundedRectangle:
            pos: self.pos
            size: max(dp(4), self.width * self.value), self.height
            radius: [dp(5)]

<HomeScreen@Screen>:
    name: 'home'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20), dp(24), dp(20), dp(8)
        spacing: dp(14)
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            Txt:
                text: 'FileRisk'
                bold: True
                font_size: '22sp'
                height: dp(44)
            Btn:
                text: 'Settings'
                size_hint_x: None
                width: dp(100)
                bg: 0, 0, 0, 0
                fg: app.t['acc']
                on_release: app.go('settings')
        Txt:
            text: 'Check your files before you open them'
            bold: True
            font_size: '26sp'
        Muted:
            text: 'Scans run on this phone. Nothing is uploaded.'
            font_size: '15sp'
        Card:
            Muted:
                text: 'Folder to scan'
            TextInput:
                id: path
                text: app.default_path
                multiline: False
                size_hint_y: None
                height: dp(48)
                padding: dp(12), dp(14)
                foreground_color: app.t['ink']
                background_color: app.t['bg']
                cursor_color: app.t['acc']
            BoxLayout:
                size_hint_y: None
                height: dp(44)
                CheckBox:
                    id: allbox
                    size_hint_x: None
                    width: dp(44)
                Txt:
                    text: 'Scan all file types'
                    height: dp(44)
            Btn:
                text: 'Scan now'
                size_hint_y: None
                height: dp(52)
                bg: app.t['acc']
                fg: app.t['onacc']
                on_release: app.start_scan(path.text, allbox.active)
        Card:
            Muted:
                text: 'What we check'
            Txt:
                text: 'APK  ·  PDF  ·  PPT  ·  Images  ·  Video  ·  Audio'
        Widget:

<ProgressScreen@Screen>:
    name: 'progress'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20), dp(28), dp(20), dp(20)
        spacing: dp(16)
        Txt:
            text: 'Scanning...'
            bold: True
            font_size: '24sp'
        Ring:
            id: ring
            size_hint: None, None
            size: dp(210), dp(210)
            pos_hint: {'center_x': .5}
            col: app.t['acc']
            fs: 36
        Txt:
            id: count
            halign: 'center'
            bold: True
            font_size: '18sp'
        Muted:
            id: cur
            halign: 'center'
        Card:
            orientation: 'horizontal'
            Txt:
                id: nclean
                halign: 'center'
                font_size: '18sp'
                bold: True
            Txt:
                id: nflag
                halign: 'center'
                font_size: '18sp'
                bold: True
        Widget:
        Btn:
            text: 'Cancel'
            size_hint_y: None
            height: dp(52)
            bg: app.t['line']
            fg: app.t['ink']
            on_release: app.cancel()

<ResultsScreen@Screen>:
    name: 'results'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20), dp(28), dp(20), dp(8)
        spacing: dp(10)
        Txt:
            text: 'Results'
            bold: True
            font_size: '24sp'
        Muted:
            id: sub
        BoxLayout:
            id: pills
            size_hint_y: None
            height: dp(34)
            spacing: dp(8)
        ScrollView:
            GridLayout:
                id: grid
                cols: 1
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height

<DetailScreen@Screen>:
    name: 'detail'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20), dp(20), dp(20), dp(12)
        spacing: dp(12)
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            Btn:
                text: 'Back'
                size_hint_x: None
                width: dp(80)
                bg: 0, 0, 0, 0
                fg: app.t['acc']
                on_release: app.go('results')
            Txt:
                text: 'File details'
                bold: True
                font_size: '18sp'
                height: dp(44)
        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(12)
                Txt:
                    id: fname
                    bold: True
                    font_size: '22sp'
                Muted:
                    id: fpath
                Card:
                    orientation: 'horizontal'
                    spacing: dp(16)
                    Ring:
                        id: ring
                        size_hint: None, None
                        size: dp(110), dp(110)
                        pos_hint: {'center_y': .5}
                    BoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: dp(110)
                        pos_hint: {'center_y': .5}
                        Widget:
                        Txt:
                            id: lvl
                            bold: True
                            font_size: '20sp'
                        Muted:
                            id: lvlnote
                        Widget:
                Card:
                    Muted:
                        text: 'Why it was flagged'
                    BoxLayout:
                        id: reasons
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(8)
                Card:
                    Txt:
                        id: info
                        font_size: '14sp'
        Btn:
            text: 'Move to quarantine'
            size_hint_y: None
            height: dp(52)
            bg: app.t['ink']
            fg: app.t['bg']
            on_release: app.quarantine()
        Btn:
            text: 'Keep file'
            size_hint_y: None
            height: dp(48)
            bg: app.t['line']
            fg: app.t['ink']
            on_release: app.go('results')

<DashboardScreen@Screen>:
    name: 'dashboard'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20), dp(28), dp(20), dp(8)
        spacing: dp(10)
        Txt:
            text: 'Dashboard'
            bold: True
            font_size: '24sp'
        Muted:
            id: dsub
        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(12)
                Card:
                    orientation: 'horizontal'
                    spacing: dp(16)
                    Donut:
                        id: donut
                        size_hint: None, None
                        size: dp(130), dp(130)
                        pos_hint: {'center_y': .5}
                    BoxLayout:
                        id: legend
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        pos_hint: {'center_y': .5}
                        spacing: dp(4)
                Card:
                    Muted:
                        text: 'Average risk by file type'
                    BoxLayout:
                        id: types
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(8)
                Btn:
                    text: 'Export report (CSV)'
                    size_hint_y: None
                    height: dp(48)
                    bg: app.t['line']
                    fg: app.t['ink']
                    on_release: app.export_csv()

<SettingsScreen@Screen>:
    name: 'settings'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20), dp(24), dp(20), dp(12)
        spacing: dp(14)
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            Btn:
                text: 'Back'
                size_hint_x: None
                width: dp(80)
                bg: 0, 0, 0, 0
                fg: app.t['acc']
                on_release: app.go('home')
            Txt:
                text: 'Settings'
                bold: True
                font_size: '24sp'
                height: dp(44)
        Card:
            Muted:
                text: 'Appearance'
            BoxLayout:
                size_hint_y: None
                height: dp(48)
                spacing: dp(8)
                Btn:
                    text: 'Light'
                    bg: app.t['acc'] if app.mode == 'light' else app.t['line']
                    fg: app.t['onacc'] if app.mode == 'light' else app.t['ink']
                    on_release: app.set_mode('light')
                Btn:
                    text: 'Dark'
                    bg: app.t['acc'] if app.mode == 'dark' else app.t['line']
                    fg: app.t['onacc'] if app.mode == 'dark' else app.t['ink']
                    on_release: app.set_mode('dark')
        Card:
            Muted:
                text: 'Quarantine'
            Txt:
                text: app.qtext
            Btn:
                text: 'Restore all files'
                size_hint_y: None
                height: dp(48)
                bg: app.t['line']
                fg: app.t['ink']
                on_release: app.restore_all()
        Card:
            Muted:
                text: 'About'
            Txt:
                text: 'FileRisk 1.0. Scans run on this device only. Static checks show risk indicators, not a guarantee of safety.'
                color: app.t['mut']
                font_size: '14sp'
        Widget:

BoxLayout:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: app.t['bg']
        Rectangle:
            pos: self.pos
            size: self.size
    ScreenManager:
        id: sm
        HomeScreen:
        ProgressScreen:
        ResultsScreen:
        DetailScreen:
        DashboardScreen:
        SettingsScreen:
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        canvas.before:
            Color:
                rgba: app.t['card']
            Rectangle:
                pos: self.pos
                size: self.size
        NavBtn:
            text: 'Scan'
            on: app.nav == 'home'
            on_release: app.go('home')
        NavBtn:
            text: 'Results'
            on: app.nav == 'results'
            on_release: app.go('results')
        NavBtn:
            text: 'Dashboard'
            on: app.nav == 'dashboard'
            on_release: app.go('dashboard')
"""


def request_storage():
    if platform != "android": return
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
        from jnius import autoclass
        if autoclass("android.os.Build$VERSION").SDK_INT >= 30 and \
                not autoclass("android.os.Environment").isExternalStorageManager():
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            i = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            i.setData(autoclass("android.net.Uri").parse("package:" + act.getPackageName()))
            act.startActivity(i)
    except Exception as e:
        print("permission error:", e)


class FileRiskApp(App):
    title = "FileRisk Scanner"
    t = DictProperty(LIGHT)
    mode = StringProperty("light")
    nav = StringProperty("home")
    qtext = StringProperty("0 files in quarantine")
    default_path = StringProperty("/storage/emulated/0/Download" if platform == "android" else os.path.expanduser("~"))

    def build(self):
        self.results, self.stats_, self.cur_file, self.cancelled, self.secs = [], {}, None, False, 0
        try:
            with open(os.path.join(self.user_data_dir, "settings.json")) as f:
                self.set_mode(json.load(f).get("mode", "light"), save=False)
        except Exception:
            pass
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self.on_key)
        self.root = Builder.load_string(KV)
        self.sm = self.root.ids.sm
        self.sm.current = "home"
        self.refresh_q()
        return self.root

    def on_start(self): request_storage()

    # ---------- navigation / theme ----------
    def scr(self, n): return self.sm.get_screen(n).ids

    def go(self, name):
        self.sm.current = name
        self.nav = {"detail": "results", "progress": "home", "settings": "home"}.get(name, name)

    def on_key(self, win, key, *a):
        if key == 27:
            if self.sm.current == "detail": self.go("results")
            elif self.sm.current != "home": self.go("home")
            else: return False
            return True
        return False

    def set_mode(self, m, save=True):
        self.mode = m
        self.t = DARK if m == "dark" else LIGHT
        Window.clearcolor = self.t["bg"]
        if save:
            try:
                with open(os.path.join(self.user_data_dir, "settings.json"), "w") as f: json.dump({"mode": m}, f)
            except Exception: pass

    def msg(self, title, text):
        lab = Label(text=text, halign="center", valign="middle")
        lab.bind(size=lambda w, s: setattr(w, "text_size", (s[0] - dp(10), None)))
        Popup(title=title, content=lab, size_hint=(.88, .35)).open()

    # ---------- scanning ----------
    def start_scan(self, path, scan_all):
        if not os.path.exists(path):
            self.msg("Folder not found", "Check the path, and allow 'All files access' for this app in Android settings.")
            return
        self.cancelled = False
        ids = self.scr("progress")
        ids.ring.value = 0; ids.ring.text = "0%"; ids.count.text = "Preparing..."; ids.cur.text = ""
        ids.nclean.text = ""; ids.nflag.text = ""
        self.go("progress")
        threading.Thread(target=self._scan, args=(path, scan_all), daemon=True).start()

    def _scan(self, path, scan_all):
        t0, results, clean, last = time.time(), [], 0, 0
        files = list(filerisk.collect(path, True, scan_all))
        total = len(files)
        for i, p in enumerate(files, 1):
            if self.cancelled: break
            r = filerisk.scan_file(p)
            results.append(r)
            clean += r["level"] == "Clean"
            if time.time() - last > 0.1 or i == total:
                last = time.time()
                Clock.schedule_once(partial(self._prog, i, total, os.path.basename(p), clean, i - clean))
        Clock.schedule_once(partial(self._done, results, time.time() - t0))

    def _prog(self, i, total, name, clean, flag, *_):
        ids = self.scr("progress")
        ids.ring.value = i / max(total, 1)
        ids.ring.text = f"{int(100 * i / max(total, 1))}%"
        ids.count.text = f"{i} of {total} files"
        ids.cur.text = name
        ids.nclean.text = f"[color=1F7A4D]{clean}[/color] clean"
        ids.nflag.text = f"[color=C62828]{flag}[/color] flagged"
        ids.nclean.markup = ids.nflag.markup = True

    def _done(self, results, secs, *_):
        self.secs = secs
        if not results:
            self.msg("Nothing to scan", "No supported files were found in that folder. Try 'Scan all file types'.")
            self.go("home"); return
        self.results = sorted(results, key=lambda r: -r["score"])
        self.refresh_all()
        self.go("results")

    def cancel(self): self.cancelled = True

    # ---------- results / dashboard ----------
    def refresh_all(self):
        self.stats_ = filerisk.stats(self.results, self.secs)
        st, lv = self.stats_, self.stats_["by_level"]
        ids = self.scr("results")
        ids.sub.text = f"{st['total_files']} files scanned in {st['seconds']}s - riskiest first"
        ids.pills.clear_widgets()
        for l in ("Critical", "High", "Medium", "Low", "Clean"):
            if l in lv:
                ids.pills.add_widget(Pill(text=f"{lv[l]['count']} {l}", bgc=lvl_rgba(l), color=lvl_text(l)))
        ids.pills.add_widget(Widget())
        ids.grid.clear_widgets()
        for r in self.results[:300]:
            row = Row()
            row.add_widget(Badge(text=str(r["score"]), bgc=lvl_rgba(r["level"]), color=lvl_text(r["level"])))
            col = BoxLayout(orientation="vertical")
            why = next((f["message"] for f in sorted(r["findings"], key=lambda f: -f["points"]) if f["points"] > 0),
                       "No risk indicators found")
            col.add_widget(Factory.Name(text=r["name"]))
            col.add_widget(Factory.Line1(text=f"{r['level']} - {why}"))
            row.add_widget(col)
            row.bind(on_release=partial(self.open_detail, r))
            ids.grid.add_widget(row)
        d = self.scr("dashboard")
        d.dsub.text = f"{st['total_files']} files - {st['total_bytes']/1e6:.1f} MB"
        d.donut.center_text = str(st["total_files"])
        total = max(st["total_files"], 1)
        d.donut.segs = [(lv[l]["count"] / total, lvl_rgba(l)) for l in ("Clean", "Low", "Medium", "High", "Critical") if l in lv]
        d.legend.clear_widgets()
        for l in ("Clean", "Low", "Medium", "High", "Critical"):
            if l in lv:
                d.legend.add_widget(Factory.Txt(text=f"[color={LEVEL_HEX[l]}]#[/color] {l}   {lv[l]['percent']}%", markup=True))
        d.types.clear_widgets()
        for k, v in sorted(st["by_type"].items(), key=lambda kv: -kv[1]["avg_score"]):
            row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(10))
            row.add_widget(Factory.Line1(text=k.upper(), size_hint_x=None, width=dp(56)))
            row.add_widget(Bar(value=v["avg_score"] / 100))
            row.add_widget(Factory.Line1(text=str(v["avg_score"]), size_hint_x=None, width=dp(40)))
            d.types.add_widget(row)

    def open_detail(self, r, *_):
        self.cur_file = r
        ids = self.scr("detail")
        ids.fname.text, ids.fpath.text = r["name"], r["path"]
        ids.ring.value, ids.ring.col = r["score"] / 100, lvl_rgba(r["level"])
        ids.ring.text = str(r["score"])
        ids.lvl.text = f"{r['level']} risk" if r["level"] != "Clean" else "No threats found"
        ids.lvlnote.text = f"Score {r['score']} of 100"
        ids.reasons.clear_widgets()
        items = [f for f in r["findings"] if f["points"] > 0] or None
        if items:
            for f in sorted(items, key=lambda f: -f["points"]):
                ids.reasons.add_widget(Factory.Txt(text=f"+{f['points']}   {f['message']}", font_size="14sp"))
        else:
            ids.reasons.add_widget(Factory.Txt(text="No risk indicators found.", font_size="14sp"))
        ids.info.text = (f"Real type: {r['kind']}\nSize: {r['size']:,} bytes\nEntropy: {r['entropy']}\n"
                         f"SHA-256: {r['sha256'][:12]}...{r['sha256'][-6:]}\n\nStatic checks show risk indicators, not a guarantee of safety.")
        self.go("detail")

    # ---------- quarantine ----------
    def qdir(self):
        d = os.path.join(self.user_data_dir, "quarantine"); os.makedirs(d, exist_ok=True); return d

    def qload(self):
        try:
            with open(os.path.join(self.qdir(), "index.json")) as f: return json.load(f)
        except Exception: return {}

    def qsave(self, idx):
        with open(os.path.join(self.qdir(), "index.json"), "w") as f: json.dump(idx, f)
        self.refresh_q()

    def refresh_q(self):
        n = len(self.qload())
        self.qtext = f"{n} file{'s' if n != 1 else ''} in quarantine. Files stay isolated until restored."

    def quarantine(self):
        r = self.cur_file
        if not r: return
        try:
            idx = self.qload()
            qn = f"{r['sha256'][:10]}_{r['name']}"
            shutil.move(r["path"], os.path.join(self.qdir(), qn))
            idx[qn] = r["path"]; self.qsave(idx)
        except Exception as e:
            self.msg("Could not quarantine", str(e)); return
        self.results = [x for x in self.results if x["path"] != r["path"]]
        self.refresh_all()
        self.go("results")
        self.msg("Moved to quarantine", f"{r['name']} is isolated. You can restore it in Settings.")

    def restore_all(self):
        idx, n = self.qload(), 0
        for qn, orig in list(idx.items()):
            src = os.path.join(self.qdir(), qn)
            if not os.path.exists(src): idx.pop(qn); continue
            dst = orig + ".restored" if os.path.exists(orig) else orig
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst); idx.pop(qn); n += 1
            except Exception: pass
        self.qsave(idx)
        self.msg("Restore complete", f"{n} file(s) restored to their original folders.")

    # ---------- export ----------
    def export_csv(self):
        if not self.results:
            self.msg("Nothing to export", "Run a scan first."); return
        d = "/storage/emulated/0/Download" if platform == "android" else os.path.expanduser("~")
        p = os.path.join(d, f"filerisk_report_{time.strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["path", "kind", "size", "sha256", "entropy", "score", "level", "reasons"])
                for r in self.results:
                    w.writerow([r["path"], r["kind"], r["size"], r["sha256"], r["entropy"], r["score"], r["level"],
                                " | ".join(x["message"] for x in r["findings"])])
            self.msg("Report saved", p)
        except Exception as e:
            self.msg("Could not save report", str(e))


if __name__ == "__main__":
    FileRiskApp().run()
