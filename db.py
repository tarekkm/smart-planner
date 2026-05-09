"""
المخطط اليومي الذكي - Smart Daily Planner v4
ملف واحد مستقل - يعمل على Windows/Mac/Linux
"""
import sys, os, sqlite3, traceback
from pathlib import Path
from datetime import date, datetime, timedelta

# ── تسجيل الأخطاء في ملف ──────────────────────────────────
LOG_FILE = Path.home() / "SmartPlanner" / "error.log"

def log_error(msg):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] {msg}\n")
    except:
        pass

# ══════════════════════════════════════════════════════════
#  DATABASE LAYER
# ══════════════════════════════════════════════════════════
DB_DIR  = Path.home() / "SmartPlanner"
DB_PATH = DB_DIR / "planner.db"

def get_conn():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, color TEXT DEFAULT '#2563EB', icon TEXT DEFAULT '📋');
    CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, phone TEXT);
    CREATE TABLE IF NOT EXISTS places (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, description TEXT,
        category_id INTEGER, task_type TEXT DEFAULT 'مهمة',
        priority TEXT DEFAULT 'متوسطة',
        importance TEXT DEFAULT 'مهم',
        urgency TEXT DEFAULT 'غير عاجل',
        estimated_duration INTEGER DEFAULT 30,
        start_date TEXT, end_date TEXT,
        preferred_time TEXT DEFAULT 'أي وقت',
        is_recurring INTEGER DEFAULT 0, recurrence_type TEXT,
        has_condition INTEGER DEFAULT 0,
        condition_type TEXT, condition_details TEXT,
        person_id INTEGER, place_id INTEGER,
        required_amount REAL DEFAULT 0,
        status TEXT DEFAULT 'لم تبدأ',
        progress INTEGER DEFAULT 0, notes TEXT, goal_id INTEGER,
        created_at TEXT DEFAULT(datetime('now')),
        updated_at TEXT DEFAULT(datetime('now')),
        completed_at TEXT, is_deleted INTEGER DEFAULT 0,
        week_days TEXT, fixed_start_time TEXT);
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, description TEXT,
        category_id INTEGER, end_date TEXT,
        target_result TEXT, status TEXT DEFAULT 'قيد التنفيذ',
        progress INTEGER DEFAULT 0,
        created_at TEXT DEFAULT(datetime('now')));
    CREATE TABLE IF NOT EXISTS goal_activities(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        weight_pct REAL DEFAULT 0,
        is_done INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT(datetime('now')));
    CREATE TABLE IF NOT EXISTS occasions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, occasion_type TEXT,
        country TEXT, day INTEGER, month INTEGER,
        is_recurring INTEGER DEFAULT 1,
        reminder_days INTEGER DEFAULT 14,
        is_active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS daily_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_date TEXT UNIQUE,
        start_time TEXT DEFAULT '08:00',
        end_time TEXT DEFAULT '22:00',
        energy_level TEXT DEFAULT 'متوسطة',
        plan_type TEXT DEFAULT 'متوسطة',
        focus_area TEXT, going_out INTEGER DEFAULT 0,
        out_places TEXT, available_persons TEXT,
        money_available INTEGER DEFAULT 1, blocked_times TEXT);
    CREATE TABLE IF NOT EXISTS daily_plan_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER, task_id INTEGER,
        scheduled_start TEXT, scheduled_end TEXT,
        actual_start TEXT, actual_end TEXT,
        status TEXT DEFAULT 'لم تبدأ',
        progress INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
        is_free INTEGER DEFAULT 0, free_label TEXT,
        is_goal INTEGER DEFAULT 0, goal_label TEXT, act_id INTEGER);
    """)
    # categories
    if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        cats = [
            ('عبادة','#16A34A','🕌'), ('عمل','#2563EB','💼'),
            ('صحة','#DC2626','❤️'), ('أسرة','#D97706','👨‍👩‍👧'),
            ('مال','#059669','💰'), ('منزل','#7C3AED','🏠'),
            ('دراسة','#0891B2','📚'), ('علاقات','#EA580C','🤝'),
            ('سفر','#0D9488','✈️'), ('تطوير الذات','#8B5CF6','🌟'),
        ]
        conn.executemany(
            "INSERT INTO categories(name,color,icon) VALUES(?,?,?)", cats)
    # settings
    defaults = [('reminder_days','14'), ('work_days','0,1,2,3,4'),
                ('work_from','08:00'), ('work_to','17:00'),
                ('country','السعودية'), ('country2','مصر'), ('city','الرياض')]
    for k, v in defaults:
        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
    # occasions
    if conn.execute("SELECT COUNT(*) FROM occasions").fetchone()[0] == 0:
        occ = [
            ('اليوم الوطني السعودي','وطني','السعودية',23,9,1,14),
            ('يوم التأسيس','وطني','السعودية',22,2,1,14),
            ('عيد الفطر','ديني','إسلامي',None,None,1,14),
            ('عيد الأضحى','ديني','إسلامي',None,None,1,14),
            ('شم النسيم','اجتماعي','مصر',None,4,1,7),
            ('ثورة 23 يوليو','وطني','مصر',23,7,1,7),
            ('يوم 6 أكتوبر','وطني','مصر',6,10,1,7),
        ]
        conn.executemany(
            "INSERT INTO occasions(name,occasion_type,country,"
            "day,month,is_recurring,reminder_days) VALUES(?,?,?,?,?,?,?)", occ)
    conn.commit()
    # ── Migrations for existing databases ──────────────────
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN week_days TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN fixed_start_time TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        # preferred_time: time period for tasks in plan (الفجر/الصباح/الظهر/...)
        conn.execute("ALTER TABLE daily_plan_items ADD COLUMN preferred_time TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        # month_day: day of month (1-31) for monthly recurrence
        conn.execute("ALTER TABLE tasks ADD COLUMN month_day INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    try:
        # year_day: "MM-DD" for annual recurrence (e.g. "12-25")
        conn.execute("ALTER TABLE tasks ADD COLUMN year_day TEXT")
        conn.commit()
    except Exception:
        pass
    for col in ["is_free INTEGER DEFAULT 0", "free_label TEXT",
                "is_goal INTEGER DEFAULT 0", "goal_label TEXT",
                "act_id INTEGER"]:
        try:
            conn.execute(f"ALTER TABLE daily_plan_items ADD COLUMN {col}")
            conn.commit()
        except Exception:
            pass
    # ── Auto-fix: extend expired tasks that should be ongoing ─────
    try:
        from datetime import date as _date
        today_str = _date.today().isoformat()
        conn.execute("""
            UPDATE tasks SET end_date='2099-12-31'
            WHERE is_deleted=0
              AND (is_recurring=1 OR week_days IS NOT NULL)
              AND end_date IS NOT NULL
              AND end_date < ?
              AND end_date < '2099-01-01'
        """, (today_str,))
        conn.commit()
    except Exception:
        pass
    conn.close()

def qry(sql, params=(), one=False):
    conn = get_conn()
    cur  = conn.execute(sql, params)
    data = cur.fetchone() if one else cur.fetchall()
    conn.close()
    if one:
        return dict(data) if data else None
    return [dict(r) for r in data]

def exe(sql, params=()):
    conn = get_conn()
    cur  = conn.execute(sql, params)
    lid  = cur.lastrowid
    conn.commit()
    conn.close()
    return lid

def get_setting(key, default=None):
    r = qry("SELECT value FROM settings WHERE key=?", (key,), one=True)
    return r['value'] if r else default

def set_setting(key, val):
    exe("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(val)))

def get_categories():
    return qry("SELECT * FROM categories ORDER BY name")

def get_persons():
    return qry("SELECT * FROM persons ORDER BY name")

def get_places():
    return qry("SELECT * FROM places ORDER BY name")

def get_tasks(filters=None):
    sql = """SELECT t.*, c.name cat_name, c.color cat_color, c.icon cat_icon,
             p.name person_name, pl.name place_name
             FROM tasks t
             LEFT JOIN categories c ON t.category_id = c.id
             LEFT JOIN persons p ON t.person_id = p.id
             LEFT JOIN places pl ON t.place_id = pl.id
             WHERE t.is_deleted = 0"""
    params = []
    if filters:
        if filters.get('status'):
            sql += " AND t.status=?"
            params.append(filters['status'])
        if filters.get('category_id'):
            sql += " AND t.category_id=?"
            params.append(filters['category_id'])
        if filters.get('priority'):
            sql += " AND t.priority=?"
            params.append(filters['priority'])
        if filters.get('search'):
            sql += " AND (t.title LIKE ? OR t.description LIKE ? OR t.notes LIKE ?)"
            s = "%" + filters['search'] + "%"
            params += [s, s, s]
    sql += (" ORDER BY CASE t.priority "
            "WHEN 'عالية جدًا' THEN 1 WHEN 'عالية' THEN 2 "
            "WHEN 'متوسطة' THEN 3 ELSE 4 END, t.end_date")
    return qry(sql, params)

def get_task(tid):
    return qry("""SELECT t.*, c.name cat_name, c.color cat_color,
               p.name person_name, pl.name place_name
               FROM tasks t
               LEFT JOIN categories c ON t.category_id=c.id
               LEFT JOIN persons p ON t.person_id=p.id
               LEFT JOIN places pl ON t.place_id=pl.id
               WHERE t.id=?""", (tid,), one=True)

def add_task(data):
    cols = ', '.join(data.keys())
    ph   = ', '.join(['?'] * len(data))
    return exe(f"INSERT INTO tasks({cols}) VALUES({ph})", list(data.values()))

def update_task(tid, data):
    data['updated_at'] = datetime.now().isoformat()
    sets = ', '.join(k + "=?" for k in data)
    exe(f"UPDATE tasks SET {sets} WHERE id=?", list(data.values()) + [tid])

def delete_task(tid, permanent=False):
    if permanent:
        exe("DELETE FROM daily_plan_items WHERE task_id=?", (tid,))
        exe("DELETE FROM tasks WHERE id=?", (tid,))
    else:
        exe("DELETE FROM daily_plan_items WHERE task_id=?", (tid,))
        exe("DELETE FROM tasks WHERE id=?", (tid,))

def get_goals():
    return qry("""SELECT g.*, c.name cat_name,
               COUNT(t.id) task_count,
               SUM(CASE WHEN t.status='تمت' THEN 1 ELSE 0 END) done_count
               FROM goals g
               LEFT JOIN categories c ON g.category_id=c.id
               LEFT JOIN tasks t ON t.goal_id=g.id AND t.is_deleted=0
               GROUP BY g.id ORDER BY g.created_at DESC""")

def get_goal(gid):
    return qry("SELECT g.*,c.name cat_name FROM goals g LEFT JOIN categories c ON g.category_id=c.id WHERE g.id=?", (gid,), one=True)

def update_goal(gid, data):
    sets = ','.join(k+"=?" for k in data)
    exe(f"UPDATE goals SET {sets} WHERE id=?", list(data.values())+[gid])

def delete_goal(gid):
    exe("DELETE FROM goal_activities WHERE goal_id=?", (gid,))
    exe("DELETE FROM goals WHERE id=?", (gid,))

def get_goal_activities(goal_id):
    return qry("SELECT * FROM goal_activities WHERE goal_id=? ORDER BY id", (goal_id,))

def add_goal_activity(goal_id, title, weight_pct, notes=""):
    return exe(
        "INSERT INTO goal_activities(goal_id,title,weight_pct,notes) VALUES(?,?,?,?)",
        (goal_id, title, weight_pct, notes))

def update_goal_activity(aid, data):
    sets = ",".join(k+"=?" for k in data)
    exe(f"UPDATE goal_activities SET {sets} WHERE id=?", list(data.values())+[aid])

def delete_goal_activity(aid):
    exe("DELETE FROM goal_activities WHERE id=?", (aid,))

def calc_goal_progress(goal_id):
    acts = get_goal_activities(goal_id)
    if not acts:
        rows = qry("SELECT COUNT(*) tc, SUM(CASE WHEN status=? THEN 1 ELSE 0 END) dc FROM tasks WHERE goal_id=? AND is_deleted=0", ("تمت", goal_id), one=True)
        tc = rows["tc"] or 0; dc = rows["dc"] or 0
        return int(dc/tc*100) if tc > 0 else 0
    total_w = sum(a["weight_pct"] for a in acts)
    if total_w == 0: return 0
    done_w = sum(a["weight_pct"] for a in acts if a["is_done"])
    return int(done_w / total_w * 100)


def add_goal(data):
    cols = ', '.join(data.keys())
    ph   = ', '.join(['?'] * len(data))
    return exe(f"INSERT INTO goals({cols}) VALUES({ph})", list(data.values()))

def get_occasions():
    return qry("SELECT * FROM occasions WHERE is_active=1 ORDER BY month,day")

def add_occasion(data):
    cols = ', '.join(data.keys())
    ph   = ', '.join(['?'] * len(data))
    exe(f"INSERT INTO occasions({cols}) VALUES({ph})", list(data.values()))

def get_upcoming_occasions(plan_date, days=14):
    today  = date.fromisoformat(plan_date)
    result = []
    for occ in get_occasions():
        if occ['day'] and occ['month']:
            try:
                od = date(today.year, occ['month'], occ['day'])
                if od < today:
                    od = date(today.year + 1, occ['month'], occ['day'])
                delta = (od - today).days
                if 0 <= delta <= days:
                    occ['days_remaining'] = delta
                    result.append(occ)
            except Exception:
                pass
    return sorted(result, key=lambda x: x['days_remaining'])

def get_or_create_plan(plan_date):
    r = qry("SELECT * FROM daily_plans WHERE plan_date=?", (plan_date,), one=True)
    if not r:
        exe("INSERT INTO daily_plans(plan_date) VALUES(?)", (plan_date,))
        r = qry("SELECT * FROM daily_plans WHERE plan_date=?", (plan_date,), one=True)
    return r

def update_plan(plan_date, data):
    sets = ', '.join(k + "=?" for k in data)
    exe(f"UPDATE daily_plans SET {sets} WHERE plan_date=?",
        list(data.values()) + [plan_date])

def add_goal_item(plan_id, goal_title, start, end, order=0, act_id=None):
    exe("""INSERT INTO daily_plan_items
           (plan_id, task_id, scheduled_start, scheduled_end,
            sort_order, is_goal, goal_label, act_id)
           VALUES (?,NULL,?,?,?,1,?,?)""",
        (plan_id, start, end, order, goal_title, act_id))

def get_plan_items(plan_id):
    rows = qry("""SELECT dpi.*, t.title, t.estimated_duration, t.priority,
               c.name cat_name, c.color cat_color, c.icon cat_icon
               FROM daily_plan_items dpi
               LEFT JOIN tasks t ON dpi.task_id=t.id AND dpi.task_id>0
               LEFT JOIN categories c ON t.category_id=c.id
               WHERE dpi.plan_id=?
               ORDER BY dpi.sort_order, dpi.scheduled_start""", (plan_id,))
    result = []
    for row in rows:
        d = dict(row)
        # For goal items: use goal_label as title
        if d.get('is_goal'):
            d['title']   = d.get('goal_label') or '🎯 وقت للهدف'
            d['type']    = 'goal'
            d['is_free'] = 0
        result.append(d)
    return result

def add_plan_item(plan_id, task_id, start, end, order=0):
    exe("""INSERT INTO daily_plan_items
           (plan_id,task_id,scheduled_start,scheduled_end,sort_order)
           VALUES(?,?,?,?,?)""", (plan_id, task_id, start, end, order))

def update_plan_item(iid, data):
    sets = ', '.join(k + "=?" for k in data)
    exe(f"UPDATE daily_plan_items SET {sets} WHERE id=?",
        list(data.values()) + [iid])

def delete_plan_items(plan_id):
    exe("DELETE FROM daily_plan_items WHERE plan_id=?", (plan_id,))

def get_today_eligible(plan_date, avail_persons=None, going_out=False,
                       avail_places=None, money=True, energy='متوسطة',
                       money_amount=0):
    if avail_persons is None: avail_persons = []
    if avail_places  is None: avail_places  = []
    today = plan_date
    d = date.fromisoformat(plan_date)
    # today_idx: 0=الأحد,1=الاثنين,...,6=السبت
    today_idx = (d.weekday() + 1) % 7

    # Include recurring tasks even if marked done on a previous day
    tasks = qry("""SELECT t.*, c.name cat_name, c.color cat_color, c.icon cat_icon,
               p.name person_name, pl.name place_name
               FROM tasks t
               LEFT JOIN categories c ON t.category_id=c.id
               LEFT JOIN persons p ON t.person_id=p.id
               LEFT JOIN places pl ON t.place_id=pl.id
               WHERE t.is_deleted=0
               AND t.status NOT IN('ملغاة','محذوفة')
               AND (
                   t.status NOT IN('تمت')
                   OR (
                       (
                           t.is_recurring=1
                           OR t.week_days IS NOT NULL
                           OR t.end_date>='2099-01-01'
                       )
                       AND (t.completed_at IS NULL OR date(t.completed_at) < ?)
                   )
               )
               AND (t.start_date IS NULL OR t.start_date<=?)""",
               (today, today))

    result = []
    for row in tasks:
        t = dict(row)
        t['_excluded'] = None
        t['_auto_reason'] = None

        # ── Tasks with NO scheduling constraints → manual only ──────────
        # A task must have at least ONE of these to be auto-included:
        # week_days, is_recurring, ongoing (2099), has_condition,
        # urgent, overdue, OR scheduled for today (start_date = today)
        is_daily    = bool(t.get('week_days'))
        is_ongoing  = (t.get('end_date') or '') >= '2099-01-01'
        is_rec      = bool(t.get('is_recurring'))
        has_cond    = bool(t.get('has_condition'))
        is_urgent   = t.get('urgency') == 'عاجل'
        is_overdue  = (t.get('end_date') and
                       t['end_date'] < today and
                       t['end_date'] < '2099-01-01')
        has_req_amt = float(t.get('required_amount') or 0) > 0

        # Monthly recurrence: match day of month
        month_day    = int(t.get('month_day') or 0)
        is_month_day = (
            month_day > 0 and
            t.get('recurrence_type') in ('شهري', 'ربع سنوي', 'نصف سنوي') and
            d.day == month_day)
        if is_month_day:
            t['_auto_reason'] = f'📅 يوم {month_day} من كل شهر'

        # Annual recurrence: match month and day
        year_day    = t.get('year_day') or ''
        is_year_day = False
        if year_day and t.get('recurrence_type') == 'سنوي':
            try:
                ym, yd2 = year_day.split('-')
                is_year_day = (d.month == int(ym) and d.day == int(yd2))
                if is_year_day:
                    t['_auto_reason'] = f'📅 يوم سنوي ({year_day})'
            except Exception:
                pass

        # KEY RULE: if task has month_day or year_day restriction,
        # is_rec alone should NOT make it appear — only on the matching day
        rec_type = t.get('recurrence_type') or ''
        has_day_restriction = (
            (month_day > 0 and rec_type in ('شهري', 'ربع سنوي', 'نصف سنوي')) or
            (bool(year_day) and rec_type == 'سنوي'))
        if has_day_restriction:
            # Override is_rec: task only appears on its specific day
            is_rec = False  # disable daily trigger
            is_ongoing = False  # disable ongoing trigger
        # Task is within its date range (start_date <= today <= end_date)
        sd = t.get('start_date') or ''
        ed = t.get('end_date')   or ''
        is_in_range = bool(
            sd and sd <= today and
            ed and ed >= today and
            ed < '2099-01-01')

        if not (is_daily or is_ongoing or is_rec or has_cond
                or is_urgent or is_overdue or has_req_amt
                or is_in_range or is_month_day or is_year_day):
            t['_excluded'] = 'لا شرط جدولة — أضفها يدوياً'
            result.append(t)
            continue

        # Auto-reason for date-range tasks
        if is_in_range and not t.get('_auto_reason'):
            if sd == ed:
                t['_auto_reason'] = '📆 مجدولة لهذا اليوم'
            else:
                t['_auto_reason'] = f'📆 مجدولة ({sd} ← {ed})'

        # Reset status for tasks completed on previous days
        if (is_rec or is_daily or is_ongoing) and t.get('status') == 'تمت':
            comp = (t.get('completed_at') or '')[:10]
            if comp < today:
                t['status'] = 'لم تبدأ'

        ct = t.get('condition_type', '') or ''

        # Week days check — runs BEFORE condition checks
        wd_val = t.get('week_days', '') or ''
        if wd_val:
            linked_days = [int(x) for x in wd_val.split(',')
                           if x.strip().isdigit()]
            if linked_days:
                days_ar_n = ['الأحد','الاثنين','الثلاثاء',
                             'الأربعاء','الخميس','الجمعة','السبت']
                if today_idx in linked_days:
                    # Today matches — auto-include, but still run conditions
                    if not t['_auto_reason']:
                        t['_auto_reason'] = '📅 مرتبطة بهذا اليوم'
                else:
                    # Today does NOT match — exclude immediately
                    linked_names = [days_ar_n[i] for i in linked_days if i < len(days_ar_n)]
                    t['_excluded'] = 'مرتبطة بـ: ' + '، '.join(linked_names)
                    result.append(t)
                    continue

        # ── Money amount check (runs for ALL tasks with required_amount) ─
        req_amt = float(t.get('required_amount') or 0)
        if req_amt > 0 and not t['_excluded'] and not t.get('_auto_reason'):
            if not money:
                t['_excluded'] = f'يتطلب مبلغ {req_amt:.0f} ر.س (المبلغ غير متوفر)'
            elif money_amount == 0:
                t['_auto_reason'] = f'المبلغ متوفر ({req_amt:.0f} ر.س)'
            elif money_amount >= req_amt:
                t['_auto_reason'] = f'✅ المبلغ متوفر ({req_amt:.0f} ر.س ≤ {money_amount:.0f})'
            else:
                t['_excluded'] = (f'المبلغ غير كافٍ — '
                                  f'المهمة تحتاج {req_amt:.0f} ر.س '
                                  f'والمتاح {money_amount:.0f} ر.س')

        # Condition checks (for other condition types)
        if t.get('has_condition') and not t['_excluded'] and not t.get('_auto_reason'):
            if ct == 'توفر شخص':
                if t.get('person_id') and t['person_id'] in avail_persons:
                    t['_auto_reason'] = (t.get('person_name') or 'الشخص') + ' متاح اليوم'
                elif t.get('person_id'):
                    t['_excluded']    = (t.get('person_name') or '') + ' غير متاح'
            elif ct == 'توفر مكان':
                if going_out:
                    if t.get('place_id') and t['place_id'] in avail_places:
                        t['_auto_reason'] = 'ستذهب إلى ' + (t.get('place_name') or 'المكان')
                    elif t.get('place_id') and avail_places:
                        t['_excluded']    = 'لن تذهب إلى ' + (t.get('place_name') or '')
                    elif not t.get('place_id'):
                        t['_auto_reason'] = 'ستخرج اليوم'
                else:
                    t['_excluded'] = 'لن تخرج من المنزل اليوم'
            elif ct == 'توفر مبلغ':
                pass  # handled above by the required_amount check
            elif ct == 'توفر موافقة':
                t['_excluded'] = 'بانتظار الموافقة'

        # Energy filter
        if (energy == 'منخفضة' and not t['_excluded'] and
                t.get('estimated_duration', 30) > 90 and
                t.get('urgency') != 'عاجل' and
                t.get('priority') not in ('عالية جدًا', 'عالية')):
            t['_excluded'] = 'مهمة طويلة - طاقة منخفضة'

        result.append(t)

    # Occasion reminders
    upcoming = get_upcoming_occasions(plan_date, 14)
    for occ in upcoming:
        dr  = occ.get('days_remaining', 99)
        urgency_lbl = 'اليوم!' if dr == 0 else 'بعد ' + str(dr) + ' يوم'
        result.append({
            'id': -(occ['id']),
            'title': 'تذكير: ' + occ['name'] + ' - ' + urgency_lbl,
            'cat_name': 'مناسبات', 'cat_color': '#F59E0B', 'cat_icon': '🗓',
            'priority': 'عالية' if dr <= 3 else 'متوسطة',
            'urgency': 'عاجل' if dr <= 1 else 'غير عاجل',
            'estimated_duration': 10, 'status': 'لم تبدأ',
            '_excluded': None, '_auto_reason': 'مناسبة خلال ' + str(dr) + ' يوم',
            'is_occasion': True,
        })
    return result


def get_stats():
    total   = qry("SELECT COUNT(*) c FROM tasks WHERE is_deleted=0",
                  one=True)['c']
    done    = qry("SELECT COUNT(*) c FROM tasks WHERE is_deleted=0 AND status='تمت'",
                  one=True)['c']
    pending = qry("SELECT COUNT(*) c FROM tasks WHERE is_deleted=0 "
                  "AND status NOT IN('تمت','ملغاة','محذوفة')",
                  one=True)['c']
    today_s = date.today().isoformat()
    overdue = qry("SELECT COUNT(*) c FROM tasks WHERE is_deleted=0 "
                  "AND status NOT IN('تمت','ملغاة') AND end_date<? "
                  "AND end_date<'2099-01-01'",
                  (today_s,), one=True)['c']
    by_cat  = qry("""SELECT c.name, c.color, c.icon, COUNT(*) cnt,
               SUM(CASE WHEN t.status='تمت' THEN 1 ELSE 0 END) done
               FROM tasks t JOIN categories c ON t.category_id=c.id
               WHERE t.is_deleted=0 GROUP BY c.id ORDER BY cnt DESC""")
    return {'total':total, 'completed':done,
            'pending':pending, 'overdue':overdue, 'by_cat':by_cat}

def add_sample_data():
    if get_tasks():
        return
    today = date.today().isoformat()
    nw    = (date.today() + timedelta(7)).isoformat()
    tom   = (date.today() + timedelta(1)).isoformat()
    cats  = {c['name']: c['id'] for c in get_categories()}
    sample = [
        {'title':'أذكار الصباح','task_type':'عادة',
         'category_id':cats.get('عبادة'),'priority':'عالية',
         'urgency':'عاجل','estimated_duration':15,
         'preferred_time':'الصباح','start_date':today,'end_date':nw,
         'is_recurring':1,'recurrence_type':'يومي','status':'لم تبدأ'},
        {'title':'قراءة القرآن الكريم','task_type':'عادة',
         'category_id':cats.get('عبادة'),'priority':'عالية',
         'urgency':'غير عاجل','estimated_duration':30,
         'preferred_time':'الصباح','start_date':today,'end_date':nw,
         'is_recurring':1,'recurrence_type':'يومي','status':'لم تبدأ'},
        {'title':'مراجعة خطة الأسبوع','task_type':'مهمة',
         'category_id':cats.get('عمل'),'priority':'عالية',
         'urgency':'عاجل','estimated_duration':45,
         'preferred_time':'الصباح','start_date':today,'end_date':today,
         'status':'لم تبدأ'},
        {'title':'تمارين رياضية','task_type':'عادة',
         'category_id':cats.get('صحة'),'priority':'متوسطة',
         'urgency':'غير عاجل','estimated_duration':45,
         'preferred_time':'الصباح','start_date':today,'end_date':nw,
         'is_recurring':1,'recurrence_type':'يومي','status':'لم تبدأ'},
        {'title':'الاتصال بالوالدين','task_type':'التزام',
         'category_id':cats.get('أسرة'),'priority':'عالية',
         'urgency':'غير عاجل','estimated_duration':20,
         'preferred_time':'المساء','start_date':today,'end_date':today,
         'status':'لم تبدأ'},
        {'title':'إعداد تقرير الأداء الشهري','task_type':'مهمة',
         'category_id':cats.get('عمل'),'priority':'عالية جدًا',
         'urgency':'عاجل','estimated_duration':90,
         'preferred_time':'الصباح','start_date':today,'end_date':tom,
         'status':'قيد التنفيذ','progress':40},
        {'title':'شراء احتياجات المنزل','task_type':'شراء',
         'category_id':cats.get('منزل'),'priority':'متوسطة',
         'urgency':'غير عاجل','estimated_duration':60,
         'preferred_time':'المساء','start_date':today,'end_date':nw,
         'has_condition':1,'condition_type':'توفر مكان',
         'condition_details':'عند الذهاب للسوق','status':'بانتظار شرط'},
        {'title':'قراءة كتاب تطوير شخصي','task_type':'هدف',
         'category_id':cats.get('تطوير الذات'),'priority':'متوسطة',
         'urgency':'غير عاجل','estimated_duration':30,
         'preferred_time':'المساء','start_date':today,'end_date':nw,
         'status':'لم تبدأ'},
        {'title':'أذكار المساء','task_type':'عادة',
         'category_id':cats.get('عبادة'),'priority':'عالية',
         'urgency':'غير عاجل','estimated_duration':15,
         'preferred_time':'المساء','start_date':today,'end_date':nw,
         'is_recurring':1,'recurrence_type':'يومي','status':'لم تبدأ'},
        {'title':'متابعة بريد العمل','task_type':'متابعة',
         'category_id':cats.get('عمل'),'priority':'متوسطة',
         'urgency':'غير عاجل','estimated_duration':20,
         'preferred_time':'الصباح','start_date':today,'end_date':nw,
         'is_recurring':1,'recurrence_type':'يومي','status':'لم تبدأ'},
    ]
    for t in sample:
        add_task(t)
    for name, phone in [("أحمد","0501234567"),("محمد","0507654321"),("المدير","")]:
        exe("INSERT INTO persons(name,phone) VALUES(?,?)", (name, phone))
    for pl in ["العمل","السوق","البنك","المستشفى","المسجد"]:
        exe("INSERT INTO places(name) VALUES(?)", (pl,))
    cats_list = get_categories()
    hid = next((c['id'] for c in cats_list if c['name'] == 'صحة'), None)
    wid = next((c['id'] for c in cats_list if c['name'] == 'عمل'), None)
    add_goal({'title':'تحسين اللياقة البدنية',
              'description':'رياضة يومية ونظام غذائي صحي',
              'category_id':hid,
              'end_date':(date.today()+timedelta(90)).isoformat(),
              'target_result':'رياضة 5 مرات أسبوعيًا'})
    add_goal({'title':'تطوير مهارات العمل',
              'description':'دورات وكتب في التخصص',
              'category_id':wid,
              'end_date':(date.today()+timedelta(180)).isoformat(),
              'target_result':'إتمام 3 دورات و6 كتب'})


# ══════════════════════════════════════════════════════════
#  QT IMPORTS & STYLES
# ══════════════════════════════════════════════════════════
