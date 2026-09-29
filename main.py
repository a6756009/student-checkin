# -*- coding: utf-8 -*-
"""
学生签到 APP - 干净重写版
技术栈: Python + Kivy + SQLite
"""
import os, sys
from kivy.config import Config

# ============ 最开头：必须在 Kivy import 之前 ============
Config.set("kivy", "keyboard_mode", "systemanddock")
Config.set("graphics", "width", "400")
Config.set("graphics", "height", "720")

import kivy
kivy.require("2.0.0")
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.utils import get_color_from_hex
from kivy.metrics import dp
from kivy.clock import Clock

# ============ 注册中文字体（兼容 Windows / Android）============
_font_candidates = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'msyh.ttc'),
    r"C:\Windows\Fonts\msyh.ttc",
    '/system/fonts/NotoSansCJK-Regular.ttc',
    '/system/fonts/DroidSansFallbackFull.ttf',
]
HAS_CN = False
FONT_PATH = None
for _fp in _font_candidates:
    try:
        if os.path.exists(_fp):
            LabelBase.register(name="CN", fn_regular=_fp, fn_bold=_fp)
            HAS_CN = True
            FONT_PATH = _fp
            break
    except Exception:
        pass
FK = {"font_name": "CN"} if HAS_CN else {}

# ============ Monkey Patch: 默认深色文字 ============
_OrgLabelInit = Label.__init__
def _PatchedLabelInit(self, **kw):
    if "color" not in kw: kw["color"] = [0.15, 0.15, 0.2, 1]
    if HAS_CN and "font_name" not in kw: kw["font_name"] = "CN"
    _OrgLabelInit(self, **kw)
Label.__init__ = _PatchedLabelInit

_OrgTIInit = TextInput.__init__
def _PatchedTIInit(self, **kw):
    if "foreground_color" not in kw: kw["foreground_color"] = [0.15, 0.15, 0.2, 1]
    if "hint_text_color" not in kw: kw["hint_text_color"] = [0.5, 0.5, 0.5, 1]
    if HAS_CN and "font_name" not in kw: kw["font_name"] = "CN"
    _OrgTIInit(self, **kw)
TextInput.__init__ = _PatchedTIInit

from datetime import datetime, date
from database import Database


# ============================================================
# 工具函数
# ============================================================
def card(widget, bg=(1, 1, 1, 1), radius=8):
    """圆角卡片背景（canvas.before 构造后手动加，不放进 __init__）"""
    with widget.canvas.before:
        Color(*bg)
        r = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(radius)])
    widget.bind(pos=lambda w, *a: setattr(r, 'pos', w.pos),
                size=lambda w, *a: setattr(r, 'size', w.size))


def toast(msg, duration=1.5):
    """居中浮动提示，自动消失"""
    box = BoxLayout()
    box.add_widget(Label(text=msg, font_size=dp(15), color=[1, 1, 1, 1], **FK))
    p = Popup(title='', content=box, size_hint=(0.75, None), size=(dp(280), dp(60)),
              background='', background_color=[0.2, 0.2, 0.2, 0.88],
              separator_height=0, auto_dismiss=True)
    p.open()
    Clock.schedule_once(lambda dt: p.dismiss(), duration)


def open_popup(popup):
    """打开弹窗 + 自动上移适配键盘"""
    last_height = [0]

    def on_kb(win, height):
        if height and height > 100:
            popup.pos_hint = {'center_x': 0.5, 'center_y': 0.68}
        else:
            popup.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        last_height[0] = height

    try:
        Window.bind(on_keyboard_height=on_kb)
    except Exception:
        pass

    def cleanup(_):
        try:
            Window.unbind(on_keyboard_height=on_kb)
        except Exception:
            pass
    popup.bind(on_dismiss=cleanup)
    popup.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
    popup.open()


