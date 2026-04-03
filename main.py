"""
Kivy shell: starts Android foreground service with the tg-ws-proxy core.
"""
import json
import secrets
import webbrowser

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

HOST = "127.0.0.1"
PORT = 1443

KV = """
<ProxyScreen>:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(12)
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # Header
    BoxLayout:
        size_hint_y: None
        height: dp(56)
        spacing: dp(12)

        BoxLayout:
            size_hint: None, None
            size: dp(44), dp(44)
            pos_hint: {'center_y': 0.5}
            canvas.before:
                Color:
                    rgba: 0.165, 0.671, 0.933, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [10]
            Label:
                text: '[b]🔒[/b]'
                markup: True
                font_size: dp(22)

        BoxLayout:
            orientation: 'vertical'
            pos_hint: {'center_y': 0.5}
            Label:
                text: 'TG WS Proxy'
                font_size: dp(16)
                bold: True
                color: 0.07, 0.07, 0.09, 1
                halign: 'left'
                text_size: self.size
                valign: 'middle'
            Label:
                text: 'MTProto прокси'
                font_size: dp(11)
                color: 0.6, 0.6, 0.65, 1
                halign: 'left'
                text_size: self.size
                valign: 'middle'

        # Toggle
        BoxLayout:
            orientation: 'vertical'
            size_hint: None, None
            size: dp(56), dp(56)
            pos_hint: {'center_y': 0.5}
            spacing: dp(2)

            Switch:
                id: proxy_switch
                size_hint: None, None
                size: dp(56), dp(38)
                pos_hint: {'center_x': 0.5}
                active: False
                on_active: app.on_toggle(self.active)

            Label:
                id: toggle_label
                text: 'Выкл'
                font_size: dp(9)
                color: 0.6, 0.6, 0.65, 1
                size_hint_y: None
                height: dp(14)
                halign: 'center'
                text_size: self.size

    # Status
    BoxLayout:
        size_hint_y: None
        height: dp(52)
        padding: dp(14), dp(10)
        canvas.before:
            Color:
                rgba: app.status_bg
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [12]

        Label:
            id: dot_label
            text: '●'
            font_size: dp(10)
            color: app.status_color
            size_hint: None, 1
            width: dp(20)

        Label:
            id: status_label
            text: app.status_text
            font_size: dp(13)
            bold: True
            color: app.status_color
            halign: 'left'
            text_size: self.size
            valign: 'middle'

    # Cards row
    BoxLayout:
        size_hint_y: None
        height: dp(64)
        spacing: dp(10)

        BoxLayout:
            orientation: 'vertical'
            padding: dp(12), dp(8)
            spacing: dp(4)
            canvas.before:
                Color:
                    rgba: 0.96, 0.97, 0.98, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [12]
            Label:
                text: 'СЕРВЕР'
                font_size: dp(9)
                color: 0.55, 0.55, 0.6, 1
                halign: 'left'
                text_size: self.size
                bold: True
            Label:
                text: '127.0.0.1'
                font_size: dp(14)
                bold: True
                color: 0.07, 0.07, 0.09, 1
                halign: 'left'
                text_size: self.size

        BoxLayout:
            orientation: 'vertical'
            size_hint_x: 0.42
            padding: dp(12), dp(8)
            spacing: dp(4)
            canvas.before:
                Color:
                    rgba: 0.96, 0.97, 0.98, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [12]
            Label:
                text: 'ПОРТ'
                font_size: dp(9)
                color: 0.55, 0.55, 0.6, 1
                halign: 'left'
                text_size: self.size
                bold: True
            Label:
                text: '1443'
                font_size: dp(14)
                bold: True
                color: 0.07, 0.07, 0.09, 1
                halign: 'left'
                text_size: self.size

    # Secret card
    BoxLayout:
        size_hint_y: None
        height: dp(72)
        padding: dp(12), dp(8)
        spacing: dp(4)
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.96, 0.97, 0.98, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [12]
        Label:
            text: 'SECRET'
            font_size: dp(9)
            color: 0.55, 0.55, 0.6, 1
            halign: 'left'
            text_size: self.size
            bold: True
            size_hint_y: None
            height: dp(18)
        Label:
            id: secret_label
            text: app.secret_display
            font_size: dp(11)
            color: 0.165, 0.671, 0.933, 1
            halign: 'left'
            text_size: self.size

    # Log (диагностика)
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        padding: dp(12), dp(8)
        canvas.before:
            Color:
                rgba: 0.98, 0.96, 0.94, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [12]
        Label:
            id: log_label
            text: app.log_text
            font_size: dp(10)
            color: 0.4, 0.3, 0.2, 1
            halign: 'left'
            valign: 'top'
            text_size: self.size
            markup: True

    Widget

    # Button
    Button:
        size_hint_y: None
        height: dp(52)
        text: 'Открыть в Telegram'
        font_size: dp(15)
        bold: True
        color: 1, 1, 1, 1
        disabled: not app.running
        background_normal: ''
        background_color: 0, 0, 0, 0
        on_release: app.open_in_telegram()
        canvas.before:
            Color:
                rgba: (0.165, 0.671, 0.933, 1) if not self.disabled else (0.88, 0.89, 0.92, 1)
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [14]
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
    status_text = StringProperty("Остановлен")
    status_color = [0.6, 0.6, 0.65, 1]
    status_bg = [0.94, 0.94, 0.96, 1]
    secret_display = StringProperty("––––––––––––––––")
    log_text = StringProperty("Лог: ожидание")

    def build(self):
        self.secret = secrets.token_hex(16)
        self.screen = ProxyScreen()
        return self.screen

    def _request_permissions(self) -> None:
        try:
            from android.permissions import Permission, check_permission, request_permissions
            if not check_permission(Permission.POST_NOTIFICATIONS):
                request_permissions([Permission.POST_NOTIFICATIONS])
            self.log_text = "Разрешения запрошены"
        except Exception as e:
            self.log_text = f"Permissions: {e}"

    def on_toggle(self, active: bool) -> None:
        if active:
            self._request_permissions()
            self.log_text = "Запуск сервиса…"
            try:
                _start_proxy_service(self.secret)
                self.running = True
                self.status_text = "Прокси запущен"
                self.status_color = [0.05, 0.6, 0.32, 1]
                self.status_bg = [0.9, 0.98, 0.93, 1]
                self.secret_display = self.secret
                self.log_text = f"OK · 127.0.0.1:{PORT}"
            except Exception as e:
                self.screen.ids.proxy_switch.active = False
                self.status_text = "Ошибка запуска"
                self.status_color = [0.8, 0.2, 0.2, 1]
                self.status_bg = [0.99, 0.93, 0.93, 1]
                self.log_text = f"Ошибка: {e}"
        else:
            try:
                _stop_proxy_service()
                self.log_text = "Сервис остановлен"
            except Exception as e:
                self.log_text = f"Стоп: {e}"
            self.running = False
            self.status_text = "Остановлен"
            self.status_color = [0.6, 0.6, 0.65, 1]
            self.status_bg = [0.94, 0.94, 0.96, 1]
            self.secret_display = "––––––––––––––––"

    def open_in_telegram(self) -> None:
        url = f"tg://proxy?server={HOST}&port={PORT}&secret={self.secret}"
        self.log_text = f"Открываю: {url[:40]}…"
        webbrowser.open(url)

    def on_pause(self):
        return True


if __name__ == "__main__":
    TgWsApp().run()
