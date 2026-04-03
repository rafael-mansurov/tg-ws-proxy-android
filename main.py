"""
Kivy shell: starts Android foreground service with the tg-ws-proxy core (proxy/).
"""
import json
import secrets
import webbrowser

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout

HOST = "127.0.0.1"
PORT = 1443

KV = """
<ProxyScreen>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0.059, 0.059, 0.098, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # ── Header ──
    BoxLayout:
        size_hint_y: None
        height: dp(64)
        padding: dp(16), dp(10)
        spacing: dp(12)
        canvas.before:
            Color:
                rgba: 0.09, 0.09, 0.16, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint: None, None
            size: dp(38), dp(38)
            pos_hint: {'center_y': 0.5}
            canvas.before:
                Color:
                    rgba: 0.33, 0.35, 0.95, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [10]
            Label:
                text: '🔒'
                font_size: dp(18)

        BoxLayout:
            orientation: 'vertical'
            pos_hint: {'center_y': 0.5}
            Label:
                text: 'TG WS Proxy'
                color: 1, 1, 1, 1
                font_size: dp(15)
                bold: True
                halign: 'left'
                text_size: self.size
                valign: 'middle'
            Label:
                text: 'MTProto прокси'
                color: 0.4, 0.4, 0.55, 1
                font_size: dp(11)
                halign: 'left'
                text_size: self.size
                valign: 'middle'

        # Toggle switch in header
        BoxLayout:
            size_hint: None, None
            size: dp(58), dp(64)
            orientation: 'vertical'
            spacing: dp(2)
            pos_hint: {'center_y': 0.5}

            Switch:
                id: proxy_switch
                size_hint: None, None
                size: dp(58), dp(34)
                pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                active: False
                on_active: app.on_toggle(self.active)

            Label:
                id: toggle_label
                text: 'Выкл'
                font_size: dp(9)
                color: 0.4, 0.4, 0.55, 1
                size_hint_y: None
                height: dp(14)
                halign: 'center'
                text_size: self.size
                valign: 'top'

    # ── Status badge ──
    BoxLayout:
        size_hint_y: None
        height: dp(50)
        padding: dp(14), dp(8)

        BoxLayout:
            spacing: dp(8)
            size_hint_y: None
            height: dp(36)
            pos_hint: {'center_y': 0.5}
            padding: dp(12), dp(6)
            canvas.before:
                Color:
                    rgba: app.status_bg
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [10]
                Color:
                    rgba: app.status_border
                Line:
                    rounded_rectangle: self.x, self.y, self.width, self.height, 10

            Label:
                id: dot
                text: '●'
                color: app.status_color
                font_size: dp(10)
                size_hint: None, 1
                width: dp(14)

            Label:
                id: status_label
                text: 'Остановлен'
                color: app.status_color
                font_size: dp(13)
                bold: True
                halign: 'left'
                text_size: self.size
                valign: 'middle'

    # ── Cards ──
    BoxLayout:
        orientation: 'vertical'
        padding: dp(14), 0
        spacing: dp(8)
        size_hint_y: None
        height: dp(180)

        BoxLayout:
            size_hint_y: None
            height: dp(52)
            spacing: dp(8)

            BoxLayout:
                orientation: 'vertical'
                padding: dp(12), dp(8)
                canvas.before:
                    Color:
                        rgba: 0.1, 0.1, 0.18, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10]
                Label:
                    text: 'СЕРВЕР'
                    color: 0.35, 0.35, 0.5, 1
                    font_size: dp(9)
                    halign: 'left'
                    text_size: self.size
                    valign: 'bottom'
                Label:
                    id: host_label
                    text: '127.0.0.1'
                    color: 0.88, 0.9, 0.95, 1
                    font_size: dp(13)
                    halign: 'left'
                    text_size: self.size
                    valign: 'top'

            BoxLayout:
                orientation: 'vertical'
                padding: dp(12), dp(8)
                size_hint_x: 0.4
                canvas.before:
                    Color:
                        rgba: 0.1, 0.1, 0.18, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10]
                Label:
                    text: 'ПОРТ'
                    color: 0.35, 0.35, 0.5, 1
                    font_size: dp(9)
                    halign: 'left'
                    text_size: self.size
                    valign: 'bottom'
                Label:
                    id: port_label
                    text: '1443'
                    color: 0.88, 0.9, 0.95, 1
                    font_size: dp(13)
                    halign: 'left'
                    text_size: self.size
                    valign: 'top'

        BoxLayout:
            orientation: 'vertical'
            padding: dp(12), dp(8)
            size_hint_y: None
            height: dp(68)
            canvas.before:
                Color:
                    rgba: 0.1, 0.1, 0.18, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [10]
            Label:
                text: 'SECRET'
                color: 0.35, 0.35, 0.5, 1
                font_size: dp(9)
                halign: 'left'
                text_size: self.size
                valign: 'bottom'
                size_hint_y: None
                height: dp(18)
            Label:
                id: secret_label
                text: '–'
                color: 0.6, 0.55, 0.98, 1
                font_size: dp(12)
                halign: 'left'
                text_size: self.size
                valign: 'top'

    Widget:
        size_hint_y: 1

    # ── Button ──
    BoxLayout:
        size_hint_y: None
        height: dp(64)
        padding: dp(14), dp(8)

        Button:
            id: tg_button
            text: 'Открыть в Telegram'
            font_size: dp(14)
            bold: True
            color: 1, 1, 1, 1
            background_normal: ''
            background_color: 0, 0, 0, 0
            disabled: not app.running
            on_release: app.open_in_telegram()
            canvas.before:
                Color:
                    rgba: (0.33, 0.35, 0.95, 1) if not self.disabled else (0.2, 0.2, 0.3, 1)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [12]

    # ── Home bar ──
    BoxLayout:
        size_hint_y: None
        height: dp(28)
        canvas.before:
            Color:
                rgba: 0.059, 0.059, 0.098, 1
            Rectangle:
                pos: self.pos
                size: self.size
        Widget
        BoxLayout:
            size_hint: None, None
            size: dp(100), dp(4)
            pos_hint: {'center_y': 0.5}
            canvas.before:
                Color:
                    rgba: 0.25, 0.25, 0.35, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [2]
        Widget
"""