# ============================================================
# 页面 1: 签到打卡
# ============================================================
class CheckinPage(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', **kw)
        self.db = Database()
        self.today_ids = set()
        # 用户选择的日期和时段
        self._sel_date = date.today()        # 默认今天
        self._sel_period = self.db.get_current_period()  # 自动选当前

        # —— 顶部：日期按钮 + 时段下拉 ——
        now = datetime.now()
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(76),
                        padding=[dp(14), dp(8), dp(14), dp(4)], spacing=dp(4))

        # 第一行：日期（可点击）
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(28), spacing=dp(8))
        self.date_btn = Button(text=self._fmt_date(self._sel_date), font_size=dp(14),
                               background_normal='', background_color=[0.88, 0.94, 1, 1],
                               color=[0.15, 0.15, 0.2, 1], size_hint_x=0.5,
                               **FK)
        self.date_btn.bind(on_press=lambda _: self._pick_date())
        row1.add_widget(self.date_btn)
        row1.add_widget(Label(text='日期 点击选日期', font_size=dp(12),
                              color=[0.5, 0.5, 0.5, 1], size_hint_x=0.5,
                              halign='right', valign='middle', **FK))
        top.add_widget(row1)

        # 第二行：时段下拉
        row2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(8))
        row2.add_widget(Label(text='时段:', font_size=dp(14), size_hint_x=None, width=dp(40),
                              halign='left', valign='middle', **FK))
        self.period_spinner = Spinner(text=self._sel_period, values=('上午', '下午', '晚上'),
                                      font_size=dp(14), size_hint_x=0.5,
                                      background_normal='', background_color=[1, 1, 1, 1],
                                      color=[0.85, 0.4, 0.2, 1], **FK)
        self.period_spinner.bind(text=lambda s, v: self._on_period_change(v))
        row2.add_widget(self.period_spinner)
        # 今天 / 重置按钮
        reset_btn = Button(text='今天', font_size=dp(12), size_hint_x=0.3,
                           background_normal='', background_color=[0.7, 0.85, 0.7, 1],
                           color=[0.15, 0.15, 0.2, 1], **FK)
        reset_btn.bind(on_press=lambda _: self._reset_today())
        row2.add_widget(reset_btn)
        top.add_widget(row2)

        self.add_widget(top)
        self.add_widget(Label(size_hint_y=None, height=dp(1), color=[0.85, 0.85, 0.85, 1]))

        # —— 班级下拉 + 统计 ——
        bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44),
                        padding=[dp(14), 0, dp(14), dp(4)], spacing=dp(8))
        bar.add_widget(Label(text='班级:', font_size=dp(14), size_hint_x=None, width=dp(42),
                             halign='left', valign='middle', color=[0.15, 0.15, 0.2, 1], **FK))
        self.cls_spinner = Spinner(text='', values=(), font_size=dp(14), size_hint_x=0.6,
                                   background_normal='', background_color=[1, 1, 1, 1],
                                   color=[0.15, 0.15, 0.2, 1], **FK)
        self.cls_spinner.bind(text=lambda s, v: self._on_class_change(v))
        bar.add_widget(self.cls_spinner)
        self.stat_lbl = Label(text='', font_size=dp(13), size_hint_x=0.4,
                              halign='right', valign='middle',
                              color=[0.2, 0.55, 0.2, 1], **FK)
        bar.add_widget(self.stat_lbl)
        self.add_widget(bar)
        self.add_widget(Label(size_hint_y=None, height=dp(1), color=[0.85, 0.85, 0.85, 1]))

        # —— 标签网格 ——
        self.scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=3, spacing=dp(6), padding=dp(10), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        self.add_widget(self.scroll)

    @staticmethod
    def _fmt_date(d):
        wd = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d.weekday()]
        return f"{d.strftime('%Y年%m月%d日')} {wd}"

    def _pick_date(self):
        """简单日期选择：输入框"""
        box = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
        box.add_widget(Label(text='输入日期 (YYYY-MM-DD)', font_size=dp(14),
                             size_hint_y=None, height=dp(24), **FK))
        ti = TextInput(text=self._sel_date.strftime('%Y-%m-%d'),
                       font_size=dp(16), multiline=False, **FK)
        box.add_widget(ti)
        # 快捷按钮
        quick = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
        def mk_qt(delta, label):
            def go(_):
                d = date.today() + __import__('datetime').timedelta(days=delta)
                ti.text = d.strftime('%Y-%m-%d')
            btn = Button(text=label, font_size=dp(12), background_normal='',
                         background_color=[0.88, 0.94, 1, 1],
                         color=[0.15, 0.15, 0.2, 1], on_press=go, **FK)
            quick.add_widget(btn)
        mk_qt(-7, '-7天')
        mk_qt(-1, '昨天')
        mk_qt(0, '今天')
        mk_qt(1, '明天')
        mk_qt(7, '+7天')
        box.add_widget(quick)

        def confirm(_):
            try:
                parts = ti.text.strip().split('-')
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                self._sel_date = d
                self.date_btn.text = self._fmt_date(d)
                popup.dismiss()
                self._on_class_change(self.cls_spinner.text)
            except Exception:
                toast('日期格式错误，请用 YYYY-MM-DD', 2)

        btns = BoxLayout(orientation='horizontal', spacing=dp(10),
                         size_hint_y=None, height=dp(44))
        btns.add_widget(Button(text='[OK] 确定', font_size=dp(14), background_normal='',
                               background_color=get_color_from_hex('#2E7D32'),
                               color=[1, 1, 1, 1], on_press=confirm, **FK))
        btns.add_widget(Button(text='取消', font_size=dp(14), background_normal='',
                               background_color=get_color_from_hex('#999999'),
                               color=[1, 1, 1, 1],
                               on_press=lambda _: popup.dismiss(), **FK))
        box.add_widget(btns)
        popup = Popup(title='', content=box, size_hint=(0.85, 0.5),
                      background='', background_color=[1, 1, 1, 1])
        open_popup(popup)

    def _reset_today(self):
        self._sel_date = date.today()
        self._sel_period = self.db.get_current_period()
        self.date_btn.text = self._fmt_date(self._sel_date)
        self.period_spinner.text = self._sel_period
        self._on_class_change(self.cls_spinner.text)
        toast('[OK] 已重置为今天')

    def _on_period_change(self, p):
        self._sel_period = p
        if self.cls_spinner.text:
            self._on_class_change(self.cls_spinner.text)

    def _refresh_today(self):
        """按所选日期+时段刷新已签到学生"""
        dstr = self._sel_date.strftime('%Y-%m-%d')
        c = self.db.conn.cursor()
        if self._sel_period == '上午':
            c.execute("SELECT student_id FROM checkins WHERE date(checkin_time)=? AND period=?",
                      (dstr, '上午'))
        elif self._sel_period == '下午':
            c.execute("SELECT student_id FROM checkins WHERE date(checkin_time)=? AND period=?",
                      (dstr, '下午'))
        else:
            c.execute("SELECT student_id FROM checkins WHERE date(checkin_time)=? AND period=?",
                      (dstr, '晚上'))
        self.today_ids = {r[0] for r in c.fetchall()}

    def _fetch(self, cls_name):
        c = self.db.conn.cursor()
        if cls_name == '全部班级':
            c.execute(
                "SELECT s.*, c.name as class_name FROM students s "
                "LEFT JOIN classes c ON s.class_id=c.id "
                "ORDER BY s.pinyin_initial, s.name")
        elif cls_name == '未分组':
            c.execute(
                "SELECT s.*, c.name as class_name FROM students s "
                "LEFT JOIN classes c ON s.class_id=c.id WHERE s.class_id IS NULL "
                "ORDER BY s.pinyin_initial, s.name")
        else:
            c.execute(
                "SELECT s.*, c.name as class_name FROM students s "
                "LEFT JOIN classes c ON s.class_id=c.id WHERE c.name=? "
                "ORDER BY s.pinyin_initial, s.name", (cls_name,))
        return [dict(r) for r in c.fetchall()]

    def _on_class_change(self, cls_name):
        if not cls_name:
            return
        students = self._fetch(cls_name)
        self._render(students)

    def _render(self, students):
        self.grid.clear_widgets()
        self._refresh_today()
        done_count = sum(1 for s in students if s['id'] in self.today_ids)

        if not students:
            self.grid.add_widget(Label(text='该班级暂无学生', font_size=dp(15),
                                       color=[0.5, 0.5, 0.5, 1], size_hint_y=None,
                                       height=dp(80), **FK))
            self.stat_lbl.text = ''
            return

        for s in students:
            sid = s['id']
            is_done = sid in self.today_ids
            bg = [0.2, 0.75, 0.3, 1] if is_done else [1, 1, 1, 1]
            fg = [1, 1, 1, 1] if is_done else [0.15, 0.15, 0.2, 1]
            btn = Button(text=s['name'], font_size=dp(18), bold=True,
                         size_hint_y=None, height=dp(50),
                         background_normal='', background_color=bg, color=fg,
                         halign='center', valign='middle', padding=[0, dp(10)], **FK)

            def mk_press(st=s, b=btn):
                def pressed(_):
                    if st['id'] in self.today_ids:
                        # 已签到 → 撤销
                        ok = self.db.undo_checkin_in_period(st['id'], self._sel_date, self._sel_period)
                        if ok:
                            toast(f"<- {st['name']} 已撤销签到，课时 +1")
                            b.background_color = [1, 1, 1, 1]
                            b.color = [0.15, 0.15, 0.2, 1]
                            self.today_ids.discard(st['id'])
                        else:
                            toast("撤销失败")
                    else:
                        # 未签到 → 签到
                        t = datetime.combine(self._sel_date, datetime.now().time())
                        self.db.checkin(st['id'], period=self._sel_period, t=t)
                        toast(f"[OK] {st['name']} {self._sel_period}签到成功")
                        b.background_color = [0.2, 0.75, 0.3, 1]
                        b.color = [1, 1, 1, 1]
                        self.today_ids.add(st['id'])

                    self.stat_lbl.text = f"已签到 {len(self.today_ids)}"
                    # 同步刷新学生资料页
                    try:
                        from kivy.app import App
                        app = App.get_running_app()
                        if hasattr(app, 'hp'):
                            app.hp.refresh()
                    except Exception:
                        pass
                return pressed
            btn.bind(on_press=mk_press())
            self.grid.add_widget(btn)

        self._current_students = students
        self.stat_lbl.text = f"已签到 {done_count}"

    def refresh(self):
        c = self.db.conn.cursor()
        c.execute("SELECT name FROM classes ORDER BY sort_order, id")
        cls_names = [r[0] for r in c.fetchall()]
        values = ['全部班级'] + cls_names + ['未分组']
        self.cls_spinner.values = values
        if self.cls_spinner.text not in values:
            self.cls_spinner.text = '全部班级'
        else:
            self._on_class_change(self.cls_spinner.text)


