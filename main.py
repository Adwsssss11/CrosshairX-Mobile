from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from kivy.uix.widget import Widget
from kivy.graphics import Color as KivyColor, Rectangle, Ellipse
from kivy.utils import platform
import json
import os

if platform == 'android':
    from jnius import autoclass
    from android.runnable import run_on_ui_thread

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
    PixelFormat = autoclass('android.graphics.PixelFormat')
    Gravity = autoclass('android.view.Gravity')
    Canvas = autoclass('android.graphics.Canvas')
    Paint = autoclass('android.graphics.Paint')
    Style = autoclass('android.graphics.Paint$Style')
    Color = autoclass('android.graphics.Color')
    Bitmap = autoclass('android.graphics.Bitmap')
    BitmapConfig = autoclass('android.graphics.Bitmap$Config')
    ImageView = autoclass('android.widget.ImageView')
    Settings = autoclass('android.provider.Settings')
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
else:
    def run_on_ui_thread(func):
        return func

CONFIG_FILE = "android_crosshair.json"


class CrosshairPreview(Widget):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        self.bind(pos=self.redraw, size=self.redraw)

    def redraw(self, *args):
        self.canvas.clear()
        cfg = self.app_ref.cfg
        cx, cy = self.center_x, self.center_y
        s = cfg["size"]
        t = cfg["thickness"]
        g = cfg["gap"]
        d = cfg["dot_size"]
        shape = cfg["shape"]
        outline = cfg["outline"]

        hex_c = cfg["color"].lstrip('#')
        r, gr, b = tuple(int(hex_c[i:i+2], 16) / 255.0 for i in (0, 2, 4))

        with self.canvas:
            KivyColor(0.12, 0.12, 0.12, 1)
            Rectangle(pos=self.pos, size=self.size)

            def draw_sym_rect(x1, y1, x2, y2):
                if outline:
                    KivyColor(0, 0, 0, 1)
                    Rectangle(pos=(x1 - 2, y1 - 2), size=(x2 - x1 + 4, y2 - y1 + 4))
                KivyColor(r, gr, b, 1)
                Rectangle(pos=(x1, y1), size=(x2 - x1, y2 - y1))

            half_t = t / 2.0

            if shape in ["cross", "cross_dot"]:
                draw_sym_rect(cx - half_t, cy + g, cx + half_t, cy + g + s)
                draw_sym_rect(cx - half_t, cy - g - s, cx + half_t, cy - g)
                draw_sym_rect(cx - g - s, cy - half_t, cx - g, cy + half_t)
                draw_sym_rect(cx + g, cy - half_t, cx + g + s, cy + half_t)

            if shape in ["dot", "cross_dot"]:
                if outline:
                    KivyColor(0, 0, 0, 1)
                    Ellipse(pos=(cx - d - 2, cy - d - 2), size=((d + 2) * 2, (d + 2) * 2))
                KivyColor(r, gr, b, 1)
                Ellipse(pos=(cx - d, cy - d), size=(d * 2, d * 2))


