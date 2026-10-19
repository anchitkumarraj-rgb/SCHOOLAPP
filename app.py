import streamlit as st, sqlite3, hashlib, os, calendar, datetime as dt
import pandas as pd

SCHOOL = "Ideal Public School, Bhangiya"
FEE = 500                 # Admission fee in rupees
UPI_ID = "9576826926-l6f9@ibl"     # Put your real UPI ID here
DEFAULT_PW = "123456"     # Starting password for new students
CLASSES = ["Nursery", "LKG", "UKG"] + [f"Class {i}" for i in range(1, 11)]
STATUS = {"P": "Present", "A": "Absent", "L": "Leave"}

# The database is always created in the same folder as this file
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "school.db")
UP = os.path.join(BASE, "uploads")
os.makedirs(UP, exist_ok=True)

CSS = """<style>
#MainMenu, footer {visibility:hidden;}
.block-container {padding-top:1.2rem; max-width:1000px;}
.hero {background:linear-gradient(135deg,#4f46e5,#7c3aed); color:#fff; padding:18px 22px;
       border-radius:16px; margin-bottom:16px;}
.hero h2 {margin:0; color:#fff; font-size:1.45rem;}
.hero p {margin:4px 0 0; opacity:.9;}
.card {background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:14px 8px;
       box-shadow:0 1px 4px rgba(0,0,0,.07); text-align:center;}
.card b {display:block; font-size:1.8rem; color:#4f46e5;}
.card span {color:#6b7280; font-size:.85rem;}
.stButton>button, .stDownloadButton>button {border-radius:10px; font-weight:600;}
</style>"""


# ---------------- Database ----------------
def q(sql, args=(), commit=False):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(sql, args).fetchall()
    if commit:
        con.commit()
    con.close()
    return rows


def ins(sql, args=()):
    con = sqlite3.connect(DB)
    cur = con.execute(sql, args)
    con.commit()
    i = cur.lastrowid
    con.close()
    return i


def many(sql, rows):
    con = sqlite3.connect(DB)
    con.executemany(sql, rows)
    con.commit()
    con.close()


def h(p):
    return hashlib.sha256(("sch$" + p).encode()).hexdigest()


def save_file(f, prefix):
    name = f"{prefix}_{dt.datetime.now():%Y%m%d%H%M%S}_{os.path.basename(f.name).replace(' ', '_')}"
    path = os.path.join(UP, name)
    with open(path, "wb") as out:
        out.write(f.getbuffer())
    return path


def show_img(path, **kw):
    if path and os.path.exists(path):
        st.image(path, **kw)


