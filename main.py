"""
المخطط اليومي الذكي - نسخة الأندرويد
"""
import os
from pathlib import Path
from datetime import date, datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle

# ── DB PATH ───────────────────────────────────────────────
if platform == 'android':
    try:
        from android.storage import app_storage_path
        DB_DIR = Path(app_storage_path()) / "SmartPlanner"
    except Exception:
        DB_DIR = Path('/sdcard') / "SmartPlanner"
else:
    DB_DIR = Path.home() / "SmartPlanner"

DB_DIR.mkdir(parents=True, exist_ok=True)

import db as D
D.DB_PATH = DB_DIR / "planner.db"
D.init_db()

# ── THEME ─────────────────────────────────────────────────
BG       = (0.059, 0.090, 0.165, 1)
CARD     = (0.118, 0.161, 0.224, 1)
CARD2    = (0.157, 0.204, 0.282, 1)
BLUE     = (0.149, 0.388, 0.922, 1)
GREEN    = (0.086, 0.643, 0.290, 1)
RED      = (0.863, 0.149, 0.149, 1)
YELLOW   = (0.851, 0.467, 0.027, 1)
PURPLE   = (0.486, 0.227, 0.929, 1)
TEXT     = (0.945, 0.957, 0.976, 1)
TEXT2    = (0.580, 0.640, 0.720, 1)

PERIODS  = ['الفجر','الصباح','الظهر','العصر','المساء','الليل']
PICONS   = {'الفجر':'🌅','الصباح':'🌞','الظهر':'🌝',
            'العصر':'🌇','المساء':'🌆','الليل':'🌙'}

Window.clearcolor = BG


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════
def today():
    return date.today().isoformat()

def col(*rgb):
    return rgb if len(rgb) == 4 else (*rgb, 1)

def mk_label(text, size=14, bold=False, color=TEXT, halign='right',
             height=None, wrap=True):
    lbl = Label(
        text=text, font_size=dp(size), bold=bold,
        color=color, halign=halign,
        text_size=(None, None),
        size_hint_y=None,
    )
    if height:
        lbl.height = dp(height)
    elif wrap:
        lbl.bind(
            width=lambda i, w: setattr(i, 'text_size', (w, None)),
            texture_size=lambda i, ts: setattr(i, 'height', ts[1] + dp(6))
        )
    else:
        lbl.height = dp(size * 2.2)
    return lbl

def mk_btn(text, callback=None, color=BLUE, size=14, height=42):
    btn = Button(
        text=text, font_size=dp(size),
        size_hint_y=None, height=dp(height),
        background_normal='', background_color=color,
        color=TEXT, border=(0,0,0,0),
    )
    if callback:
        btn.bind(on_release=callback)
    return btn

def bg_widget(color, radius=dp(10)):
    w = Widget(size_hint_y=None)
    def _draw(inst, val):
        inst.canvas.before.clear()
        with inst.canvas.before:
            Color(*color)
            RoundedRectangle(pos=inst.pos, size=inst.size, radius=[radius])
    w.bind(pos=_draw, size=_draw)
    return w

class Card(BoxLayout):
    def __init__(self, color=None, radius=dp(10), **kw):
        kw.setdefault('size_hint_y', None)
        kw.setdefault('orientation', 'vertical')
        kw.setdefault('padding', dp(12))
        kw.setdefault('spacing', dp(6))
        super().__init__(**kw)
        _color = color or CARD
        with self.canvas.before:
            Color(*_color)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=lambda i,v: setattr(i._bg,'pos',v),
                  size=lambda i,v: setattr(i._bg,'size',v))
        self.bind(minimum_height=self.setter('height'))

class Scroll(ScrollView):
    def __init__(self, **kw):
        kw.setdefault('size_hint', (1,1))
        kw.setdefault('bar_width', dp(3))
        super().__init__(**kw)
        self.content = BoxLayout(
            orientation='vertical', size_hint_y=None,
            padding=dp(10), spacing=dp(8))
        self.content.bind(minimum_height=self.content.setter('height'))
        self.add_widget(self.content)

    def add(self, w):
        self.content.add_widget(w)

    def clear(self):
        self.content.clear_widgets()