class CrosshairMobileApp(App):
    def build(self):
        self.title = "Crosshair X Mobile"
        self.overlay_view = None
        self.wm = None

        self.cfg = {
            "shape": "cross_dot",
            "size": 26,
            "thickness": 4,
            "gap": 10,
            "dot_size": 5,
            "color": "#00FF00",
            "outline": True
        }
        self.load_cfg()

        root = BoxLayout(orientation='vertical', padding=25, spacing=12)

        root.add_widget(Label(
            text="[b]Crosshair X — Mobile[/b]",
            markup=True,
            font_size='22sp',
            size_hint_y=None,
            height=50
        ))

        self.preview = CrosshairPreview(self, size_hint_y=None, height=160)
        root.add_widget(self.preview)

        btn_perm = Button(
            text="1. Разрешить показ поверх игр",
            background_normal='',
            background_color=(0.15, 0.45, 0.85, 1),
            bold=True,
            size_hint_y=None,
            height=80
        )
        btn_perm.bind(on_press=self.request_permission)
        root.add_widget(btn_perm)

        shape_box = GridLayout(cols=3, spacing=8, size_hint_y=None, height=75)
        for label, val in [("Крест + точка", "cross_dot"), ("Крестик", "cross"), ("Точка", "dot")]:
            b = Button(text=label)
            b.bind(on_press=lambda inst, v=val: self.update_cfg("shape", v))
            shape_box.add_widget(b)
        root.add_widget(shape_box)

        self.add_slider(root, "Длина линий:", "size", 8, 70)
        self.add_slider(root, "Толщина линий:", "thickness", 2, 14)
        self.add_slider(root, "Зазор:", "gap", 0, 45)
        self.add_slider(root, "Размер точки:", "dot_size", 2, 16)

        out_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=55)
        out_box.add_widget(Label(text="Чёрная обводка (контур):"))
        cb = CheckBox(active=self.cfg["outline"])
        cb.bind(active=lambda inst, val: self.update_cfg("outline", val))
        out_box.add_widget(cb)
        root.add_widget(out_box)

        color_box = GridLayout(cols=6, spacing=6, size_hint_y=None, height=70)
        colors = [
            ("#00FF00", (0, 1, 0, 1)),
            ("#FF0000", (1, 0, 0, 1)),
            ("#00FFFF", (0, 1, 1, 1)),
            ("#FFFF00", (1, 1, 0, 1)),
            ("#FF00FF", (1, 0, 1, 1)),
            ("#FFFFFF", (1, 1, 1, 1))
        ]
        for hex_c, rgba in colors:
            cb_btn = Button(background_normal='', background_color=rgba)
            cb_btn.bind(on_press=lambda inst, c=hex_c: self.update_cfg("color", c))
            color_box.add_widget(cb_btn)
        root.add_widget(color_box)

        ctrl_box = GridLayout(cols=2, spacing=12, size_hint_y=None, height=95)
        btn_on = Button(text="ВКЛЮЧИТЬ ПРИЦЕЛ", background_normal='', background_color=(0, 0.75, 0.2, 1), bold=True)
        btn_on.bind(on_press=lambda inst: self.start_overlay())
        btn_off = Button(text="ВЫКЛЮЧИТЬ", background_normal='', background_color=(0.85, 0.15, 0.15, 1), bold=True)
        btn_off.bind(on_press=lambda inst: self.stop_overlay())
        ctrl_box.add_widget(btn_on)
        ctrl_box.add_widget(btn_off)
        root.add_widget(ctrl_box)

        return root

    def add_slider(self, parent, title, key, min_v, max_v):
        box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        lbl = Label(text=f"{title} {self.cfg[key]}", size_hint_x=0.45)
        sld = Slider(min=min_v, max=max_v, value=self.cfg[key], step=1, size_hint_x=0.55)

        def on_val(inst, val):
            val = int(val)
            lbl.text = f"{title} {val}"
            self.update_cfg(key, val)

        sld.bind(value=on_val)
        box.add_widget(lbl)
        box.add_widget(sld)
        parent.add_widget(box)

    def load_cfg(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.cfg.update(json.load(f))
            except Exception:
                pass

    def save_cfg(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f)
        except Exception:
            pass

    def update_cfg(self, key, val):
        self.cfg[key] = val
        self.save_cfg()
        self.preview.redraw()
        if self.overlay_view is not None and platform == 'android':
            self.stop_overlay()
            self.start_overlay()

    def request_permission(self, instance):
        if platform == 'android':
            activity = PythonActivity.mActivity
            if not Settings.canDrawOverlays(activity):
                intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + activity.getPackageName())
                )
                activity.startActivity(intent)

    def start_overlay(self):
        if platform == 'android':
            self._show_android_overlay()

    def stop_overlay(self):
        if platform == 'android':
            self._hide_android_overlay()

    @run_on_ui_thread
    def _show_android_overlay(self):
        activity = PythonActivity.mActivity
        if not Settings.canDrawOverlays(activity):
            self.request_permission(None)
            return
        if self.overlay_view is not None:
            return

        self.wm = activity.getSystemService(activity.WINDOW_SERVICE)

        s = self.cfg["size"]
        t = self.cfg["thickness"]
        g = self.cfg["gap"]
        d = self.cfg["dot_size"]
        shape = self.cfg["shape"]
        outline = self.cfg["outline"]
        main_color = Color.parseColor(self.cfg["color"])
        black_color = Color.parseColor("#000000")

        bmp_size = (s + g) * 2 + 40
        bitmap = Bitmap.createBitmap(bmp_size, bmp_size, BitmapConfig.ARGB_8888)
        canvas = Canvas(bitmap)
        c = bmp_size / 2.0

        paint = Paint()
        paint.setAntiAlias(True)
        paint.setStyle(Style.FILL)

        def draw_rect_sym(x1, y1, x2, y2):
            if outline:
                paint.setColor(black_color)
                canvas.drawRect(x1 - 2, y1 - 2, x2 + 2, y2 + 2, paint)
            paint.setColor(main_color)
            canvas.drawRect(x1, y1, x2, y2, paint)

        half_t = t / 2.0

        if shape in ["cross", "cross_dot"]:
            draw_rect_sym(c - half_t, c - g - s, c + half_t, c - g)
            draw_rect_sym(c - half_t, c + g, c + half_t, c + g + s)
            draw_rect_sym(c - g - s, c - half_t, c - g, c + half_t)
            draw_rect_sym(c + g, c - half_t, c + g + s, c + half_t)

        if shape in ["dot", "cross_dot"]:
            if outline:
                paint.setColor(black_color)
                canvas.drawCircle(c, c, d + 2, paint)
            paint.setColor(main_color)
            canvas.drawCircle(c, c, d, paint)

        iv = ImageView(activity)
        iv.setImageBitmap(bitmap)

        params = LayoutParams(
            LayoutParams.WRAP_CONTENT,
            LayoutParams.WRAP_CONTENT,
            2038,
            LayoutParams.FLAG_NOT_FOCUSABLE | LayoutParams.FLAG_NOT_TOUCHABLE | LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        )
        params.gravity = Gravity.CENTER

        self.overlay_view = iv
        self.wm.addView(self.overlay_view, params)

    @run_on_ui_thread
    def _hide_android_overlay(self):
        if self.wm and self.overlay_view:
            self.wm.removeView(self.overlay_view)
            self.overlay_view = None


if __name__ == '__main__':
    CrosshairMobileApp().run()