def init():
    q("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE,
         pw TEXT, role TEXT, name TEXT, cls TEXT, roll INTEGER)""", commit=True)
    q("""CREATE TABLE IF NOT EXISTS attendance(d TEXT, sid INTEGER, status TEXT,
         PRIMARY KEY(d, sid))""", commit=True)
    q("""CREATE TABLE IF NOT EXISTS homework(id INTEGER PRIMARY KEY, cls TEXT, title TEXT,
         body TEXT, due TEXT, img TEXT)""", commit=True)
    q("""CREATE TABLE IF NOT EXISTS subs(id INTEGER PRIMARY KEY, hw INTEGER, sid INTEGER,
         path TEXT, t TEXT)""", commit=True)
    q("CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY, cls TEXT, body TEXT, d TEXT)", commit=True)
    q("""CREATE TABLE IF NOT EXISTS admissions(id INTEGER PRIMARY KEY, name TEXT, parent TEXT,
         phone TEXT, cls TEXT, txn TEXT, proof TEXT, status TEXT, d TEXT)""", commit=True)
    if "father" not in [c["name"] for c in q("PRAGMA table_info(users)")]:
        q("ALTER TABLE users ADD COLUMN father TEXT DEFAULT ''", commit=True)
    if not q("SELECT 1 FROM users WHERE role='admin'"):
        q("INSERT INTO users(username,pw,role,name) VALUES('admin',?,'admin','Principal')",
          (h("admin123"),), commit=True)


def add_student(name, cls, roll=None, pw=DEFAULT_PW, father=""):
    if roll is None:
        roll = q("SELECT COALESCE(MAX(roll),0) m FROM users WHERE role='student' AND cls=?", (cls,))[0]["m"] + 1
    i = ins("INSERT INTO users(username,pw,role,name,cls,roll,father) VALUES(?,?,?,?,?,?,?)",
            (f"tmp{os.urandom(4).hex()}", h(pw), "student", name.strip(), cls, int(roll), father.strip()))
    uname = f"S{i:04d}"
    q("UPDATE users SET username=? WHERE id=?", (uname, i), commit=True)
    return uname, int(roll)


def students_of(cls):
    res = q("SELECT id,roll,name,father,username FROM users WHERE role='student' AND cls=? ORDER BY roll, id", (cls,))
    return [dict(row) for row in res]


# ---------------- Look and feel ----------------
def hero(title, sub=""):
    st.markdown(f"<div class='hero'><h2>{title}</h2><p>{sub}</p></div>", unsafe_allow_html=True)


def card(col, num, label):
    col.markdown(f"<div class='card'><b>{num}</b><span>{label}</span></div>", unsafe_allow_html=True)


# ---------------- Login and admission ----------------
def login_page():
    u = st.text_input("Username", key="lu")
    p = st.text_input("Password", type="password", key="lp")
    if st.button("Login", type="primary", use_container_width=True):
        r = q("SELECT * FROM users WHERE username=? AND pw=?", (u.strip(), h(p)))
        if r:
            st.session_state.user = dict(r[0])
            st.rerun()
        else:
            st.error("Wrong username or password")


def admission_page():
    st.info(f"Admission fee: Rs {FEE}   |   UPI ID: {UPI_ID}\n\nPay the fee first, then enter the Transaction ID below.")
    name = st.text_input("Student's name")
    parent = st.text_input("Parent's name")
    phone = st.text_input("Mobile number")
    cls = st.selectbox("Class for admission", CLASSES, key="adm_cls")
    txn = st.text_input("Transaction ID")
    proof = st.file_uploader("Payment screenshot", type=["jpg", "jpeg", "png"])
    if st.button("Submit application", type="primary", use_container_width=True):
        if not (name and parent and phone and txn):
            st.error("Please fill in all details")
            return
        i = ins("INSERT INTO admissions(name,parent,phone,cls,txn,proof,status,d) VALUES(?,?,?,?,?,?,?,?)",
                (name, parent, phone, cls, txn, save_file(proof, "pay") if proof else "", "pending",
                 str(dt.date.today())))
        st.success(f"Application submitted (number {i}). The school will contact you after checking.")


# ---------------- Home pages ----------------
def staff_home(u):
    hero(f"Hello, {u['name']} 👋", f"{SCHOOL} • {dt.date.today():%d-%m-%Y}")
    today = str(dt.date.today())
    n = lambda sql, a=(): q(sql, a)[0]["c"]
    c = st.columns(4)
    card(c[0], n("SELECT COUNT(*) c FROM users WHERE role='student'"), "Total students")
    card(c[1], n("SELECT COUNT(*) c FROM attendance WHERE d=? AND status='P'", (today,)), "Present today")
    card(c[2], n("SELECT COUNT(*) c FROM attendance WHERE d=? AND status='A'", (today,)), "Absent today")
    card(c[3], n("SELECT COUNT(*) c FROM admissions WHERE status='pending'"), "New applications")
    st.write("")
    strength = {r["cls"]: r["c"] for r in q("SELECT cls, COUNT(*) c FROM users WHERE role='student' GROUP BY cls")}
    done = {r["cls"] for r in q("SELECT DISTINCT u.cls FROM attendance a JOIN users u ON u.id=a.sid WHERE a.d=?", (today,))}
    todo = [x for x in CLASSES if x in strength and x not in done]
    if todo:
        st.warning("Today's attendance is pending for: " + ", ".join(todo))
    elif strength:
        st.success("Attendance has been taken for all classes today ✅")
    if strength:
        st.markdown("##### 📊 Students per class")
        st.bar_chart(pd.Series(strength).reindex([x for x in CLASSES if x in strength]))
    else:
        st.info("To begin, open 'Students' in the left menu and add students.")


def student_home(u):
    hero(f"Hello, {u['name']} 👋", f"{u['cls']} • Roll No. {u['roll']}")
    rows = q("SELECT status FROM attendance WHERE sid=?", (u["id"],))
    tot, p = len(rows), sum(r["status"] == "P" for r in rows)
    pend = q("""SELECT COUNT(*) c FROM homework h WHERE h.cls=? AND
                NOT EXISTS (SELECT 1 FROM subs s WHERE s.hw=h.id AND s.sid=?)""", (u["cls"], u["id"]))[0]["c"]
    c = st.columns(3)
    card(c[0], f"{p / tot * 100:.0f}%" if tot else "-", "Attendance")
    card(c[1], p, "Days present")
    card(c[2], pend, "Pending homework")
    st.write("")
    notices_view(u, home=True)


# ---------------- Attendance ----------------
def attendance_page(u):
    hero("✅ Take Attendance", "Choose a class, mark each student and save")
    c1, c2 = st.columns(2)
    cls = c1.selectbox("Class", CLASSES)
    d = c2.date_input("Date", dt.date.today())
    kids = students_of(cls)
    if not kids:
        st.warning(f"There are no students in {cls} yet. Add students from the 'Students' menu first.")
        return
    if d.weekday() == 6:
        st.info("Note: this date is a Sunday.")
    old = {r["sid"]: r["status"] for r in q("SELECT sid,status FROM attendance WHERE d=?", (str(d),))}
    st.caption(f"Total students: {len(kids)}  •  " +
               ("Attendance for this date is already saved, you can change it" if any(k["id"] in old for k in kids)
                else "Attendance for this date is not taken yet (everyone is set to Present)"))
    with st.form(f"att_{cls}_{d}"):
        a, b, c = st.columns([1, 4, 6])
        a.markdown("**Roll**"); b.markdown("**Name**"); c.markdown("**Status**")
        sel = {}
        for k in kids:
            a, b, c = st.columns([1, 4, 6])
            a.write(str(k["roll"]))
            b.write(k["name"])
            sel[k["id"]] = c.radio("Status", ["P", "A", "L"], index=["P", "A", "L"].index(old.get(k["id"], "P")),
                                   format_func=STATUS.get, horizontal=True,
                                   key=f"r{k['id']}_{d}", label_visibility="collapsed")
        if st.form_submit_button("💾 Save attendance", type="primary", use_container_width=True):
            many("INSERT OR REPLACE INTO attendance(d,sid,status) VALUES(?,?,?)",
                 [(str(d), sid, s) for sid, s in sel.items()])
            v = list(sel.values())
            st.success(f"Attendance of {cls} for {d:%d-%m-%Y} saved: Present {v.count('P')}, "
                       f"Absent {v.count('A')}, Leave {v.count('L')}")


def month_list():
    first = dt.date.today().replace(day=1)
    months = []
    for i in range(12):
        y, m = divmod(first.year * 12 + first.month - 1 - i, 12)
        months.append(f"{y}-{m + 1:02d}")
    return months


def register_page(u):
    hero("📒 Monthly Attendance Register", "Roll, name, father's name and every date of the month")
    c1, c2 = st.columns(2)
    cls = c1.selectbox("Class", CLASSES, key="reg_cls")
    ym = c2.selectbox("Month", month_list(), key="reg_ym")
    y, m = int(ym[:4]), int(ym[5:])
    kids = students_of(cls)
    if not kids:
        st.warning(f"There are no students in {cls} yet. Add students from the 'Students' menu first.")
        return
    rec = {(r["sid"], r["d"]): r["status"] for r in q("SELECT sid,d,status FROM attendance WHERE d LIKE ?", (ym + "%",))}
    wd = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    rows = []
    for k in kids:
        row = {"Roll": k["roll"], "Name": k["name"], "Father's Name": k["father"] or ""}
        p = a = 0
        for d in range(1, calendar.monthrange(y, m)[1] + 1):
            s = rec.get((k["id"], f"{ym}-{d:02d}"), "")
            row[f"{d} {wd[dt.date(y, m, d).weekday()]}"] = s
            p += s == "P"
            a += s == "A"
        row["Total P"], row["Total A"] = p, a
        rows.append(row)
    df = pd.DataFrame(rows)
    st.caption(f"{cls} • {m:02d}-{y} • Total students {len(kids)}   |   P = Present, A = Absent, L = Leave, blank = not taken")

    def color(v):
        return {"A": "background-color:#fecaca", "P": "background-color:#bbf7d0",
                "L": "background-color:#fef08a"}.get(v, "")
    sty = df.style
    sty = (sty.map if hasattr(sty, "map") else sty.applymap)(color, subset=list(df.columns[3:-2]))
    st.dataframe(sty, hide_index=True, use_container_width=True)
    st.download_button("⬇️ Download register (opens in Excel)", df.to_csv(index=False).encode("utf-8-sig"),
                       f"{cls}_{ym}_register.csv")
    st.caption("To fill or change a date, open 'Take Attendance' and pick that date.")


def report_page(u):
    hero("📊 Attendance Report", "Monthly summary of a class")
    c1, c2 = st.columns(2)
    cls = c1.selectbox("Class", CLASSES)
    ym = c2.selectbox("Month", month_list())
    rows = q("""SELECT u.roll, u.name, a.status FROM users u
                LEFT JOIN attendance a ON a.sid=u.id AND a.d LIKE ?
                WHERE u.role='student' AND u.cls=?""", (ym + "%", cls))
    if not rows:
        st.info("There are no students in this class")
        return
    df = pd.DataFrame([dict(r) for r in rows])
    g = df.groupby(["roll", "name"]).status.agg(
        P=lambda s: int((s == "P").sum()), A=lambda s: int((s == "A").sum()),
        L=lambda s: int((s == "L").sum())).reset_index().sort_values("roll")
    g["days"] = g["P"] + g["A"] + g["L"]
    g["pct"] = (g["P"] * 100 / g["days"].where(g["days"] > 0)).round(1).fillna(0)
    g.columns = ["Roll", "Name", "Present", "Absent", "Leave", "Total Days", "Percentage"]
    low = g[(g["Total Days"] > 0) & (g["Percentage"] < 75)]
    if len(low):
        st.warning("Below 75% attendance: " + ", ".join(low["Name"]))
    st.dataframe(g, hide_index=True, use_container_width=True)
    st.download_button("⬇️ Download CSV", g.to_csv(index=False).encode("utf-8-sig"), f"{cls}_{ym}.csv")


def my_attendance(u):
    hero("📅 My Attendance")
    rows = q("SELECT d,status FROM attendance WHERE sid=? ORDER BY d DESC", (u["id"],))
    if not rows:
        st.info("No records yet")
        return
    ym = st.selectbox("Month", sorted({r["d"][:7] for r in rows}, reverse=True))
    mr = [r for r in rows if r["d"].startswith(ym)]
    p = sum(r["status"] == "P" for r in mr)
    c = st.columns(3)
    card(c[0], f"{p / len(mr) * 100:.0f}%", "Attendance this month")
    card(c[1], p, "Present")
    card(c[2], sum(r["status"] == "A" for r in mr), "Absent")
    st.write("")
    st.dataframe(pd.DataFrame([{"Date": dt.date.fromisoformat(r["d"]).strftime("%d-%m-%Y (%a)"),
                                "Status": STATUS[r["status"]]} for r in mr]),
                 hide_index=True, use_container_width=True)


# ---------------- Student and teacher management ----------------
def students_page(u):
    hero("🎓 Students", "Add students once - the data is saved forever")
    cls = st.selectbox("Select class", CLASSES)
    raw_kids = students_of(cls)
    kids = [dict (row) for row in raw_kids]
    kids = students_of(cls)
    t1, t2, t3 = st.tabs([f"📋 List ({len(kids)})", "➕ One student", "📥 Many students at once"])
    with t1:
        if not kids:
            st.info("There are no students in this class yet")
        else:
            st.dataframe(pd.DataFrame([{"Roll": k["roll"], "Name": k["name"], "Father's Name": k["father"] or "",
                                        "Username": k["username"]} for k in kids]),
                         hide_index=True, use_container_width=True)
            who = st.selectbox("Select a student to edit", kids, format_func=lambda k: f"{k['roll']} - {k['name']}")
            nm = st.text_input("Name", who["name"], key=f"n{who['id']}")
            fa = st.text_input("Father's name", who["father"] or "", key=f"fa{who['id']}")
            rl = st.number_input("Roll number", 1, 500, int(who["roll"]), key=f"rl{who['id']}")
            b = st.columns(3)
            if b[0].button("✏️ Update", use_container_width=True):
                q("UPDATE users SET name=?, roll=?, father=? WHERE id=?", (nm.strip(), int(rl), fa.strip(), who["id"]), commit=True)
                st.rerun()
            if b[1].button("🔑 Reset password", use_container_width=True):
                q("UPDATE users SET pw=? WHERE id=?", (h(DEFAULT_PW), who["id"]), commit=True)
                st.success(f"Password reset to {DEFAULT_PW}")
            if b[2].button("🗑️ Delete", use_container_width=True):
                st.session_state.confirm_del = who["id"]
            if st.session_state.get("confirm_del") == who["id"]:
                st.error(f"Delete {who['name']} permanently?")
                if st.button("Yes, delete"):
                    for t, col in (("attendance", "sid"), ("subs", "sid"), ("users", "id")):
                        q(f"DELETE FROM {t} WHERE {col}=?", (who["id"],), commit=True)
                    st.session_state.confirm_del = None
                    st.rerun()
    with t2:
        nm = st.text_input("Student's name", key="one_n")
        fa = st.text_input("Father's name", key="one_f")
        nxt = (max(k["roll"] for k in kids) + 1) if kids else 1
        rl = st.number_input("Roll number", 1, 500, nxt, key=f"one_r_{cls}_{nxt}")
        pw = st.text_input("Password", DEFAULT_PW, key="one_p")
        if st.button("➕ Add student", type="primary"):
            if nm.strip():
                un, r = add_student(nm, cls, rl, pw, fa)
                st.success(f"{nm} added - username: {un}, roll: {r}")
            else:
                st.error("Please enter a name")
    with t3:
        st.caption("One student per line: student name, father's name (separated by a comma). "
                   "Example: Rahul Kumar, Suresh Kumar. Roll numbers are given automatically.")
        txt = st.text_area("List of names", height=200, key=f"bulk_{cls}")
        if st.button("📥 Add all", type="primary"):
            names = [x.strip() for x in txt.splitlines() if x.strip()]
            if not names:
                st.error("Please enter at least one name")
            else:
                out = []
                for x in names:
                    nm_, _, fa_ = x.partition(",")
                    un, r = add_student(nm_, cls, None, DEFAULT_PW, fa_.strip())
                    out.append({"Roll": r, "Name": nm_.strip(), "Father's Name": fa_.strip(),
                                "Username": un, "Password": DEFAULT_PW})
                st.success(f"{len(out)} students added to {cls}")
                df = pd.DataFrame(out)
                st.dataframe(df, hide_index=True, use_container_width=True)
                st.download_button("⬇️ Download login list", df.to_csv(index=False).encode("utf-8-sig"),
                                   f"{cls}_login_list.csv")


def teachers_page(u):
    hero("👤 Teachers")
    name = st.text_input("Teacher's name")
    un = st.text_input("Username")
    pw = st.text_input("Password")
    if st.button("➕ Add teacher", type="primary"):
        if name and un and pw:
            try:
                q("INSERT INTO users(username,pw,role,name) VALUES(?,?,'teacher',?)", (un.strip(), h(pw), name), commit=True)
                st.success("Teacher added")
            except sqlite3.IntegrityError:
                st.error("This username already exists")
        else:
            st.error("Please fill in all details")
    st.markdown("##### Current teachers")
    for t in q("SELECT id,name,username FROM users WHERE role='teacher'"):
        c = st.columns([4, 1])
        c[0].write(f"👤 {t['name']}  ({t['username']})")
        if c[1].button("🗑️", key=f"dt{t['id']}"):
            q("DELETE FROM users WHERE id=?", (t["id"],), commit=True)
            st.rerun()


# ---------------- Homework ----------------
def homework_page(u):
    hero("📚 Homework", "Send homework and view the photos students submit")
    cls = st.selectbox("Class", CLASSES)
    t1, t2 = st.tabs(["➕ New homework", "📥 Submitted work"])
    with t1:
        title = st.text_input("Subject / title")
        body = st.text_area("Homework details")
        due = st.date_input("Due date", dt.date.today() + dt.timedelta(days=1))
        img = st.file_uploader("Attach a photo (optional)", type=["jpg", "jpeg", "png"])
        if st.button("📤 Send homework", type="primary"):
            if title:
                ins("INSERT INTO homework(cls,title,body,due,img) VALUES(?,?,?,?,?)",
                    (cls, title, body, str(due), save_file(img, "hwq") if img else ""))
                st.success("Homework sent")
            else:
                st.error("Please enter a title")
    with t2:
        kids = students_of(cls)
        hws = q("SELECT * FROM homework WHERE cls=? ORDER BY id DESC", (cls,))
        if not hws:
            st.info("No homework has been given to this class yet")
        for hw in hws:
            subs = q("SELECT * FROM subs WHERE hw=? ORDER BY id", (hw["id"],))
            done = {s["sid"] for s in subs}
            with st.expander(f"{hw['title']} • Submitted {len(done)}/{len(kids)} • Due {hw['due']}"):
                pend = [k["name"] for k in kids if k["id"] not in done]
                if pend:
                    st.warning("Not submitted: " + ", ".join(pend))
                names = {k["id"]: k["name"] for k in kids}
                for s in subs:
                    st.write(f"**{names.get(s['sid'], '-')}** • {s['t']}")
                    show_img(s["path"], width=260)
                if st.button("🗑️ Delete this homework", key=f"dh{hw['id']}"):
                    q("DELETE FROM subs WHERE hw=?", (hw["id"],), commit=True)
                    q("DELETE FROM homework WHERE id=?", (hw["id"],), commit=True)
                    st.rerun()


def my_homework(u):
    hero("📚 My Homework")
    hws = q("SELECT * FROM homework WHERE cls=? ORDER BY id DESC", (u["cls"],))
    if not hws:
        st.info("No homework right now 🎉")
    for hw in hws:
        done = q("SELECT * FROM subs WHERE hw=? AND sid=?", (hw["id"], u["id"]))
        with st.expander(f"{'✅' if done else '⏳'} {hw['title']} • Due {hw['due']}"):
            st.write(hw["body"])
            show_img(hw["img"], width=300)
            if done:
                st.success(f"You submitted this on {done[-1]['t']}")
                show_img(done[-1]["path"], width=220)
            cam = st.toggle("📷 Take a photo with the camera", key=f"t{hw['id']}")
            pic = st.camera_input("Take a photo", key=f"c{hw['id']}") if cam else \
                st.file_uploader("Choose a photo from gallery", type=["jpg", "jpeg", "png"], key=f"f{hw['id']}")
            if pic and st.button("📤 Submit" if not done else "📤 Submit again", key=f"s{hw['id']}", type="primary"):
                ins("INSERT INTO subs(hw,sid,path,t) VALUES(?,?,?,?)",
                    (hw["id"], u["id"], save_file(pic, f"hw{hw['id']}_{u['id']}"), f"{dt.datetime.now():%d-%m-%Y %H:%M}"))
                st.rerun()


# ---------------- Notices ----------------
def notices_view(u, home=False):
    if not home:
        hero("📢 Notices")
    else:
        st.markdown("##### 📢 Latest notices")
    rows = q("SELECT * FROM notices WHERE cls IN ('All',?) ORDER BY id DESC LIMIT ?", (u["cls"], 3 if home else 30))
    if not rows:
        st.caption("No notices")
    for n in rows:
        st.info(f"**{n['d']}** - {n['body']}")


def notice_page(u):
    hero("📢 Notices", "Send a notice to a class or the whole school")
    cls = st.selectbox("Send to", ["All"] + CLASSES)
    body = st.text_area("Write the notice")
    if st.button("📤 Publish", type="primary") and body.strip():
        ins("INSERT INTO notices(cls,body,d) VALUES(?,?,?)", (cls, body.strip(), str(dt.date.today())))
        st.success("Notice sent")
    st.markdown("##### Earlier notices")
    for n in q("SELECT * FROM notices ORDER BY id DESC LIMIT 20"):
        c = st.columns([6, 1])
        c[0].write(f"**{n['d']}** • {n['cls']} - {n['body']}")
        if c[1].button("🗑️", key=f"dn{n['id']}"):
            q("DELETE FROM notices WHERE id=?", (n["id"],), commit=True)
            st.rerun()


# ---------------- Admissions (admin) ----------------
def admissions_admin(u):
    hero("📝 Admission Applications")
    t1, t2 = st.tabs(["⏳ New applications", "📜 Past records"])
    with t1:
        pend = q("SELECT * FROM admissions WHERE status='pending' ORDER BY id")
        if not pend:
            st.info("No new applications")
        for a in pend:
            with st.expander(f"{a['name']} -> {a['cls']} • Txn: {a['txn']}"):
                st.write(f"Parent: {a['parent']}  |  Phone: {a['phone']}  |  Date: {a['d']}")
                show_img(a["proof"], width=260)
                c1, c2 = st.columns(2)
                if c1.button("✅ Approve", key=f"ok{a['id']}", type="primary", use_container_width=True):
                    un, r = add_student(a["name"], a["cls"], None, a["phone"], a["parent"])
                    q("UPDATE admissions SET status='approved' WHERE id=?", (a["id"],), commit=True)
                    st.success(f"Admitted - roll {r} - username: {un} - password: {a['phone']}")
                if c2.button("❌ Reject", key=f"no{a['id']}", use_container_width=True):
                    q("UPDATE admissions SET status='rejected' WHERE id=?", (a["id"],), commit=True)
                    st.rerun()
    with t2:
        rows = q("SELECT d,name,cls,phone,txn,status FROM admissions WHERE status!='pending' ORDER BY id DESC")
        if rows:
            st.dataframe(pd.DataFrame([dict(r) for r in rows]), hide_index=True, use_container_width=True)
        else:
            st.caption("No records")


def password_page(u):
    hero("🔑 Change Password")
    old = st.text_input("Old password", type="password")
    new = st.text_input("New password", type="password")
    if st.button("Change", type="primary"):
        if not q("SELECT 1 FROM users WHERE id=? AND pw=?", (u["id"], h(old))):
            st.error("Old password is wrong")
        elif len(new) < 4:
            st.error("New password must be at least 4 characters")
        else:
            q("UPDATE users SET pw=? WHERE id=?", (h(new), u["id"]), commit=True)
            st.success("Password changed")


# ---------------- Main ----------------
st.set_page_config(page_title=SCHOOL, page_icon="🏫")
st.markdown(CSS, unsafe_allow_html=True)
init()
user = st.session_state.get("user")

if not user:
    hero(f"🏫 {SCHOOL}", "Attendance • Homework • Admission")
    tl, ta = st.tabs(["🔐 Login", "📝 New Admission"])
    with tl:
        login_page()
    with ta:
        admission_page()
else:
    if user["role"] == "student":
        menu = {"🏠 Home": student_home, "📅 My Attendance": my_attendance,
                "📚 Homework": my_homework, "📢 Notices": notices_view}
    else:
        menu = {"🏠 Home": staff_home, "✅ Take Attendance": attendance_page,
                "📒 Monthly Register": register_page, "📊 Report": report_page,
                "🎓 Students": students_page, "📚 Homework": homework_page, "📢 Notices": notice_page}
        if user["role"] == "admin":
            menu["📝 Admissions"] = admissions_admin
            menu["👤 Teachers"] = teachers_page
    menu["🔑 Change Password"] = password_page
    st.sidebar.markdown(f"### 🏫 {SCHOOL}")
    st.sidebar.caption(f"👤 {user['name']} ({user['role']})")
    choice = st.sidebar.radio("Menu", list(menu), label_visibility="collapsed")
    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    menu[choice](user)