# ══════════════════════════════════════════════════════════
#  NAV BAR
# ══════════════════════════════════════════════════════════
class NavBar(BoxLayout):
    def __init__(self, sm, **kw):
        super().__init__(orientation='horizontal',
                        size_hint_y=None, height=dp(58), **kw)
        self.sm = sm
        with self.canvas.before:
            Color(*CARD)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i,v: setattr(i._bg,'pos',v),
                  size=lambda i,v: setattr(i._bg,'size',v))
        self._btns = {}
        for name, icon, screen in [
            ('today',   '📅', 'today'),
            ('tasks',   '📋', 'tasks'),
            ('goals',   '🎯', 'goals'),
            ('reports', '📊', 'reports'),
        ]:
            btn = Button(
                text=icon, font_size=dp(24),
                background_normal='', background_color=(0,0,0,0),
                color=TEXT2, size_hint_x=1,
            )
            btn.bind(on_release=lambda x, s=screen: self._go(s))
            self._btns[name] = btn
            self.add_widget(btn)
        self._set_active('today')

    def _go(self, screen):
        self.sm.current = screen
        self._set_active(screen)
        # Refresh screen
        scr = self.sm.get_screen(screen)
        if hasattr(scr, 'refresh'):
            scr.refresh()

    def _set_active(self, name):
        for k, b in self._btns.items():
            b.color = BLUE if k == name else TEXT2


