import json
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.switch import Switch
from kivy.core.window import Window
from kivy.utils import platform

CONFIG_FILE = "crosshair_android.json"
Window.clearcolor = (0.07, 0.07, 0.07, 1)  # Тёмный фон #121212


class AndroidOverlayManager:
    """Управляет системным окном поверх всех игр на Android через WindowManager"""
    def __init__(self):
        self.is_showing = False
        self.overlay_view = None
        self.wm = None
        self.params = None

    def has_permission(self):
        if platform != "android":
            return True
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Settings = autoclass("android.provider.Settings")
        return Settings.canDrawOverlays(PythonActivity.mActivity)

    def request_permission(self):
        if platform != "android":
            return
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Settings = autoclass("android.provider.Settings")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")

        activity = PythonActivity.mActivity
        intent = Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:" + activity.getPackageName())
        )
        activity.startActivity(intent)

    def create_crosshair_bitmap(self, cfg):
        """Генерирует точный попиксельный Bitmap для Android без размытия"""
        from jnius import autoclass
        Bitmap = autoclass("android.graphics.Bitmap")
        BitmapConfig = autoclass("android.graphics.Bitmap$Config")
        Canvas = autoclass("android.graphics.Canvas")
        Paint = autoclass("android.graphics.Paint")
        Color = autoclass("android.graphics.Color")

        canvas_size = 301
        c = canvas_size // 2  # 150
        bmp = Bitmap.createBitmap(canvas_size, canvas_size, BitmapConfig.ARGB_8888)
        canvas = Canvas(bmp)

        paint_main = Paint()
        paint_main.setAntiAlias(False)
        paint_main.setColor(Color.parseColor(cfg["color"]))

        paint_outline = Paint()
        paint_outline.setAntiAlias(False)
        paint_outline.setColor(Color.BLACK)

        s = int(cfg["size"])
        t = int(cfg["thickness"])
        g = int(cfg["gap"])
        d = int(cfg["dot_size"])
        outline = cfg["outline"]
        shape = cfg["shape"]

        def draw_exact_box(x1, y1, w, h):
            x2 = x1 + w
            y2 = y1 + h
            if outline:
                canvas.drawRect(float(x1 - 1), float(y1 - 1), float(x2 + 1), float(y2 + 1), paint_outline)
            canvas.drawRect(float(x1), float(y1), float(x2), float(y2), paint_main)

        cx_start = c - (t // 2)
        cy_start = c - (t // 2)

        if shape in ["cross", "cross_dot"]:
            draw_exact_box(cx_start, cy_start - g - s, t, s)
            draw_exact_box(cx_start, cy_start + t + g, t, s)
            draw_exact_box(cx_start - g - s, cy_start, s, t)
            draw_exact_box(cx_start + t + g, cy_start, s, t)

        if shape in ["dot", "cross_dot"]:
            dx_start = c - (d // 2)
            dy_start = c - (d // 2)
            draw_exact_box(dx_start, dy_start, d, d)

        return bmp

    def show_or_update(self, cfg):
        if platform != "android":
            return
        if not cfg["visible"]:
            self.hide()
            return
        if not self.has_permission():
            self.request_permission()
            return

        from jnius import autoclass
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def _update_ui():
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            WindowManagerLayoutParams = autoclass("android.view.WindowManager$LayoutParams")
            PixelFormat = autoclass("android.graphics.PixelFormat")
            Gravity = autoclass("android.view.Gravity")
            ImageView = autoclass("android.widget.ImageView")

            activity = PythonActivity.mActivity
            if self.wm is None:
                self.wm = activity.getSystemService(Context.WINDOW_SERVICE)

            bmp = self.create_crosshair_bitmap(cfg)

            if self.overlay_view is None:
                self.overlay_view = ImageView(activity)
                self.overlay_view.setImageBitmap(bmp)

                # TYPE_APPLICATION_OVERLAY (2038) + сквозные касания + полный физический экран
                flags = (
                    WindowManagerLayoutParams.FLAG_NOT_FOCUSABLE
                    | WindowManagerLayoutParams.FLAG_NOT_TOUCHABLE
                    | WindowManagerLayoutParams.FLAG_LAYOUT_IN_SCREEN
                    | WindowManagerLayoutParams.FLAG_LAYOUT_NO_LIMITS
                )
                self.params = WindowManagerLayoutParams(
                    301,
                    301,
                    2038,
                    flags,
                    PixelFormat.TRANSLUCENT
                )
                self.params.gravity = Gravity.CENTER
                self.params.x = int(cfg["offset_x"])
                self.params.y = int(cfg["offset_y"])
                self.wm.addView(self.overlay_view, self.params)
                self.is_showing = True
            else:
                self.overlay_view.setImageBitmap(bmp)
                self.params.x = int(cfg["offset_x"])
                self.params.y = int(cfg["offset_y"])
                self.wm.updateViewLayout(self.overlay_view, self.params)

        _update_ui()

    def hide(self):
        if platform != "android" or not self.is_showing or self.overlay_view is None:
            return
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def _remove_ui():
            try:
                self.wm.removeView(self.overlay_view)
            except Exception:
                pass
            self.overlay_view = None
            self.is_showing = False

        _remove_ui()


class CrosshairMobileApp(App):
    def build(self):
        self.defaults = {
            "shape": "cross_dot",
            "size": 24,
            "thickness": 2,
            "gap": 8,
            "dot_size": 2,
            "color": "#00FF00",
            "outline": True,
            "offset_x": 0,
            "offset_y": 0,
            "visible": False
        }
        self.config_data = dict(self.defaults)
        self.load_config()
        self.overlay = AndroidOverlayManager()
        self.sliders = {}

        root = BoxLayout(orientation="vertical", padding=16, spacing=10)

        # Заголовок
        root.add_widget(Label(
            text="Crosshair X (Android Edition)",
            font_size="22sp",
            bold=True,
            color=(0, 1, 0, 1),
            size_hint_y=None,
            height=45
        ))

        # Кнопка разрешения поверх окон
        btn_perm = Button(
            text="1. Разрешить показ поверх игр",
            background_normal="",
            background_color=(0.08, 0.4, 0.75, 1),
            font_size="15sp",
            bold=True,
            size_hint_y=None,
            height=48
        )
        btn_perm.bind(on_release=lambda *_: self.overlay.request_permission())
        root.add_widget(btn_perm)

        # Главная кнопка Вкл / Выкл прицел
        self.btn_toggle = Button(
            text="Прицел: ВКЛЮЧЁН" if self.config_data["visible"] else "Прицел: ВЫКЛЮЧЕН",
            background_normal="",
            background_color=(0.18, 0.49, 0.2, 1) if self.config_data["visible"] else (0.78, 0.16, 0.16, 1),
            font_size="16sp",
            bold=True,
            size_hint_y=None,
            height=52
        )
        self.btn_toggle.bind(on_release=self.toggle_overlay)
        root.add_widget(self.btn_toggle)

        # Прокручиваемая панель настроек
        scroll = ScrollView()
        panel = BoxLayout(orientation="vertical", spacing=10, size_hint_y=None)
        panel.bind(minimum_height=panel.setter("height"))

        # Выбор формы (без круга)
        panel.add_widget(Label(text="Форма прицела:", size_hint_y=None, height=30, color=(0.8, 0.8, 0.8, 1)))
        shape_box = GridLayout(cols=3, spacing=8, size_hint_y=None, height=46)
        for label_txt, val in [("Крест + точка", "cross_dot"), ("Крестик", "cross"), ("Точка", "dot")]:
            b = Button(text=label_txt, background_normal="", background_color=(0.18, 0.18, 0.18, 1))
            b.bind(on_release=lambda _, v=val: self.set_param("shape", v))
            shape_box.add_widget(b)
        panel.add_widget(shape_box)

        # Быстрый выбор цвета
        panel.add_widget(Label(text="Цвет прицела:", size_hint_y=None, height=30, color=(0.8, 0.8, 0.8, 1)))
        color_box = GridLayout(cols=5, spacing=8, size_hint_y=None, height=44)
        colors = [
            ("#00FF00", (0, 1, 0, 1)),
            ("#FF0000", (1, 0, 0, 1)),
            ("#00FFFF", (0, 1, 1, 1)),
            ("#FFFF00", (1, 1, 0, 1)),
            ("#FFFFFF", (1, 1, 1, 1))
        ]
        for hex_code, rgba in colors:
            cb = Button(background_normal="", background_color=rgba)
            cb.bind(on_release=lambda _, c=hex_code: self.set_param("color", c))
            color_box.add_widget(cb)
        panel.add_widget(color_box)

        # Ползунки настроек
        self.add_slider(panel, "Длина линий", "size", 4, 80)
        self.add_slider(panel, "Толщина линий", "thickness", 1, 12)
        self.add_slider(panel, "Зазор от центра", "gap", 0, 50)
        self.add_slider(panel, "Размер точки", "dot_size", 1, 16)
        self.add_slider(panel, "Смещение по X", "offset_x", -80, 80)
        self.add_slider(panel, "Смещение по Y", "offset_y", -80, 80)

        # Переключатель чёрной обводки (1 пиксель)
        out_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=44)
        out_box.add_widget(Label(text="Чёрная обводка (1 пиксель):", halign="left"))
        self.sw_outline = Switch(active=self.config_data["outline"])
        self.sw_outline.bind(active=lambda _, val: self.set_param("outline", val))
        out_box.add_widget(self.sw_outline)
        panel.add_widget(out_box)

        # Кнопка полного сброса настроек
        btn_reset = Button(
            text="Сбросить все настройки",
            background_normal="",
            background_color=(0.26, 0.26, 0.26, 1),
            font_size="15sp",
            size_hint_y=None,
            height=48
        )
        btn_reset.bind(on_release=self.reset_all_settings)
        panel.add_widget(btn_reset)

        scroll.add_widget(panel)
        root.add_widget(scroll)

        if self.config_data["visible"]:
            self.overlay.show_or_update(self.config_data)

        return root

    def add_slider(self, parent, title, key, min_v, max_v):
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=62)
        lbl = Label(text=f"{title}: {int(self.config_data[key])}", size_hint_y=None, height=26)
        sld = Slider(min=min_v, max=max_v, value=self.config_data[key], step=1)

        def on_val(_, val):
            iv = int(val)
            lbl.text = f"{title}: {iv}"
            self.set_param(key, iv)

        sld.bind(value=on_val)
        box.add_widget(lbl)
        box.add_widget(sld)
        parent.add_widget(box)
        self.sliders[key] = (sld, lbl, title)

    def set_param(self, key, val):
        self.config_data[key] = val
        self.save_config()
        if self.config_data["visible"]:
            self.overlay.show_or_update(self.config_data)

    def toggle_overlay(self, *_):
        self.config_data["visible"] = not self.config_data["visible"]
        self.btn_toggle.text = "Прицел: ВКЛЮЧЁН" if self.config_data["visible"] else "Прицел: ВЫКЛЮЧЕН"
        self.btn_toggle.background_color = (0.18, 0.49, 0.2, 1) if self.config_data["visible"] else (0.78, 0.16, 0.16, 1)
        self.save_config()
        self.overlay.show_or_update(self.config_data)

    def reset_all_settings(self, *_):
        was_visible = self.config_data["visible"]
        self.config_data = dict(self.defaults)
        self.config_data["visible"] = was_visible

        for key, (sld, lbl, title) in self.sliders.items():
            sld.value = self.config_data[key]
            lbl.text = f"{title}: {int(self.config_data[key])}"

        self.sw_outline.active = True
        self.save_config()
        if self.config_data["visible"]:
            self.overlay.show_or_update(self.config_data)

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2)
        except Exception:
            pass

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config_data.update(json.load(f))
            except Exception:
                pass


if __name__ == "__main__":
    CrosshairMobileApp().run()