# ============================================================
# 页面 2: 学生资料（左侧）
# ============================================================
class HistoryPage(BoxLayout):
    def _sync_checkin(self):
        """添加/删除学生或班级后，刷新签到打卡页"""
        try:
            from kivy.app import App
            app = App.get_running_app()
            if hasattr(app, 'cp'):
                app.cp.refresh()
        except Exception:
            pass

    def __init__(self, **kw):
        super().__init__(orientation='vertical', **kw)
        self.db = Database()

        # —— 搜索 + 管理按钮 ——
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(90),
                        padding=[dp(12), dp(8), dp(12), dp(4)], spacing=dp(4))
        self.search_input = TextInput(hint_text='搜索学生名字...', font_size=dp(13),
                                      size_hint_y=None, height=dp(34),
                                      multiline=False, padding=[dp(10), dp(6)], **FK)
        self.search_input.bind(text=lambda s, v: self.refresh())
        top.add_widget(self.search_input)
        btns = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        btn_s = Button(text='学生管理', font_size=dp(14), background_normal='',
                       background_color=get_color_from_hex('#2E7D32'), color=[1, 1, 1, 1], **FK)
        btn_s.bind(on_press=lambda _: self._manage_students())
        btns.add_widget(btn_s)
        btn_c = Button(text='班级管理', font_size=dp(14), background_normal='',
                       background_color=get_color_from_hex('#F57C00'), color=[1, 1, 1, 1], **FK)
        btn_c.bind(on_press=lambda _: self._manage_classes())
        btns.add_widget(btn_c)
        top.add_widget(btns)
        self.add_widget(top)
        self.add_widget(Label(size_hint_y=None, height=dp(1), color=[0.85, 0.85, 0.85, 1]))

        # —— 列表 ——
        self.scroll = ScrollView(do_scroll_x=False)
        self.list_c = BoxLayout(orientation='vertical', size_hint_y=None,
                                spacing=dp(6), padding=dp(10))
        self.list_c.bind(minimum_height=self.list_c.setter('height'))
        self.scroll.add_widget(self.list_c)
        self.add_widget(self.scroll)

    # ----- 主列表刷新 -----
    def refresh(self):
        q = self.search_input.text.strip() or None
        groups = self.db.get_students_grouped(search=q)
        self.list_c.clear_widgets()
        if not groups:
            self.list_c.add_widget(Label(text='暂无学生，点击"学生管理"添加',
                                         font_size=dp(15), color=[0.5, 0.5, 0.5, 1],
                                         size_hint_y=None, height=dp(80), **FK))
            return
        for g in groups:
            cls = g['class']
            # 班级标题
            title = Label(
                text=f"[b][size=15]分组 {cls['name']}[/size][/b]  ({len(g['students'])}人)",
                markup=True, halign='left', valign='middle',
                color=[0.25, 0.3, 0.5, 1], size_hint_y=None, height=dp(30), **FK)
            title.bind(size=title.setter('text_size'))
            self.list_c.add_widget(title)
            if not g['students']:
                self.list_c.add_widget(Label(text='  （暂无学生）', font_size=dp(13),
                                             color=[0.6, 0.6, 0.6, 1], size_hint_y=None,
                                             height=dp(24), halign='left', valign='middle', **FK))
            for st in g['students']:
                self.list_c.add_widget(self._student_row(st))

    def _student_row(self, st):
        """一个学生单行显示：名字 + 剩余课时"""
        outer = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42),
                          padding=[dp(14), dp(0)], spacing=dp(10))
        card(outer, bg=(1, 1, 1, 1))

        def on_touch_down(instance, touch):
            if instance.collide_point(*touch.pos):
                instance._pressed = True
                return False

        def on_touch_up(instance, touch):
            pressed = getattr(instance, '_pressed', False)
            instance._pressed = False
            if pressed and instance.collide_point(*touch.pos):
                self._open_detail(st)

        outer.bind(on_touch_down=on_touch_down, on_touch_up=on_touch_up)

        outer.add_widget(Label(text=st['name'], bold=True, font_size=dp(15),
                                halign='left', valign='middle', size_hint_x=0.6,
                                text_size=(None, dp(42)), **FK))
        outer.add_widget(Label(text=f"剩余{st['remaining_hours']}课时", font_size=dp(13),
                               color=[0.2, 0.55, 0.2, 1], size_hint_x=0.4,
                               halign='right', valign='middle',
                               text_size=(None, dp(42)), **FK))
        return outer

    # ----- 学生详情弹窗 -----
    def _open_detail(self, st):
        stats = self.db.get_student_stats(st['id'])
        if not stats:
            return

        box = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(8))
        card(box, bg=(0.98, 0.98, 0.99, 1))

        box.add_widget(Label(text=st['name'], bold=True, font_size=dp(20),
                             size_hint_y=None, height=dp(40), halign='left', valign='middle', **FK))
        cn = st.get('class_name') or '未分组'
        box.add_widget(Label(text=f"班级：{cn}", font_size=dp(14), color=[0.45, 0.45, 0.5, 1],
                             size_hint_y=None, height=dp(22), halign='left', valign='middle', **FK))

        # 三个统计卡片
        stat_row = BoxLayout(orientation='horizontal', spacing=dp(8), size_hint_y=None, height=dp(70))
        for label, val, col in [
            ('剩余课时', st['remaining_hours'], '#2E7D32'),
            ('累计上课', stats['total'], '#1565C0'),
            ('总充值', st['total_hours'], '#E65100'),
        ]:
            cb = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(2))
            card(cb, bg=(1, 1, 1, 1))
            cb.add_widget(Label(text=label, font_size=dp(12), color=[0.5, 0.5, 0.5, 1],
                                size_hint_y=None, height=dp(20), **FK))
            cb.add_widget(Label(text=f"[b][color={col}][size=24]{val}[/size][/color][/b]",
                                markup=True, **FK))
            stat_row.add_widget(cb)
        box.add_widget(stat_row)

        # 时段统计
        ps = stats['period_stats']
        box.add_widget(Label(
            text=f"上午 {ps.get('上午', 0)}节  ·  下午 {ps.get('下午', 0)}节  ·  晚上 {ps.get('晚上', 0)}节",
            font_size=dp(13), color=[0.3, 0.35, 0.4, 1],
            size_hint_y=None, height=dp(22), halign='center', valign='middle', **FK))

        # 充值区
        recharge_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(8))
        recharge_row.add_widget(Label(text='课时充值:', font_size=dp(14), size_hint_x=0.3,
                                      halign='left', valign='middle', **FK))
        hi = TextInput(hint_text='输入数量', font_size=dp(14), multiline=False,
                       input_filter='int', **FK)
        recharge_row.add_widget(hi)

        def do_recharge(_):
            h = int(hi.text) if hi.text.strip() else 0
            if h > 0:
                self.db.add_hours(st['id'], h)
                popup.dismiss()
                toast(f"[OK] 充值 {h} 课时成功")
                self._open_detail(self.db.get_student(st['id']))
                self.refresh()

        recharge_row.add_widget(Button(text='[OK] 充值', font_size=dp(14), background_normal='',
                                       background_color=get_color_from_hex('#2E7D32'),
                                       color=[1, 1, 1, 1], size_hint_x=0.25,
                                       on_press=do_recharge, **FK))
        box.add_widget(recharge_row)

        # 考勤历史标题
        box.add_widget(Label(
            text=f"[b]考勤历史[/b] （共 {len(stats['all_checkins'])} 次）",
            markup=True, font_size=dp(14), size_hint_y=None, height=dp(26),
            halign='left', valign='middle', **FK))

        # 考勤历史列表（可滚动）
        scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
        hist = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        hist.bind(minimum_height=hist.setter('height'))

        all_checkins = stats['all_checkins']
        if not all_checkins:
            hist.add_widget(Label(text='暂无考勤记录', font_size=dp(14),
                                  color=[0.5, 0.5, 0.5, 1], size_hint_y=None, height=dp(50), **FK))
        for ch in all_checkins:
            ch_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(52),
                               padding=[dp(12), dp(6)], spacing=dp(2))
            card(ch_box, bg=(1, 1, 1, 1))
            ct = ch['checkin_time'][:10]
            hm = ch['checkin_time'][11:16]
            period = ch['period']
            ch_box.add_widget(Label(text=f"{ct}  ·  {period}", bold=True,
                                    font_size=dp(14), halign='left', valign='middle',
                                    size_hint_y=None, height=dp(22), **FK))
            ch_box.add_widget(Label(text=f"时间 {hm} 签到", font_size=dp(13),
                                    color=[0.45, 0.45, 0.5, 1],
                                    halign='left', valign='middle',
                                    size_hint_y=None, height=dp(20), **FK))
            hist.add_widget(ch_box)

        scroll.add_widget(hist)
        box.add_widget(scroll)

        # 底部按钮
        bottom = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))

        def do_delete(_):
            box2 = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
            box2.add_widget(Label(text=f"确定删除学生 '{st['name']}' 吗？", font_size=dp(15), **FK))

            def yes(_):
                self.db.delete_student(st['id'])
                popup2.dismiss()
                popup.dismiss()
                self.refresh()
                toast("[OK] 学生已删除")

            btns = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(44))
            btns.add_widget(Button(text='[X] 删除', font_size=dp(14), background_normal='',
                                   background_color=get_color_from_hex('#C62828'),
                                   color=[1, 1, 1, 1], on_press=yes, **FK))
            btns.add_widget(Button(text='取消', font_size=dp(14), background_normal='',
                                   background_color=get_color_from_hex('#999999'),
                                   color=[1, 1, 1, 1],
                                   on_press=lambda _: popup2.dismiss(), **FK))
            box2.add_widget(btns)
            popup2 = Popup(title='', content=box2, size_hint=(0.85, 0.3))
            open_popup(popup2)

        bottom.add_widget(Button(text='删除学生', font_size=dp(14), background_normal='',
                                 background_color=get_color_from_hex('#C62828'),
                                 color=[1, 1, 1, 1], on_press=do_delete, **FK))
        bottom.add_widget(Button(text='关闭', font_size=dp(14), background_normal='',
                                 background_color=get_color_from_hex('#999999'),
                                 color=[1, 1, 1, 1],
                                 on_press=lambda _: popup.dismiss(), **FK))
        box.add_widget(bottom)

        popup = Popup(title='', content=box, size_hint=(0.95, 0.92))
        open_popup(popup)

    # ----- 学生管理弹窗 -----
    def _manage_students(self):
        box = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))
        card(box, bg=(0.98, 0.98, 0.99, 1))
        box.add_widget(Label(text='[b][size=17]学生管理[/size][/b]', markup=True,
                             size_hint_y=None, height=dp(32), **FK))

        top = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        add_btn = Button(text='＋ 添加学生', font_size=dp(14), background_normal='',
                         background_color=get_color_from_hex('#2E7D32'),
                         color=[1, 1, 1, 1], **FK)
        top.add_widget(add_btn)
        close_btn = Button(text='关闭', font_size=dp(14), background_normal='',
                           background_color=get_color_from_hex('#999999'),
                           color=[1, 1, 1, 1], **FK)
        top.add_widget(close_btn)
        box.add_widget(top)

        scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
        grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        def _refresh_list():
            grid.clear_widgets()
            all_s = self.db.get_all_students()
            if not all_s:
                grid.add_widget(Label(text='暂无学生', font_size=dp(14),
                                      color=[0.5, 0.5, 0.5, 1], size_hint_y=None,
                                      height=dp(50), **FK))
                return
            for s in all_s:
                cn = s.get('class_name') or '未分组'
                row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
                row.add_widget(Label(
                    text=f"  {s['name']}  ({cn})  剩余{s['remaining_hours']}课时",
                    font_size=dp(14), halign='left', valign='middle', size_hint_x=0.7, **FK))

                def mk_del(sid=s['id'], nm=s['name']):
                    def do_del(_):
                        box2 = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
                        box2.add_widget(Label(text=f"确定删除学生 '{nm}' 吗？",
                                              font_size=dp(14), **FK))

                        def yes(_):
                            self.db.delete_student(sid)
                            popup2.dismiss()
                            _refresh_list()
                            self.refresh()

                        btns = BoxLayout(orientation='horizontal', spacing=dp(10),
                                         size_hint_y=None, height=dp(44))
                        btns.add_widget(Button(text='[X] 删除', font_size=dp(14),
                                               background_normal='',
                                               background_color=get_color_from_hex('#C62828'),
                                               color=[1, 1, 1, 1], on_press=yes, **FK))
                        btns.add_widget(Button(text='取消', font_size=dp(14),
                                               background_normal='',
                                               background_color=get_color_from_hex('#999999'),
                                               color=[1, 1, 1, 1],
                                               on_press=lambda _: popup2.dismiss(), **FK))
                        box2.add_widget(btns)
                        popup2 = Popup(title='', content=box2, size_hint=(0.85, 0.3))
                        open_popup(popup2)
                    return do_del

                row.add_widget(Button(text='删除', font_size=dp(13), size_hint_x=0.3,
                                      background_normal='',
                                      background_color=get_color_from_hex('#C62828'),
                                      color=[1, 1, 1, 1], on_press=mk_del(), **FK))
                grid.add_widget(row)

        _refresh_list()
        scroll.add_widget(grid)
        box.add_widget(scroll)

        popup = Popup(title='', content=box, size_hint=(0.95, 0.85))

        def _add_student(_):
            popup.dismiss()
            cls_names = [c['name'] for c in self.db.get_all_classes()] + ['未分组']
            a_box = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
            a_box.add_widget(Label(text='[b]添加学生[/b]', markup=True, font_size=dp(16),
                                   size_hint_y=None, height=dp(30), **FK))
            ni = TextInput(hint_text='学生姓名', font_size=dp(15), multiline=False, **FK)
            a_box.add_widget(ni)
            cls_sp = Spinner(text='选择班级', values=cls_names, font_size=dp(14),
                             background_normal='', background_color=[1, 1, 1, 1],
                             color=[0.15, 0.15, 0.2, 1], **FK)
            a_box.add_widget(cls_sp)
            hi = TextInput(hint_text='初始课时（可留空）', font_size=dp(15),
                           multiline=False, input_filter='int', **FK)
            a_box.add_widget(hi)

            def do_save(_):
                nm = ni.text.strip()
                if not nm:
                    return
                cls_id = None
                for c in self.db.get_all_classes():
                    if c['name'] == cls_sp.text:
                        cls_id = c['id']
                        break
                hours = int(hi.text) if hi.text.strip() else 0
                self.db.add_student(nm, cls_id, hours)
                a_popup.dismiss()
                toast(f"[OK] {nm} 添加成功")
                self._manage_students()
                self.refresh()
                self._sync_checkin()

            btns = BoxLayout(orientation='horizontal', spacing=dp(10),
                             size_hint_y=None, height=dp(44))
            btns.add_widget(Button(text='[OK] 保存', font_size=dp(14), background_normal='',
                                   background_color=get_color_from_hex('#2E7D32'),
                                   color=[1, 1, 1, 1], on_press=do_save, **FK))
            btns.add_widget(Button(text='取消', font_size=dp(14), background_normal='',
                                   background_color=get_color_from_hex('#999999'),
                                   color=[1, 1, 1, 1],
                                   on_press=lambda _: a_popup.dismiss(), **FK))
            a_box.add_widget(btns)
            a_popup = Popup(title='', content=a_box, size_hint=(0.85, 0.5))
            open_popup(a_popup)

        add_btn.bind(on_press=_add_student)
        close_btn.bind(on_press=lambda _: (popup.dismiss(), self.refresh()))
        open_popup(popup)

    # ----- 班级管理弹窗 -----
    def _manage_classes(self):
        box = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))
        card(box, bg=(0.98, 0.98, 0.99, 1))
        box.add_widget(Label(text='[b][size=17]班级管理[/size][/b]', markup=True,
                             size_hint_y=None, height=dp(32), **FK))

        top = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        add_btn = Button(text='＋ 添加班级', font_size=dp(14), background_normal='',
                         background_color=get_color_from_hex('#2E7D32'),
                         color=[1, 1, 1, 1], **FK)
        top.add_widget(add_btn)
        close_btn = Button(text='关闭', font_size=dp(14), background_normal='',
                           background_color=get_color_from_hex('#999999'),
                           color=[1, 1, 1, 1], **FK)
        top.add_widget(close_btn)
        box.add_widget(top)

        scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
        grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        def _refresh_list():
            grid.clear_widgets()
            cls_list = self.db.get_all_classes()
            if not cls_list:
                grid.add_widget(Label(text='暂无班级', font_size=dp(14),
                                      color=[0.5, 0.5, 0.5, 1], size_hint_y=None,
                                      height=dp(50), **FK))
                return
            for cls in cls_list:
                cnt = len(self.db.get_students_by_class(cls['id']))
                row = BoxLayout(orientation='horizontal', size_hint_y=None,
                                height=dp(42), spacing=dp(6))
                row.add_widget(Label(text=f"  {cls['name']}  ({cnt}人)", font_size=dp(14),
                                     halign='left', valign='middle',
                                     size_hint_x=0.45, **FK))

                def mk_rename(cid=cls['id'], nm=cls['name']):
                    def do_rename(_):
                        box2 = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
                        box2.add_widget(Label(text='重命名班级', font_size=dp(14),
                                              size_hint_y=None, height=dp(24), **FK))
                        ni = TextInput(text=nm, font_size=dp(15), multiline=False, **FK)
                        box2.add_widget(ni)

                        def save(_):
                            if ni.text.strip():
                                self.db.update_class(cid, ni.text.strip())
                                popup2.dismiss()
                                _refresh_list()
                                self.refresh()

                        btns = BoxLayout(orientation='horizontal', spacing=dp(10),
                                         size_hint_y=None, height=dp(44))
                        btns.add_widget(Button(text='[OK] 保存', font_size=dp(14),
                                               background_normal='',
                                               background_color=get_color_from_hex('#1565C0'),
                                               color=[1, 1, 1, 1], on_press=save, **FK))
                        btns.add_widget(Button(text='取消', font_size=dp(14),
                                               background_normal='',
                                               background_color=get_color_from_hex('#999999'),
                                               color=[1, 1, 1, 1],
                                               on_press=lambda _: popup2.dismiss(), **FK))
                        box2.add_widget(btns)
                        popup2 = Popup(title='', content=box2, size_hint=(0.8, 0.35))
                        open_popup(popup2)
                    return do_rename

                row.add_widget(Button(text='重命名', font_size=dp(12), size_hint_x=0.275,
                                      background_normal='',
                                      background_color=get_color_from_hex('#1565C0'),
                                      color=[1, 1, 1, 1], on_press=mk_rename(), **FK))

                def mk_del(cid=cls['id'], nm=cls['name']):
                    def do_del(_):
                        box2 = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
                        box2.add_widget(Label(
                            text=f"删除 '{nm}' ？\n该班学生将变为未分组",
                            font_size=dp(13), **FK))

                        def yes(_):
                            self.db.delete_class(cid)
                            popup2.dismiss()
                            _refresh_list()
                            self.refresh()

                        btns = BoxLayout(orientation='horizontal', spacing=dp(10),
                                         size_hint_y=None, height=dp(44))
                        btns.add_widget(Button(text='[X] 删除', font_size=dp(14),
                                               background_normal='',
                                               background_color=get_color_from_hex('#C62828'),
                                               color=[1, 1, 1, 1], on_press=yes, **FK))
                        btns.add_widget(Button(text='取消', font_size=dp(14),
                                               background_normal='',
                                               background_color=get_color_from_hex('#999999'),
                                               color=[1, 1, 1, 1],
                                               on_press=lambda _: popup2.dismiss(), **FK))
                        box2.add_widget(btns)
                        popup2 = Popup(title='', content=box2, size_hint=(0.85, 0.35))
                        open_popup(popup2)
                    return do_del

                row.add_widget(Button(text='删除', font_size=dp(12), size_hint_x=0.275,
                                      background_normal='',
                                      background_color=get_color_from_hex('#C62828'),
                                      color=[1, 1, 1, 1], on_press=mk_del(), **FK))
                grid.add_widget(row)

        _refresh_list()
        scroll.add_widget(grid)
        box.add_widget(scroll)

        popup = Popup(title='', content=box, size_hint=(0.95, 0.85))

        def _add_class(_):
            popup.dismiss()
            a_box = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
            a_box.add_widget(Label(text='[b]添加班级[/b]', markup=True, font_size=dp(16),
                                   size_hint_y=None, height=dp(30), **FK))
            ni = TextInput(hint_text='班级名称', font_size=dp(15), multiline=False, **FK)
            a_box.add_widget(ni)

            def do_save(_):
                nm = ni.text.strip()
                if nm:
                    rid = self.db.add_class(nm)
                    a_popup.dismiss()
                    if rid:
                        toast(f"[OK] 班级 '{nm}' 添加成功")
                    else:
                        toast("该班级已存在", 2.0)
                    self._manage_classes()
                    self.refresh()

            btns = BoxLayout(orientation='horizontal', spacing=dp(10),
                             size_hint_y=None, height=dp(44))
            btns.add_widget(Button(text='[OK] 保存', font_size=dp(14), background_normal='',
                                   background_color=get_color_from_hex('#2E7D32'),
                                   color=[1, 1, 1, 1], on_press=do_save, **FK))
            btns.add_widget(Button(text='取消', font_size=dp(14), background_normal='',
                                   background_color=get_color_from_hex('#999999'),
                                   color=[1, 1, 1, 1],
                                   on_press=lambda _: a_popup.dismiss(), **FK))
            a_box.add_widget(btns)
            a_popup = Popup(title='', content=a_box, size_hint=(0.8, 0.35))
            open_popup(a_popup)

        add_btn.bind(on_press=_add_class)
        close_btn.bind(on_press=lambda _: (popup.dismiss(), self.refresh()))
        open_popup(popup)