# ══════════════════════════════════════════════════════════
#  TODAY SCREEN
# ══════════════════════════════════════════════════════════
class TodayScreen(Screen):
    plan_date = today()

    def on_enter(self):
        if not hasattr(self, '_ready'):
            self._ready = True
            self._build()
        self.refresh()

    def _build(self):
        root = BoxLayout(orientation='vertical')

        # Top bar
        tb = BoxLayout(size_hint_y=None, height=dp(52), padding=(dp(10),0))
        with tb.canvas.before:
            Color(*CARD)
            self._tb_bg = Rectangle(pos=tb.pos, size=tb.size)
        tb.bind(pos=lambda i,v: setattr(i,'_tb_bg',i._tb_bg) or
                setattr(i._tb_bg,'pos',v),
                size=lambda i,v: setattr(i._tb_bg,'size',v))

        prev_btn = Button(text='◀', font_size=dp(18), size_hint_x=None, width=dp(44),
                         background_normal='', background_color=CARD2, color=TEXT)
        prev_btn.bind(on_release=lambda x: self._nav_day(-1))
        self._date_lbl = Label(text=self.plan_date, font_size=dp(15),
                               bold=True, color=TEXT)
        next_btn = Button(text='▶', font_size=dp(18), size_hint_x=None, width=dp(44),
                         background_normal='', background_color=CARD2, color=TEXT)
        next_btn.bind(on_release=lambda x: self._nav_day(1))
        new_btn = Button(text='✨', font_size=dp(20), size_hint_x=None, width=dp(44),
                        background_normal='', background_color=BLUE, color=TEXT)
        new_btn.bind(on_release=lambda x: self._create_plan())

        tb.add_widget(prev_btn)
        tb.add_widget(self._date_lbl)
        tb.add_widget(next_btn)
        tb.add_widget(new_btn)
        root.add_widget(tb)

        # Content scroll
        self._scroll = Scroll()
        root.add_widget(self._scroll)
        self.add_widget(root)

    def refresh(self):
        if not hasattr(self, '_scroll'):
            return
        self._date_lbl.text = self.plan_date
        self._scroll.clear()
        plan  = D.get_or_create_plan(self.plan_date)
        items = D.get_plan_items(plan['id'])

        if not items:
            elig = [t for t in D.get_today_eligible(self.plan_date,[],False,[],True,'متوسطة')
                    if not t.get('_excluded')]
            empty_card = Card(color=CARD2)
            empty_card.add_widget(mk_label("📭", size=32, halign='center', height=44))
            empty_card.add_widget(mk_label("لم تُنشأ خطة اليوم بعد", size=14,
                                           halign='center', color=TEXT2))
            empty_card.add_widget(mk_label(f"{len(elig)} مهمة مؤهلة", size=12,
                                           halign='center', color=TEXT2))
            create_btn = mk_btn("✨ إنشاء الخطة الآن", lambda x: self._create_plan())
            empty_card.add_widget(create_btn)
            self._scroll.add(empty_card)
            return

        # Stats
        done_c = sum(1 for i in items if i.get('status') == 'تمت')
        total_c = len(items)
        pct = int(done_c / total_c * 100) if total_c else 0
        stat_card = Card(color=CARD2)
        stat_card.add_widget(mk_label(
            f"الخطة — {total_c} عنصر  |  {done_c} مكتمل ({pct}%)",
            size=13, bold=True, height=28))
        # Progress bar
        pb_row = BoxLayout(size_hint_y=None, height=dp(10))
        with pb_row.canvas:
            Color(*CARD)
            Rectangle(pos=pb_row.pos, size=pb_row.size)
            Color(*GREEN)
            self._pb_rect = Rectangle(pos=pb_row.pos,
                                      size=(pb_row.width * pct/100, dp(10)))
        pb_row.bind(pos=lambda i,v: (setattr(i._pb_rect if hasattr(i,'_pb_rect') else Widget(),'pos',v)),
                    size=lambda i,v: None)
        stat_card.add_widget(pb_row)
        self._scroll.add(stat_card)

        # Items
        for item in items:
            self._scroll.add(self._item_card(item))

    def _item_card(self, item):
        is_done = item.get('status') == 'تمت'
        is_goal = item.get('is_goal')
        iid     = item['id']
        tid     = item.get('task_id', 0)

        card_color = CARD
        if is_done: card_color = (0.086, 0.2, 0.138, 1)
        if is_goal: card_color = (0.2, 0.1, 0.35, 1)

        card = Card(color=card_color)

        # Time
        time_txt = f"{item.get('scheduled_start','')} — {item.get('scheduled_end','')}"
        period = item.get('preferred_time','')
        if period:
            time_txt += f"  {PICONS.get(period,'')} {period}"
        card.add_widget(mk_label(time_txt, size=11, color=TEXT2, height=18))

        # Title
        title = item.get('title') or item.get('goal_label') or '—'
        if is_done:
            title = f"[s]{title}[/s]"
        tl = Label(text=title, markup=True, font_size=dp(13),
                   bold=True, color=TEXT2 if is_done else TEXT,
                   halign='right', size_hint_y=None)
        tl.bind(width=lambda i,w: setattr(i,'text_size',(w,None)),
                texture_size=lambda i,ts: setattr(i,'height',ts[1]+dp(4)))
        card.add_widget(tl)

        # Buttons
        if not is_done:
            btn_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
            done_b = mk_btn("✓ تم", color=GREEN, size=12, height=34)
            done_b.bind(on_release=lambda x, i=iid, t=tid: self._mark_done(i, t))
            per_b  = mk_btn(PICONS.get(period,'⏰'), color=CARD2, size=18, height=34)
            per_b.size_hint_x = None; per_b.width = dp(44)
            per_b.bind(on_release=lambda x, i=iid: self._show_period(i))
            del_b  = mk_btn("✕", color=RED, size=14, height=34)
            del_b.size_hint_x = None; del_b.width = dp(44)
            del_b.bind(on_release=lambda x, i=iid: self._del_item(i))
            btn_row.add_widget(done_b)
            btn_row.add_widget(per_b)
            btn_row.add_widget(del_b)
            card.add_widget(btn_row)

        return card

    def _mark_done(self, iid, tid):
        D.update_plan_item(iid, {'status':'تمت','progress':100,
            'actual_end': datetime.now().strftime('%H:%M')})
        if tid and tid > 0:
            task = D.get_task(tid)
            is_rep = task and (task.get('is_recurring') or task.get('week_days')
                               or (task.get('end_date','') or '') >= '2099-01-01')
            if is_rep:
                D.update_task(tid, {'completed_at': datetime.now().isoformat()})
            else:
                D.update_task(tid, {'status':'تمت','progress':100,
                    'completed_at': datetime.now().isoformat()})
        Clock.schedule_once(lambda dt: self.refresh(), 0.2)

    def _del_item(self, iid):
        D.exe("DELETE FROM daily_plan_items WHERE id=?", (iid,))
        Clock.schedule_once(lambda dt: self.refresh(), 0.1)

    def _show_period(self, iid):
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        popup = Popup(title='⏰ اختر فترة التنفيذ',
                     content=content, size_hint=(0.85, 0.7))
        for p in PERIODS:
            btn = mk_btn(f"{PICONS[p]}  {p}", color=CARD2, size=14, height=46)
            btn.bind(on_release=lambda x, pr=p: (
                D.update_plan_item(iid, {'preferred_time': pr}),
                popup.dismiss(),
                Clock.schedule_once(lambda dt: self.refresh(), 0.2)
            ))
            content.add_widget(btn)
        none_btn = mk_btn("⏰ بدون تحديد", color=CARD, size=13, height=40)
        none_btn.bind(on_release=lambda x: (
            D.update_plan_item(iid, {'preferred_time': ''}),
            popup.dismiss(),
            Clock.schedule_once(lambda dt: self.refresh(), 0.2)
        ))
        content.add_widget(none_btn)
        popup.open()

    def _create_plan(self):
        elig = [t for t in D.get_today_eligible(self.plan_date,[],False,[],True,'متوسطة')
                if not t.get('_excluded')]
        if not elig:
            return
        pri = {'عالية جدًا':0,'عالية':1,'متوسطة':2,'منخفضة':3,'لاحقًا':4}
        elig.sort(key=lambda t: (pri.get(t.get('priority','متوسطة'),5),
                                  0 if t.get('urgency')=='عاجل' else 1))
        plan = D.get_or_create_plan(self.plan_date)
        D.delete_plan_items(plan['id'])
        cur = 8*60
        for t in elig:
            if t.get('is_occasion'): continue
            dur = t.get('estimated_duration',30) or 30
            ss  = "%02d:%02d"%(cur//60,cur%60); cur+=dur
            es  = "%02d:%02d"%(cur//60,cur%60)
            D.add_plan_item(plan['id'], t['id'], ss, es, 0)
        Clock.schedule_once(lambda dt: self.refresh(), 0.3)

    def _nav_day(self, delta):
        d = date.fromisoformat(self.plan_date) + timedelta(delta)
        self.plan_date = d.isoformat()
        self.refresh()


# ══════════════════════════════════════════════════════════
#  TASKS SCREEN
# ══════════════════════════════════════════════════════════
class TasksScreen(Screen):
    def on_enter(self):
        if not hasattr(self, '_ready'):
            self._ready = True
            self._build()
        self.refresh()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        # Toolbar
        tb = BoxLayout(size_hint_y=None, height=dp(52), padding=(dp(10),0))
        with tb.canvas.before:
            Color(*CARD)
            self._tb_bg = Rectangle(pos=tb.pos, size=tb.size)
        tb.bind(pos=lambda i,v: setattr(i._tb_bg,'pos',v),
                size=lambda i,v: setattr(i._tb_bg,'size',v))
        tb.add_widget(Label(text='📋 بنك المهام', font_size=dp(15),
                            bold=True, color=TEXT))
        add_btn = mk_btn("+ جديدة", lambda x: self._add_task(),
                        color=BLUE, size=13, height=36)
        add_btn.size_hint_x = None; add_btn.width = dp(90)
        tb.add_widget(add_btn)
        root.add_widget(tb)
        self._scroll = Scroll()
        root.add_widget(self._scroll)
        self.add_widget(root)

    def refresh(self):
        if not hasattr(self, '_scroll'): return
        self._scroll.clear()
        all_tasks = D.get_tasks()
        today_s   = today()
        overdue   = [t for t in all_tasks
                     if t.get('status') not in ('تمت','ملغاة','محذوفة')
                     and t.get('end_date') and t['end_date'] < today_s
                     and t['end_date'] < '2099-01-01']
        pending   = [t for t in all_tasks
                     if t.get('status') not in ('تمت','ملغاة','محذوفة')
                     and t not in overdue]
        done      = [t for t in all_tasks if t.get('status') == 'تمت']

        if overdue:
            self._scroll.add(mk_label(f"⚠️ متأخرة ({len(overdue)})",
                size=12, bold=True, color=RED, height=26))
            for t in overdue:
                self._scroll.add(self._task_card(t))

        if pending:
            self._scroll.add(mk_label(f"📋 معلقة ({len(pending)})",
                size=12, bold=True, color=TEXT2, height=26))
            for t in pending:
                self._scroll.add(self._task_card(t))

        if done:
            self._scroll.add(mk_label(f"✅ مكتملة ({len(done)})",
                size=12, bold=True, color=GREEN, height=26))
            for t in done[:8]:
                self._scroll.add(self._task_card(t, done=True))

        if not all_tasks:
            c = Card(color=CARD2)
            c.add_widget(mk_label("لا توجد مهام بعد", size=14, halign='center'))
            self._scroll.add(c)

    def _task_card(self, t, done=False):
        card = Card(color=(0.086,0.2,0.138,1) if done else CARD)
        title = t.get('title','')
        card.add_widget(mk_label(title, size=13, bold=True,
                                 color=TEXT2 if done else TEXT))
        meta = []
        if t.get('cat_name'): meta.append(t['cat_name'])
        if t.get('estimated_duration'): meta.append(f"⏱ {t['estimated_duration']} د")
        if t.get('end_date') and t['end_date']<'2099': meta.append(f"📅 {t['end_date']}")
        if meta:
            card.add_widget(mk_label("  •  ".join(meta), size=11,
                                     color=TEXT2, height=18))
        if not done:
            tid = t['id']
            btn_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
            plan_btn = mk_btn("📅 للخطة", color=BLUE, size=12, height=32)
            plan_btn.bind(on_release=lambda x, t=tid: self._add_to_plan(t))
            edit_btn = mk_btn("✏️", color=CARD2, size=14, height=32)
            edit_btn.size_hint_x = None; edit_btn.width = dp(44)
            edit_btn.bind(on_release=lambda x, t=tid: self._edit(t))
            del_btn = mk_btn("🗑", color=RED, size=14, height=32)
            del_btn.size_hint_x = None; del_btn.width = dp(44)
            del_btn.bind(on_release=lambda x, t=tid: self._delete(t))
            btn_row.add_widget(plan_btn)
            btn_row.add_widget(edit_btn)
            btn_row.add_widget(del_btn)
            card.add_widget(btn_row)
        return card

    def _add_to_plan(self, tid):
        task = D.get_task(tid)
        if not task: return
        d     = today()
        plan  = D.get_or_create_plan(d)
        items = D.get_plan_items(plan['id'])
        real  = [i for i in items if i.get('scheduled_end')]
        last  = max((i['scheduled_end'] for i in real), default='08:00') if real else '08:00'
        h,m   = map(int, last.split(':'))
        dur   = task.get('estimated_duration',30) or 30
        cur   = h*60+m
        ss    = "%02d:%02d"%(cur//60,cur%60); cur+=dur
        es    = "%02d:%02d"%(cur//60,cur%60)
        D.add_plan_item(plan['id'], tid, ss, es, len(items))

    def _edit(self, tid):
        self._show_form(tid)

    def _add_task(self):
        self._show_form()

    def _show_form(self, tid=None):
        task = D.get_task(tid) if tid else {}
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        title_i = TextInput(text=task.get('title','') if task else '',
                           hint_text='عنوان المهمة',
                           background_color=CARD2, foreground_color=TEXT,
                           size_hint_y=None, height=dp(46), font_size=dp(14),
                           multiline=False)
        dur_i   = TextInput(text=str(task.get('estimated_duration',30) if task else 30),
                           hint_text='المدة (دقيقة)',
                           background_color=CARD2, foreground_color=TEXT,
                           size_hint_y=None, height=dp(46), font_size=dp(14),
                           multiline=False, input_filter='int')
        content.add_widget(title_i)
        content.add_widget(dur_i)
        popup = Popup(title="تعديل المهمة" if tid else "مهمة جديدة",
                     content=content, size_hint=(0.9, 0.5))

        def _save(x):
            title = title_i.text.strip()
            if not title: popup.dismiss(); return
            data = {'title': title,
                    'estimated_duration': int(dur_i.text or 30),
                    'status': 'لم تبدأ', 'priority': 'متوسطة'}
            if tid: D.update_task(tid, data)
            else:   D.add_task(data)
            popup.dismiss()
            Clock.schedule_once(lambda dt: self.refresh(), 0.2)

        save_btn = mk_btn("💾 حفظ", _save, color=BLUE)
        content.add_widget(save_btn)
        popup.open()

    def _delete(self, tid):
        D.exe("UPDATE tasks SET is_deleted=1 WHERE id=?", (tid,))
        Clock.schedule_once(lambda dt: self.refresh(), 0.2)


# ══════════════════════════════════════════════════════════
#  GOALS SCREEN
# ══════════════════════════════════════════════════════════
class GoalsScreen(Screen):
    def on_enter(self):
        if not hasattr(self, '_ready'):
            self._ready = True
            self._build()
        self.refresh()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        tb = BoxLayout(size_hint_y=None, height=dp(52))
        with tb.canvas.before:
            Color(*CARD)
            self._tb = Rectangle(pos=tb.pos, size=tb.size)
        tb.bind(pos=lambda i,v: setattr(i._tb,'pos',v),
                size=lambda i,v: setattr(i._tb,'size',v))
        tb.add_widget(Label(text='🎯 الأهداف', font_size=dp(15), bold=True, color=TEXT))
        root.add_widget(tb)
        self._scroll = Scroll()
        root.add_widget(self._scroll)
        self.add_widget(root)

    def refresh(self):
        if not hasattr(self, '_scroll'): return
        self._scroll.clear()
        goals = D.get_goals()
        if not goals:
            c = Card(color=CARD2)
            c.add_widget(mk_label("🎯", size=32, halign='center', height=42))
            c.add_widget(mk_label("لا توجد أهداف", size=14, halign='center'))
            c.add_widget(mk_label("أضف أهدافاً من تطبيق الكمبيوتر", size=12,
                                  halign='center', color=TEXT2))
            self._scroll.add(c)
            return
        for g in goals:
            pct  = D.calc_goal_progress(g['id'])
            acts = D.get_goal_activities(g['id'])
            self._scroll.add(self._goal_card(g, pct, acts))

    def _goal_card(self, g, pct, acts):
        card = Card(color=CARD)
        hdr = BoxLayout(size_hint_y=None, height=dp(30))
        hdr.add_widget(Label(text=f"🎯 {g.get('title','')}",
                            font_size=dp(14), bold=True, color=TEXT))
        hdr.add_widget(Label(text=f"{pct}%",
                            font_size=dp(20), bold=True, color=PURPLE,
                            size_hint_x=None, width=dp(60), halign='left'))
        card.add_widget(hdr)

        from kivy.uix.progressbar import ProgressBar
        pb = ProgressBar(value=pct, max=100, size_hint_y=None, height=dp(8))
        card.add_widget(pb)

        if acts:
            for act in acts:
                arow = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
                from kivy.uix.switch import Switch
                sw = Switch(active=bool(act['is_done']),
                           size_hint_x=None, width=dp(60))
                aid = act['id']
                gid = g['id']
                sw.bind(active=lambda inst, val, a=aid, gi=gid:
                       self._toggle(a, val, gi))
                arow.add_widget(sw)
                arow.add_widget(Label(
                    text=act.get('title',''),
                    font_size=dp(13),
                    color=TEXT2 if act['is_done'] else TEXT,
                    halign='right',
                ))
                arow.add_widget(Label(
                    text=f"{int(act.get('weight_pct',0))}%",
                    font_size=dp(11), bold=True, color=PURPLE,
                    size_hint_x=None, width=dp(40), halign='left',
                ))
                card.add_widget(arow)
        return card

    def _toggle(self, aid, done, gid):
        D.update_goal_activity(aid, {'is_done': int(done)})
        pct = D.calc_goal_progress(gid)
        D.update_goal(gid, {'progress': pct})
        Clock.schedule_once(lambda dt: self.refresh(), 0.5)


# ══════════════════════════════════════════════════════════
#  REPORTS SCREEN
# ══════════════════════════════════════════════════════════
class ReportsScreen(Screen):
    def on_enter(self):
        if not hasattr(self, '_ready'):
            self._ready = True
            self._build()
        self.refresh()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        tb = BoxLayout(size_hint_y=None, height=dp(52))
        with tb.canvas.before:
            Color(*CARD)
            self._tb = Rectangle(pos=tb.pos, size=tb.size)
        tb.bind(pos=lambda i,v: setattr(i._tb,'pos',v),
                size=lambda i,v: setattr(i._tb,'size',v))
        tb.add_widget(Label(text='📊 التقارير', font_size=dp(15), bold=True, color=TEXT))
        root.add_widget(tb)
        self._scroll = Scroll()
        root.add_widget(self._scroll)
        self.add_widget(root)

    def refresh(self):
        if not hasattr(self, '_scroll'): return
        self._scroll.clear()
        s = D.get_stats()

        # Grid of stats
        grid = GridLayout(cols=2, spacing=dp(8),
                         size_hint_y=None, height=dp(150))
        for val, lbl, color in [
            (s['total'],     '📋 إجمالي',  BLUE),
            (s['completed'], '✅ مكتملة',  GREEN),
            (s['pending'],   '⏳ معلقة',   YELLOW),
            (s['overdue'],   '⚠️ متأخرة',  RED),
        ]:
            c = Card(color=CARD2)
            c.add_widget(Label(text=str(val), font_size=dp(28),
                               bold=True, color=color, size_hint_y=None, height=dp(50)))
            c.add_widget(Label(text=lbl, font_size=dp(11),
                               color=TEXT2, size_hint_y=None, height=dp(22)))
            grid.add_widget(c)
        self._scroll.add(grid)

        # Overall progress
        if s['total']:
            pct = int(s['completed']/s['total']*100)
            pc = Card(color=CARD)
            ph = BoxLayout(size_hint_y=None, height=dp(28))
            ph.add_widget(Label(text='📈 نسبة الإنجاز الكلية',
                               font_size=dp(13), bold=True, color=TEXT))
            ph.add_widget(Label(text=f"{pct}%", font_size=dp(16),
                               bold=True, color=BLUE, size_hint_x=None, width=dp(50)))
            pc.add_widget(ph)
            from kivy.uix.progressbar import ProgressBar
            pc.add_widget(ProgressBar(value=pct, max=100,
                                     size_hint_y=None, height=dp(10)))
            self._scroll.add(pc)

        # Goals
        goals = D.get_goals()
        if goals:
            self._scroll.add(mk_label("🎯 تقدم الأهداف", size=13,
                                      bold=True, color=TEXT2, height=28))
            from kivy.uix.progressbar import ProgressBar
            for g in goals:
                pct_g = D.calc_goal_progress(g['id'])
                gc = Card(color=CARD)
                gh = BoxLayout(size_hint_y=None, height=dp(26))
                gh.add_widget(Label(text=g.get('title',''), font_size=dp(13),
                                   bold=True, color=TEXT))
                gh.add_widget(Label(text=f"{pct_g}%", font_size=dp(14),
                                   bold=True, color=PURPLE,
                                   size_hint_x=None, width=dp(50)))
                gc.add_widget(gh)
                gc.add_widget(ProgressBar(value=pct_g, max=100,
                                         size_hint_y=None, height=dp(8)))
                self._scroll.add(gc)


# ══════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════
class SmartPlannerApp(App):
    def build(self):
        self.title = "المخطط اليومي الذكي"
        Window.clearcolor = BG

        # Screen manager
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(TodayScreen(name='today'))
        sm.add_widget(TasksScreen(name='tasks'))
        sm.add_widget(GoalsScreen(name='goals'))
        sm.add_widget(ReportsScreen(name='reports'))

        # Root layout
        root = BoxLayout(orientation='vertical')
        root.add_widget(sm)

        # Navigation bar
        nav = NavBar(sm)
        root.add_widget(nav)

        return root


if __name__ == '__main__':
    SmartPlannerApp().run()