Builder.load_string(KV)


class ProxyScreen(BoxLayout):
    pass


def _start_proxy_service(secret: str) -> None:
    from jnius import autoclass
    ServiceProxy = autoclass("unofficial.tgws.tgwsproxy.ServiceProxy")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ServiceProxy.start(PythonActivity.mActivity, json.dumps({"secret": secret}))


def _stop_proxy_service() -> None:
    from jnius import autoclass
    ServiceProxy = autoclass("unofficial.tgws.tgwsproxy.ServiceProxy")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ServiceProxy.stop(PythonActivity.mActivity)


class TgWsApp(App):
    running = BooleanProperty(False)
    status_color = ListProperty([0.45, 0.45, 0.6, 1])
    status_bg = ListProperty([0.12, 0.12, 0.2, 0.5])
    status_border = ListProperty([0.25, 0.25, 0.4, 0.4])

    def build(self):
        self.secret = secrets.token_hex(16)
        self.screen = ProxyScreen()
        return self.screen

    def _request_permissions(self) -> None:
        try:
            from android.permissions import Permission, check_permission, request_permissions
            if not check_permission(Permission.POST_NOTIFICATIONS):
                request_permissions([Permission.POST_NOTIFICATIONS])
        except Exception:
            pass

    def on_toggle(self, active: bool) -> None:
        ids = self.screen.ids
        if active:
            self._request_permissions()
            try:
                _start_proxy_service(self.secret)
                self.running = True
                ids.status_label.text = "Прокси запущен в фоне"
                ids.toggle_label.text = "Вкл"
                self.status_color = (0.13, 0.8, 0.4, 1)
                self.status_bg = (0.13, 0.46, 0.26, 0.18)
                self.status_border = (0.13, 0.7, 0.35, 0.35)
                ids.secret_label.text = self.secret
            except Exception as e:
                ids.proxy_switch.active = False
                ids.status_label.text = f"Ошибка: {e}"
                self.status_color = (0.9, 0.3, 0.3, 1)
                self.status_bg = (0.4, 0.1, 0.1, 0.18)
                self.status_border = (0.7, 0.2, 0.2, 0.35)
        else:
            try:
                _stop_proxy_service()
            except Exception:
                pass
            self.running = False
            ids.status_label.text = "Остановлен"
            ids.toggle_label.text = "Выкл"
            self.status_color = (0.45, 0.45, 0.6, 1)
            self.status_bg = (0.12, 0.12, 0.2, 0.5)
            self.status_border = (0.25, 0.25, 0.4, 0.4)
            ids.secret_label.text = "–"

    def open_in_telegram(self) -> None:
        url = f"tg://proxy?server={HOST}&port={PORT}&secret={self.secret}"
        webbrowser.open(url)

    def on_pause(self):
        return True


if __name__ == "__main__":
    TgWsApp().run()