# ============================================================
# 页面 3: 设置（右侧）
# ============================================================
class SettingsPage(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', **kw)
        self.db = Database()

        self.container = BoxLayout(orientation='vertical', padding=dp(10),
                                   spacing=dp(10))

        self._build_period_section()
        self._build_export_section()
        self._build_clear_section()

        self.add_widget(self.container)

    # ----- 时间段 -----
    def _build_period_section(self):
        box = BoxLayout(orientation='vertical', spacing=dp(6),
                        padding=[dp(10), dp(10), dp(10), dp(10)])
        card(box, bg=(1, 1, 1, 1))
        box.add_widget(Label(text='[b][size=15]打卡时间段[/size][/b]', markup=True,
                             size_hint_y=None, height=dp(26), halign='left', valign='middle', **FK))
        s = self.db.get_all_period_settings()
        self.period_inputs = {}
        for label, sk, ek in [('上午', 'morning_start', 'morning_end'),
                              ('下午', 'afternoon_start', 'afternoon_end'),
                              ('晚上', 'evening_start', 'evening_end')]:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(6))
            row.add_widget(Label(text=f"{label}：", font_size=dp(13), size_hint_x=None,
                                 width=dp(44), halign='left', valign='middle', **FK))
            ti1 = TextInput(text=s.get(sk, ''), font_size=dp(13), multiline=False,
                            size_hint_x=0.4, padding=[dp(6), dp(6)], **FK)
            row.add_widget(ti1)
            row.add_widget(Label(text='—', font_size=dp(14), size_hint_x=None,
                                 width=dp(14), halign='center', valign='middle', **FK))
            ti2 = TextInput(text=s.get(ek, ''), font_size=dp(13), multiline=False,
                            size_hint_x=0.4, padding=[dp(6), dp(6)], **FK)
            row.add_widget(ti2)
            self.period_inputs[sk] = ti1
            self.period_inputs[ek] = ti2
            box.add_widget(row)

        save_btn = Button(text='[OK] 保存时间段', font_size=dp(13), background_normal='',
                          background_color=get_color_from_hex('#2E7D32'), color=[1, 1, 1, 1],
                          size_hint_y=None, height=dp(34), **FK)

        def save_period(_):
            for k, ti in self.period_inputs.items():
                self.db.set_setting(k, ti.text.strip())
            toast("[OK] 设置已保存")

        save_btn.bind(on_press=save_period)
        box.add_widget(save_btn)
        box.size_hint_y = 0.42
        self.container.add_widget(box)

    # ----- 导出 -----
    def _build_export_section(self):
        box = BoxLayout(orientation='vertical', spacing=dp(6),
                        padding=[dp(10), dp(10), dp(10), dp(10)])
        card(box, bg=(1, 1, 1, 1))
        box.add_widget(Label(text='[b][size=15]数据导出[/size][/b]', markup=True,
                             size_hint_y=None, height=dp(26), halign='left', valign='middle', **FK))
        box.add_widget(Label(text='导出学生资料和签到记录为 Excel',
                             font_size=dp(12), color=[0.5, 0.5, 0.5, 1],
                             size_hint_y=None, height=dp(18),
                             halign='left', valign='middle', **FK))
        btn = Button(text='导出 Excel', font_size=dp(13), background_normal='',
                     background_color=get_color_from_hex('#2E7D32'), color=[1, 1, 1, 1],
                     size_hint_y=None, height=dp(34), **FK)

        def do_export(_):
            import os as _os
            from datetime import datetime as _dt
            ebox = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
            ebox.add_widget(Label(text='导出数据', font_size=dp(15),
                                  size_hint_y=None, height=dp(26), **FK))
            ebox.add_widget(Label(text='保存位置:', font_size=dp(13),
                                  size_hint_y=None, height=dp(22), halign='left', **FK))
            dir_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            dir_ti = TextInput(text=_os.path.expanduser('~'), font_size=dp(13),
                               multiline=False, size_hint_x=0.75, **FK)
            dir_row.add_widget(dir_ti)

            def pick_dir(_):
                try:
                    from tkinter import Tk, filedialog
                    root_tk = Tk()
                    root_tk.withdraw()
                    chosen = filedialog.askdirectory(initialdir=dir_ti.text)
                    root_tk.destroy()
                    if chosen:
                        dir_ti.text = chosen
                except Exception as ex:
                    toast(f"无法打开选择器: {ex}", 2)

            pick_btn = Button(text='选择', font_size=dp(13), size_hint_x=0.25,
                              background_normal='',
                              background_color=get_color_from_hex('#1565C0'),
                              color=[1, 1, 1, 1], on_press=pick_dir, **FK)
            dir_row.add_widget(pick_btn)
            ebox.add_widget(dir_row)
            ebox.add_widget(Label(text='文件名:', font_size=dp(13),
                                  size_hint_y=None, height=dp(22), halign='left', **FK))
            name_ti = TextInput(
                text=f"学生签到数据_{_dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                font_size=dp(13), multiline=False, **FK)
            ebox.add_widget(name_ti)

            def do_save(_):
                d = dir_ti.text.strip()
                n = name_ti.text.strip()
                if not d or not n:
                    return
                if not n.endswith('.xlsx'):
                    n += '.xlsx'
                fp = _os.path.join(d, n)
                try:
                    self.db.export_to_excel(fp)
                    epopup.dismiss()
                    toast(f"[OK] 导出成功\n{fp}", 2.5)
                except Exception as ex:
                    toast(f"导出失败：{ex}", 2.5)

            btns = BoxLayout(orientation='horizontal', spacing=dp(10),
                             size_hint_y=None, height=dp(44))
            btns.add_widget(Button(text='[OK] 确认导出', font_size=dp(14),
                                   background_normal='',
                                   background_color=get_color_from_hex('#2E7D32'),
                                   color=[1, 1, 1, 1], on_press=do_save, **FK))
            btns.add_widget(Button(text='取消', font_size=dp(14),
                                   background_normal='',
                                   background_color=get_color_from_hex('#999999'),
                                   color=[1, 1, 1, 1],
                                   on_press=lambda _: epopup.dismiss(), **FK))
            ebox.add_widget(btns)
            epopup = Popup(title='', content=ebox, size_hint=(0.9, 0.6))
            open_popup(epopup)

        btn.bind(on_press=do_export)
        box.add_widget(btn)
        box.size_hint_y = 0.28
        self.container.add_widget(box)

    # ----- 清除 -----
    def _build_clear_section(self):
        box = BoxLayout(orientation='vertical', spacing=dp(6),
                        padding=[dp(10), dp(10), dp(10), dp(10)])
        card(box, bg=(1, 1, 1, 1))
        box.add_widget(Label(text='[b][size=15]危险操作[/size][/b]', markup=True,
                             size_hint_y=None, height=dp(26), halign='left', valign='middle',
                             color=[0.8, 0.2, 0.2, 1], **FK))
        btn = Button(text='清除所有数据', font_size=dp(13), background_normal='',
                     background_color=get_color_from_hex('#C62828'), color=[1, 1, 1, 1],
                     size_hint_y=None, height=dp(34), **FK)

        def do_clear(_):
            cbox = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
            cbox.add_widget(Label(text='清除所有数据？', font_size=dp(16),
                                   size_hint_y=None, height=dp(28), **FK))
            cbox.add_widget(Label(
                text='将删除所有学生、签到记录和班级。\n'
                     '时间段设置会保留。\n\n'
                     '请输入"清除"两个字确认：',
                font_size=dp(13), color=[0.5, 0.5, 0.5, 1], **FK))
            ti = TextInput(hint_text='清除', font_size=dp(18), multiline=False, **FK)
            cbox.add_widget(ti)

            def confirm(_):
                if ti.text.strip() == '清除':
                    self.db.clear_all_data(clear_classes=True)
                    cpopup.dismiss()
                    toast("[OK] 已清除所有数据", 2.5)
                else:
                    toast('请输入正确的"清除"', 1.5)

            btns = BoxLayout(orientation='horizontal', spacing=dp(10),
                             size_hint_y=None, height=dp(44))
            btns.add_widget(Button(text='[X] 确认清除', font_size=dp(14),
                                   background_normal='',
                                   background_color=get_color_from_hex('#C62828'),
                                   color=[1, 1, 1, 1], on_press=confirm, **FK))
            btns.add_widget(Button(text='取消', font_size=dp(14),
                                   background_normal='',
                                   background_color=get_color_from_hex('#999999'),
                                   color=[1, 1, 1, 1],
                                   on_press=lambda _: cpopup.dismiss(), **FK))
            cbox.add_widget(btns)
            cpopup = Popup(title='', content=cbox, size_hint=(0.9, 0.5))
            open_popup(cpopup)

        btn.bind(on_press=do_clear)
        box.add_widget(btn)
        box.size_hint_y = 0.30
        self.container.add_widget(box)


# ============================================================
# 主应用
# ============================================================
class MainApp(App):
    def build(self):
        root = BoxLayout(orientation='vertical')

        self.cp = CheckinPage()
        self.hp = HistoryPage()
        self.sp = SettingsPage()
        self._pages = [self.hp, self.cp, self.sp]
        self._current_idx = None

        # —— 自定义底部导航栏 ——
        nav = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(56),
                        spacing=0, padding=[0, 0, 0, 0])
        self._nav_btns = []
        tab_defs = [
            ('学生资料', get_color_from_hex('#1565C0')),
            ('签到打卡', get_color_from_hex('#2E7D32')),
            ('设置',     get_color_from_hex('#C62828')),
        ]
        for i, (label, color) in enumerate(tab_defs):
            btn = Button(text=label, font_size=dp(15), bold=True, size_hint_x=1,
                         background_normal='', background_color=color,
                         color=[1, 1, 1, 1], **FK)

            def mk_press(idx=i, b=btn, c=color):
                def pressed(_):
                    self._switch_to(idx)
                    self._highlight(b, c)
                return pressed
            btn.bind(on_press=mk_press())
            self._nav_btns.append((btn, color))
            nav.add_widget(btn)

        root.add_widget(nav)  # nav 在最底部

        self._root = root
        self._bg_cache = {}  # page -> (rect, color)

        # 默认：签到打卡页（index 1）
        self._switch_to(1)
        self._highlight(self._nav_btns[1][0], self._nav_btns[1][1])

        # 延迟初始化 + 背景（等布局完成）
        Clock.schedule_once(lambda dt: self.cp.refresh(), 0.2)
        Clock.schedule_once(lambda dt: self.hp.refresh(), 0.2)

        # 页面主题色（延迟设置，等布局完成后用 Rectangle 铺满）
        Clock.schedule_once(lambda dt: self._setup_bg(self.hp, [0.92, 0.96, 1.0, 1.0]), 0.3)
        Clock.schedule_once(lambda dt: self._setup_bg(self.cp, [0.92, 1.0, 0.94, 1.0]), 0.3)
        Clock.schedule_once(lambda dt: self._setup_bg(self.sp, [1.0, 0.95, 0.94, 1.0]), 0.3)

        return root

    def _setup_bg(self, page, color):
        """给页面画一个铺满的纯色背景（用 Rectangle，避免 RoundedRectangle 问题）"""
        # 先清掉旧的 canvas.before
        page.canvas.before.clear()
        with page.canvas.before:
            Color(*color)
            rect = Rectangle(pos=page.pos, size=page.size)

        def update(w, *a):
            rect.pos = w.pos
            rect.size = w.size

        # 先手动设一次正确的 pos/size
        rect.pos = page.pos
        rect.size = page.size
        page.bind(pos=update, size=update)
        self._bg_cache[page] = (rect, color)

    def _switch_to(self, idx):
        """切换到指定页面"""
        root = self._root
        if self._current_idx == idx:
            return
        if self._current_idx is not None:
            old_page = self._pages[self._current_idx]
            if old_page.parent is root:
                root.remove_widget(old_page)
        root.add_widget(self._pages[idx], index=0)
        self._current_idx = idx
        # 确保新页面背景正确铺满
        Clock.schedule_once(lambda dt, p=self._pages[idx]: self._ensure_bg_fit(p), 0.05)

    def _ensure_bg_fit(self, page):
        """切换页面后确保背景 Rectangle 铺满正确"""
        if page in self._bg_cache:
            rect, _ = self._bg_cache[page]
            rect.pos = page.pos
            rect.size = page.size

    def _highlight(self, active_btn, active_color):
        for btn, color in self._nav_btns:
            if btn is active_btn:
                btn.background_color = color
            else:
                btn.background_color = [color[0] * 0.45, color[1] * 0.45, color[2] * 0.45, 1]


if __name__ == '__main__':
    MainApp().run()
