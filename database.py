# -*- coding: utf-8 -*-
import sqlite3
import os
from datetime import datetime, date


class Database:
    _instance = None

    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            app_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(app_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            cls._db_path = db_path or os.path.join(data_dir, 'student_checkin.db')
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        self.conn = sqlite3.connect(self._db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, sort_order INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, class_id INTEGER, remaining_hours INTEGER DEFAULT 0, total_hours INTEGER DEFAULT 0, pinyin_initial TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, checkin_time TEXT NOT NULL, period TEXT NOT NULL, FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE)")
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()
        c.execute("SELECT COUNT(*) FROM classes")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO classes (name, sort_order) VALUES (?, ?)", ("默认班级", 0))
        defaults = {"morning_start": "06:00", "morning_end": "12:00",
                    "afternoon_start": "12:00", "afternoon_end": "18:00",
                    "evening_start": "18:00", "evening_end": "21:00"}
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        self.conn.commit()

    def get_setting(self, key, default=None):
        c = self.conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = c.fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    def get_all_period_settings(self):
        keys = ["morning_start", "morning_end", "afternoon_start",
                "afternoon_end", "evening_start", "evening_end"]
        return {k: self.get_setting(k, "") for k in keys}

    def set_all_period_settings(self, s):
        for k, v in s.items():
            self.set_setting(k, v)

    @staticmethod
    def _time_to_minutes(t):
        p = t.split(":")
        return int(p[0]) * 60 + int(p[1])

    def get_current_period(self):
        now = datetime.now()
        cur = now.hour * 60 + now.minute
        periods = {
            "上午": (self.get_setting("morning_start", "06:00"), self.get_setting("morning_end", "12:00")),
            "下午": (self.get_setting("afternoon_start", "12:00"), self.get_setting("afternoon_end", "18:00")),
            "晚上": (self.get_setting("evening_start", "18:00"), self.get_setting("evening_end", "21:00")),
        }
        for n, (s, e) in periods.items():
            try:
                if self._time_to_minutes(s) <= cur < self._time_to_minutes(e):
                    return n
            except Exception:
                pass
        # 不在任何时段内 → 选最近的（按开始时间距离当前最近）
        best, best_diff = "上午", 99999
        for n, (s, e) in periods.items():
            try:
                sm = self._time_to_minutes(s)
                diff = abs(cur - sm)
                if diff < best_diff:
                    best_diff, best = diff, n
            except Exception:
                pass
        return best

    def get_all_classes(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM classes ORDER BY sort_order, id")
        return [dict(r) for r in c.fetchall()]

    def add_class(self, name):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO classes (name) VALUES (?)", (name,))
            self.conn.commit()
            return c.lastrowid
        except Exception:
            return None

    def update_class(self, cid, name):
        c = self.conn.cursor()
        c.execute("UPDATE classes SET name=? WHERE id=?", (name, cid))
        self.conn.commit()

    def delete_class(self, cid):
        c = self.conn.cursor()
        c.execute("UPDATE students SET class_id=NULL WHERE class_id=?", (cid,))
        c.execute("DELETE FROM classes WHERE id=?", (cid,))
        self.conn.commit()

    def _pi(self, name):
        if not name:
            return "#"
        ch = name[0].upper()
        if "A" <= ch <= "Z":
            return ch
        return "#"

    def add_student(self, name, class_id=None, init_hours=0):
        c = self.conn.cursor()
        c.execute("INSERT INTO students (name,class_id,remaining_hours,total_hours,pinyin_initial) VALUES (?,?,?,?,?)",
                  (name, class_id, init_hours, init_hours, self._pi(name)))
        self.conn.commit()
        return c.lastrowid

    def update_student(self, sid, name=None, class_id=None):
        c = self.conn.cursor()
        ups, params = [], []
        if name is not None:
            ups.append("name=?")
            params.append(name)
            ups.append("pinyin_initial=?")
            params.append(self._pi(name))
        if class_id is not None:
            ups.append("class_id=?")
            params.append(class_id)
        if ups:
            params.append(sid)
            c.execute("UPDATE students SET " + ",".join(ups) + " WHERE id=?", params)
            self.conn.commit()

    def delete_student(self, sid):
        c = self.conn.cursor()
        c.execute("DELETE FROM students WHERE id=?", (sid,))
        self.conn.commit()

    def get_student(self, sid):
        c = self.conn.cursor()
        c.execute("SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id WHERE s.id=?", (sid,))
        row = c.fetchone()
        return dict(row) if row else None

    def get_all_students(self):
        c = self.conn.cursor()
        c.execute("SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id ORDER BY c.sort_order, s.pinyin_initial, s.name")
        return [dict(r) for r in c.fetchall()]

    def get_students_by_class(self, cid):
        c = self.conn.cursor()
        c.execute("SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id WHERE s.class_id=? ORDER BY s.pinyin_initial, s.name", (cid,))
        return [dict(r) for r in c.fetchall()]

    def get_students_grouped(self, search=None):
        classes = self.get_all_classes()
        result = []
        for cls in classes:
            ss = self.get_students_by_class(cls["id"])
            if search:
                ss = [s for s in ss if search in s["name"]]
                if ss:  # 搜索模式：只显示有匹配学生的班级
                    result.append({"class": cls, "students": ss})
            else:
                # 非搜索模式：所有班级都显示（即使没学生）
                result.append({"class": cls, "students": ss})
        # 未分组
        c = self.conn.cursor()
        if search:
            c.execute("SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id WHERE s.class_id IS NULL AND s.name LIKE ? ORDER BY s.pinyin_initial, s.name", ("%" + search + "%",))
        else:
            c.execute("SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id WHERE s.class_id IS NULL ORDER BY s.pinyin_initial, s.name")
        ug = [dict(r) for r in c.fetchall()]
        if ug:
            result.append({"class": {"id": None, "name": "未分组", "sort_order": 999}, "students": ug})
        return result

    def add_hours(self, sid, hours):
        c = self.conn.cursor()
        c.execute("UPDATE students SET remaining_hours=remaining_hours+?, total_hours=total_hours+? WHERE id=?", (hours, hours, sid))
        self.conn.commit()

    def deduct_hours(self, sid, hours=1):
        c = self.conn.cursor()
        c.execute("UPDATE students SET remaining_hours=MAX(0, remaining_hours-?) WHERE id=?", (hours, sid))
        self.conn.commit()

    def checkin(self, sid, period=None, t=None):
        if t is None:
            t = datetime.now()
        if period is None:
            period = self.get_current_period()
        c = self.conn.cursor()
        c.execute("INSERT INTO checkins (student_id,checkin_time,period) VALUES (?,?,?)",
                  (sid, t.strftime("%Y-%m-%d %H:%M:%S"), period))
        self.deduct_hours(sid, 1)
        self.conn.commit()
        return c.lastrowid

    def undo_checkin_today(self, sid):
        """撤销该学生今天最近的一条签到记录，加回 1 课时。返回 True 表示成功"""
        today = date.today().strftime('%Y-%m-%d')
        c = self.conn.cursor()
        c.execute(
            "SELECT id FROM checkins WHERE student_id=? AND date(checkin_time)=? ORDER BY checkin_time DESC LIMIT 1",
            (sid, today))
        row = c.fetchone()
        if not row:
            return False
        c.execute("DELETE FROM checkins WHERE id=?", (row[0],))
        c.execute("UPDATE students SET remaining_hours=remaining_hours+1 WHERE id=?", (sid,))
        self.conn.commit()
        return True

    def undo_checkin_in_period(self, sid, sel_date, sel_period):
        """撤销该学生指定日期+时段的签到，加回 1 课时。返回 True 表示成功"""
        dstr = sel_date.strftime('%Y-%m-%d')
        c = self.conn.cursor()
        c.execute(
            "SELECT id FROM checkins WHERE student_id=? AND date(checkin_time)=? AND period=? ORDER BY checkin_time DESC LIMIT 1",
            (sid, dstr, sel_period))
        row = c.fetchone()
        if not row:
            return False
        c.execute("DELETE FROM checkins WHERE id=?", (row[0],))
        c.execute("UPDATE students SET remaining_hours=remaining_hours+1 WHERE id=?", (sid,))
        self.conn.commit()
        return True

    def get_checkins_by_student(self, sid, limit=None):
        c = self.conn.cursor()
        if limit:
            c.execute("SELECT * FROM checkins WHERE student_id=? ORDER BY checkin_time DESC LIMIT ?", (sid, limit))
        else:
            c.execute("SELECT * FROM checkins WHERE student_id=? ORDER BY checkin_time DESC", (sid,))
        return [dict(r) for r in c.fetchall()]

    def get_checkins_today(self, sid):
        today = date.today().strftime("%Y-%m-%d")
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM checkins WHERE student_id=? AND date(checkin_time)=?", (sid, today))
        return c.fetchone()[0]

    def get_student_stats(self, sid):
        s = self.get_student(sid)
        if not s:
            return None
        chs = self.get_checkins_by_student(sid)
        stats = {"上午": 0, "下午": 0, "晚上": 0}
        for ch in chs:
            if ch["period"] in stats:
                stats[ch["period"]] += 1
        return {"student": s, "recent": chs[:5], "total": len(chs), "period_stats": stats, "all_checkins": chs}

    def clear_all_data(self, clear_classes=False):
        c = self.conn.cursor()
        c.execute("DELETE FROM checkins")
        c.execute("DELETE FROM students")
        if clear_classes:
            c.execute("DELETE FROM classes")
            c.execute("INSERT INTO classes (name, sort_order) VALUES (?, ?)", ("默认班级", 0))
        self.conn.commit()

    def export_to_excel(self, filepath):
        """导出一个整合表格：每个学生一行，显示课时和最近一年签到情况"""
        from datetime import date, timedelta
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

        wb = Workbook()
        ws = wb.active
        ws.title = "学生课时与签到汇总"

        headers = ["序号", "姓名", "班级", "剩余课时", "已上课时",
                   "最近一年签到次数", "最近一年签到日期"]
        hfont = Font(bold=True, size=12, color="FFFFFF")
        hfill = PatternFill(start_color="4A90D9", end_color="4A90D9", fill_type="solid")
        halign = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        thin = Side(style="thin", color="CCCCCC")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for col, h in enumerate(headers, 1):
            cc = ws.cell(row=1, column=col, value=h)
            cc.font = hfont
            cc.fill = hfill
            cc.alignment = halign
            cc.border = border

        one_year_ago = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')
        students = self.get_all_students()

        for idx, s in enumerate(students, 1):
            cn = s.get("class_name") or "未分组"
            rem = s["remaining_hours"]
            used = s["total_hours"]

            # 查最近一年签到
            c = self.conn.cursor()
            c.execute(
                "SELECT checkin_time, period FROM checkins "
                "WHERE student_id=? AND date(checkin_time)>=? "
                "ORDER BY checkin_time ASC",
                (s["id"], one_year_ago))
            recent = c.fetchall()
            recent_count = len(recent)
            # 日期列表，如 "03-15上午, 03-16下午, 04-02上午"
            dates_strs = []
            for t, period in recent:
                short_date = t[5:10]  # MM-DD
                dates_strs.append(f"{short_date}{period}")
            dates_combined = "  ".join(dates_strs)

            row = [idx, s["name"], cn, rem, used, recent_count, dates_combined]
            for col, val in enumerate(row, 1):
                cc = ws.cell(row=idx + 1, column=col, value=val)
                cc.border = border
                if col in [1, 4, 5, 6]:  # 序号、课时、次数
                    cc.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cc.alignment = left_align

        # 列宽
        col_widths = [6, 14, 14, 10, 10, 14, 60]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[chr(64 + i)].width = w

        # 行高（日期列可能多行）
        for r in range(2, len(students) + 2):
            ws.row_dimensions[r].height = 24

        # 统计汇总
        row_no = len(students) + 3
        ws.cell(row=row_no, column=1, value="统计汇总").font = Font(bold=True)
        ws.merge_cells(start_row=row_no, start_column=1,
                       end_row=row_no, end_column=4)

        row_no += 1
        ws.cell(row=row_no, column=1, value="学生总数").font = Font(bold=True)
        ws.cell(row=row_no, column=2, value=len(students))
        total_used = sum(s["total_hours"] for s in students)
        ws.cell(row=row_no, column=3, value="累计已上课时").font = Font(bold=True)
        ws.cell(row=row_no, column=4, value=total_used)

        wb.save(filepath)
        return True

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
