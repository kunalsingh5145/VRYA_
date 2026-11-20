"""
Library Management - Web App with Admin & User login | Backend: SQLite (SQL)
Run:  python app.py     then open  http://localhost:8000
Admin: admin / admin123      Users: aman / aman123, riya / riya123, mehta / mehta123, kabir / kabir123
"""
import sqlite3, os, json, hashlib, secrets
from datetime import date, timedelta
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "library_web.db")
TODAY = "2026-11-18"      # matches sample data & v_overdue view
PORT = 8000
SESSIONS = {}             # token -> {username, role, member_id}

# ---------------- security helpers ----------------
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()

def check_pw(pw, stored):
    return secrets.compare_digest(hash_pw(pw, stored.split("$")[0]), stored)

# ---------------- database helpers ----------------
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c

def init_db():
    if os.path.exists(DB):
        return
    c = conn()
    for f in ("schema.sql", "data.sql"):
        c.executescript(open(os.path.join(BASE, f)).read())
    c.execute("INSERT INTO user_account(username,password_hash,role,member_id) VALUES (?,?,?,NULL)",
              ("admin", hash_pw("admin123"), "ADMIN"))
    for mid, uname in [(1, "aman"), (2, "riya"), (3, "mehta"), (4, "kabir")]:
        c.execute("INSERT INTO user_account(username,password_hash,role,member_id) VALUES (?,?,?,?)",
                  (uname, hash_pw(uname + "123"), "USER", mid))
    c.commit(); c.close()

def migrate():
    """Add return_requested_on to databases created before the return-request feature."""
    c = conn()
    cols = [r["name"] for r in c.execute("PRAGMA table_info(transaction_log)")]
    if "return_requested_on" not in cols:
        c.execute("ALTER TABLE transaction_log ADD COLUMN return_requested_on TEXT")
        c.commit()
    c.close()

def q(sql, params=()):
    c = conn()
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close()
    return rows

# ================= ADMIN READ ENDPOINTS =================
GET = {
 "/api/resources": """SELECT r.resource_id, r.title, r.isbn, r.type, p.name AS publisher, c.name AS category,
        COALESCE(GROUP_CONCAT(a.name, ', '), '-') AS authors, r.copies_avail, r.copies_total, r.year
        FROM resource r JOIN publisher p USING(publisher_id) JOIN category c USING(category_id)
        LEFT JOIN resource_author ra USING(resource_id) LEFT JOIN author a USING(author_id)
        GROUP BY r.resource_id ORDER BY r.resource_id""",
 "/api/members": "SELECT * FROM v_member_summary ORDER BY member_id",
 "/api/transactions": """SELECT t.txn_id, m.name AS member, r.title, t.issue_date, t.due_date, t.return_date, t.return_requested_on
        FROM transaction_log t JOIN member m USING(member_id) JOIN resource r USING(resource_id)
        ORDER BY t.txn_id DESC""",
 "/api/overdue": "SELECT * FROM v_overdue ORDER BY days_overdue DESC",
 "/api/popular": "SELECT * FROM v_popular_resources LIMIT 5",
 "/api/monthly": """WITH monthly AS (SELECT substr(issue_date,1,7) AS month, COUNT(*) AS issues
        FROM transaction_log GROUP BY month) SELECT month, issues FROM monthly ORDER BY month""",
 "/api/categories": """SELECT c.name AS category, COUNT(*) AS borrows FROM transaction_log t
        JOIN resource r USING(resource_id) JOIN category c USING(category_id)
        GROUP BY c.name ORDER BY borrows DESC""",
 "/api/dues": """WITH dues AS (SELECT t.member_id, SUM(p.amount) AS owed FROM penalty p
        JOIN transaction_log t USING(txn_id) WHERE p.paid=0 GROUP BY t.member_id)
        SELECT m.name, d.owed FROM dues d JOIN member m USING(member_id)""",
 "/api/reservations": """SELECT res.res_id, m.name AS member, r.title, res.res_date, res.status
        FROM reservation res JOIN member m USING(member_id) JOIN resource r USING(resource_id)
        ORDER BY res.res_id DESC""",
 "/api/plans": "SELECT * FROM membership_plan",
 "/api/fines": """SELECT p.penalty_id, m.name AS member, r.title, p.days_late, p.amount, p.paid
        FROM penalty p JOIN transaction_log t USING(txn_id) JOIN member m USING(member_id)
        JOIN resource r USING(resource_id) ORDER BY p.paid, p.penalty_id DESC""",
 "/api/stats": """SELECT (SELECT COUNT(*) FROM resource) AS resources,
        (SELECT COUNT(*) FROM member) AS members,
        (SELECT COUNT(*) FROM transaction_log WHERE return_date IS NULL) AS on_loan,
        (SELECT COUNT(*) FROM v_overdue) AS overdue,
        (SELECT COUNT(*) FROM transaction_log WHERE return_date IS NULL AND return_requested_on IS NOT NULL) AS pending_returns,
        (SELECT COALESCE(SUM(amount),0) FROM penalty WHERE paid=0) AS unpaid_fines""",
}

# ================= CORE OPERATIONS =================
def issue(d):
    c = conn()
    mid, rid = int(d["member_id"]), int(d["resource_id"])
    r = c.execute("SELECT copies_avail, title FROM resource WHERE resource_id=?", (rid,)).fetchone()
    m = c.execute("""SELECT p.max_books, p.loan_days FROM member m JOIN membership_plan p USING(plan_id)
                     WHERE m.member_id=?""", (mid,)).fetchone()
    if not r or not m: return 404, {"error": "Member or resource not found"}
    if r["copies_avail"] <= 0: return 400, {"error": "No copies available. Reserve it instead."}
    held = c.execute("SELECT COUNT(*) FROM transaction_log WHERE member_id=? AND return_date IS NULL", (mid,)).fetchone()[0]
    if held >= m["max_books"]: return 400, {"error": f"Borrow limit ({m['max_books']}) reached for this plan"}
    dup = c.execute("SELECT 1 FROM transaction_log WHERE member_id=? AND resource_id=? AND return_date IS NULL", (mid, rid)).fetchone()
    if dup: return 400, {"error": "You already have this resource on loan"}
    due = (date.fromisoformat(TODAY) + timedelta(days=m["loan_days"])).isoformat()
    c.execute("INSERT INTO transaction_log(member_id,resource_id,issue_date,due_date) VALUES (?,?,?,?)", (mid, rid, TODAY, due))
    c.execute("UPDATE resource SET copies_avail=copies_avail-1 WHERE resource_id=?", (rid,))
    c.commit(); c.close()
    return 200, {"message": f"Rented '{r['title']}'. Due {due}"}

def give_back(d):
    c = conn()
    t = c.execute("""SELECT t.due_date, t.resource_id, p.fine_per_day FROM transaction_log t
        JOIN member m USING(member_id) JOIN membership_plan p USING(plan_id)
        WHERE t.txn_id=? AND t.return_date IS NULL""", (int(d["txn_id"]),)).fetchone()
    if not t: return 400, {"error": "Invalid or already returned transaction"}
    late = (date.fromisoformat(TODAY) - date.fromisoformat(t["due_date"])).days
    c.execute("UPDATE transaction_log SET return_date=? WHERE txn_id=?", (TODAY, int(d["txn_id"])))
    c.execute("UPDATE resource SET copies_avail=copies_avail+1 WHERE resource_id=?", (t["resource_id"],))
    msg = "Returned on time. No penalty."
    if late > 0:
        amt = late * t["fine_per_day"]
        c.execute("INSERT INTO penalty(txn_id,days_late,amount) VALUES (?,?,?)", (int(d["txn_id"]), late, amt))
        msg = f"Returned {late} days late. Penalty: Rs {amt:.2f}"
    c.commit(); c.close()
    return 200, {"message": msg}

def reserve(d):
    c = conn()
    mid, rid = int(d["member_id"]), int(d["resource_id"])
    if c.execute("SELECT 1 FROM reservation WHERE member_id=? AND resource_id=? AND status='ACTIVE'", (mid, rid)).fetchone():
        return 400, {"error": "You already have an active reservation for this resource"}
    c.execute("INSERT INTO reservation(member_id,resource_id,res_date) VALUES (?,?,?)", (mid, rid, TODAY))
    c.commit(); c.close()
    return 200, {"message": "Reservation placed"}

def pay_fine(d):
    c = conn()
    c.execute("UPDATE penalty SET paid=1 WHERE penalty_id=?", (int(d["penalty_id"]),))
    c.commit(); c.close()
    return 200, {"message": "Fine marked as paid"}

def reject_return(d):
    """Admin: the book never arrived -> cancel the member's request. Loan stays open, fine keeps counting."""
    c = conn()
    cur = c.execute("""UPDATE transaction_log SET return_requested_on=NULL
                       WHERE txn_id=? AND return_date IS NULL AND return_requested_on IS NOT NULL""", (int(d["txn_id"]),))
    n = cur.rowcount
    c.commit(); c.close()
    if not n: return 400, {"error": "No pending return request for this loan"}
    return 200, {"message": "Return request rejected. Loan stays open and the fine keeps counting."}

def make_account(c, username, password, member_id):
    if len(password) < 4: raise ValueError("Password must be at least 4 characters")
    c.execute("INSERT INTO user_account(username,password_hash,role,member_id) VALUES (?,?,?,?)",
              (username, hash_pw(password), "USER", member_id))

def add_member(d):
    c = conn()
    mid = c.execute("INSERT INTO member(name,email,phone,plan_id,join_date) VALUES (?,?,?,?,?)",
              (d["name"], d["email"], d.get("phone", ""), int(d["plan_id"]), TODAY)).lastrowid
    if d.get("username"):
        make_account(c, d["username"].strip().lower(), d.get("password", ""), mid)
    c.commit(); c.close()
    return 200, {"message": "Member added" + (" with login account" if d.get("username") else "")}

def add_resource(d):
    c = conn()
    def get_or_create(table, col, idcol, val):
        row = c.execute(f"SELECT {idcol} FROM {table} WHERE {col}=?", (val,)).fetchone()
        return row[0] if row else c.execute(f"INSERT INTO {table}({col}) VALUES (?)", (val,)).lastrowid
    pid = get_or_create("publisher", "name", "publisher_id", d["publisher"])
    cid = get_or_create("category", "name", "category_id", d["category"])
    n = int(d.get("copies", 1))
    rid = c.execute("""INSERT INTO resource(title,isbn,type,publisher_id,category_id,copies_total,copies_avail,year)
        VALUES (?,?,?,?,?,?,?,?)""", (d["title"], d.get("isbn") or None, d["type"], pid, cid, n, n, d.get("year") or None)).lastrowid
    for name in [a.strip() for a in d.get("authors", "").split(",") if a.strip()]:
        aid = get_or_create("author", "name", "author_id", name)
        c.execute("INSERT OR IGNORE INTO resource_author VALUES (?,?)", (rid, aid))
    c.commit(); c.close()
    return 200, {"message": "Resource added"}

ADMIN_POST = {"/api/issue": issue, "/api/return": give_back, "/api/reject-return": reject_return, "/api/reserve": reserve,
              "/api/members": add_member, "/api/resources": add_resource, "/api/pay": pay_fine}

# ================= USER (MEMBER) ENDPOINTS =================
def user_get(path, mid):
    if path == "/api/u/catalogue":
        return q("""SELECT r.resource_id, r.title, r.type, p.name AS publisher, c.name AS category,
            COALESCE(GROUP_CONCAT(a.name, ', '), '-') AS authors, r.copies_avail, r.copies_total, r.year
            FROM resource r JOIN publisher p USING(publisher_id) JOIN category c USING(category_id)
            LEFT JOIN resource_author ra USING(resource_id) LEFT JOIN author a USING(author_id)
            GROUP BY r.resource_id ORDER BY r.title""")
    if path == "/api/u/loans":
        return q("""SELECT t.txn_id, r.title, r.type, t.issue_date, t.due_date, t.return_date, t.return_requested_on,
            CASE WHEN t.return_date IS NULL AND t.due_date < :today
                 THEN CAST(julianday(:today) - julianday(t.due_date) AS INTEGER) ELSE 0 END AS days_overdue,
            CASE WHEN t.return_date IS NULL AND t.due_date < :today
                 THEN CAST(julianday(:today) - julianday(t.due_date) AS INTEGER) * p.fine_per_day ELSE 0 END AS fine_so_far
            FROM transaction_log t JOIN resource r USING(resource_id)
            JOIN member m ON m.member_id = t.member_id JOIN membership_plan p ON p.plan_id = m.plan_id
            WHERE t.member_id = :mid ORDER BY t.txn_id DESC""", {"today": TODAY, "mid": mid})
    if path == "/api/u/reservations":
        return q("""SELECT res.res_id, r.title, res.res_date, res.status FROM reservation res
            JOIN resource r USING(resource_id) WHERE res.member_id=? ORDER BY res.res_id DESC""", (mid,))
    if path == "/api/u/fines":
        return q("""SELECT p.penalty_id, r.title, p.days_late, p.amount, p.paid FROM penalty p
            JOIN transaction_log t USING(txn_id) JOIN resource r USING(resource_id)
            WHERE t.member_id=? ORDER BY p.penalty_id DESC""", (mid,))
    if path == "/api/u/profile":
        return q("""SELECT m.name, m.email, m.join_date, pl.plan_name, pl.max_books, pl.loan_days, pl.fine_per_day,
            (SELECT COUNT(*) FROM transaction_log WHERE member_id=m.member_id AND return_date IS NULL) AS holding,
            (SELECT COALESCE(SUM(p.amount),0) FROM penalty p JOIN transaction_log t USING(txn_id)
              WHERE t.member_id=m.member_id AND p.paid=0) AS unpaid
            FROM member m JOIN membership_plan pl USING(plan_id) WHERE m.member_id=?""", (mid,))[0]
    return None

def request_return(d, mid):
    """Member side only RECORDS a request. Stock, return_date and penalty change only when the
    librarian confirms (give_back via /api/return), because only the librarian can see the physical book."""
    c = conn()
    t = c.execute("SELECT member_id, return_date, return_requested_on FROM transaction_log WHERE txn_id=?",
                  (int(d["txn_id"]),)).fetchone()
    if not t or t["member_id"] != mid:
        c.close(); return 403, {"error": "This is not your loan"}
    if t["return_date"]:
        c.close(); return 400, {"error": "Already returned"}
    if t["return_requested_on"]:
        c.close(); return 400, {"error": "Return already requested - waiting for the librarian"}
    c.execute("UPDATE transaction_log SET return_requested_on=? WHERE txn_id=?", (TODAY, int(d["txn_id"])))
    c.commit(); c.close()
    return 200, {"message": "Return requested. Hand the book to the librarian - it counts as returned only after they confirm."}

# ================= ADMIN-ONLY DATABASE EXPLORER (read-only) =================
def ro_conn():
    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c

def db_objects():
    c = ro_conn()
    out = []
    for o in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 1 WHEN 'view' THEN 2 ELSE 3 END, name").fetchall():
        item = dict(o)
        if o["type"] in ("table", "view"):
            item["rows"] = c.execute(f'SELECT COUNT(*) FROM "{o["name"]}"').fetchone()[0]
            item["columns"] = [dict(r) for r in c.execute(f'PRAGMA table_info("{o["name"]}")')]
            if o["type"] == "table":
                item["fks"] = [dict(r) for r in c.execute(f'PRAGMA foreign_key_list("{o["name"]}")')]
        out.append(item)
    c.close()
    return out

def run_query(sql):
    s = sql.strip().rstrip(";")
    if ";" in s: raise ValueError("Run one statement at a time")
    if s.split()[0].upper() not in ("SELECT", "WITH", "PRAGMA", "EXPLAIN"):
        raise ValueError("Read-only console: use SELECT / WITH / PRAGMA / EXPLAIN")
    c = ro_conn()
    cur = c.execute(s)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = [list(r) for r in cur.fetchmany(500)]
    c.close()
    return {"columns": cols, "rows": rows}

# ================= HTTP SERVER =================
def home(s): return "/admin" if s["role"] == "ADMIN" else "/user"

class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json", headers=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, to):
        self.send_response(302); self.send_header("Location", to); self.send_header("Content-Length", "0"); self.end_headers()

    def page(self, name):
        self.send(200, open(os.path.join(BASE, name), "rb").read(), "text/html; charset=utf-8", {"Cache-Control": "no-store"})

    def session(self):
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sid": return SESSIONS.get(v)
        return None

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")

    def need(self, s, role):
        """returns True if allowed, otherwise sends 401/403 and returns False"""
        if not s: self.send(401, {"error": "Please log in"}); return False
        if s["role"] != role: self.send(403, {"error": "Access denied for your role"}); return False
        return True

    def do_GET(self):
        u = urlparse(self.path); path = u.path; s = self.session()
        if path == "/": return self.redirect(home(s) if s else "/login")
        if path == "/login": return self.redirect(home(s)) if s else self.page("login.html")
        if path == "/admin": return self.page("admin.html") if s and s["role"] == "ADMIN" else self.redirect("/login")
        if path == "/user":  return self.page("user.html") if s and s["role"] == "USER" else self.redirect("/login")
        if path == "/api/me":
            return self.send(200, s) if s else self.send(401, {"error": "Please log in"})
        try:
            if path.startswith("/api/u/"):
                if not self.need(s, "USER"): return
                res = user_get(path, s["member_id"])
                return self.send(200, res) if res is not None else self.send(404, {"error": "not found"})
            if path in GET:
                if not self.need(s, "ADMIN"): return
                return self.send(200, q(GET[path]))
            if path == "/api/db/objects":
                if not self.need(s, "ADMIN"): return
                return self.send(200, db_objects())
            if path == "/api/db/table":
                if not self.need(s, "ADMIN"): return
                name = parse_qs(u.query).get("name", [""])[0]
                if name not in [o["name"] for o in db_objects() if o["type"] in ("table", "view")]:
                    return self.send(404, {"error": "unknown table"})
                return self.send(200, run_query(f'SELECT * FROM "{name}"'))
        except Exception as e:
            return self.send(500, {"error": str(e)})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        s = self.session(); p = self.path
        try:
            if p == "/api/login":
                d = self.body()
                rows = q("""SELECT u.username,u.password_hash,u.role,u.member_id,COALESCE(m.name,'Administrator') AS name
                            FROM user_account u LEFT JOIN member m USING(member_id) WHERE u.username=?""",
                         (str(d.get("username", "")).strip().lower(),))
                if not rows or not check_pw(str(d.get("password", "")), rows[0]["password_hash"]):
                    return self.send(401, {"error": "Wrong username or password"})
                r = rows[0]; tok = secrets.token_hex(24)
                SESSIONS[tok] = {"username": r["username"], "role": r["role"], "member_id": r["member_id"], "name": r["name"]}
                return self.send(200, {"redirect": home(SESSIONS[tok])},
                                 headers={"Set-Cookie": f"sid={tok}; Path=/; HttpOnly; SameSite=Strict"})
            if p == "/api/register":
                d = self.body()
                c = conn()
                name, email = d["name"].strip(), d["email"].strip().lower()
                if not name or not email: return self.send(400, {"error": "Name and email are required"})
                mid = c.execute("INSERT INTO member(name,email,phone,plan_id,join_date) VALUES (?,?,?,1,?)",
                                (name, email, d.get("phone", ""), TODAY)).lastrowid
                make_account(c, email, d.get("password", ""), mid)
                c.commit(); c.close()
                tok = secrets.token_hex(24)
                SESSIONS[tok] = {"username": email, "role": "USER", "member_id": mid, "name": name}
                return self.send(200, {"redirect": "/user"},
                                 headers={"Set-Cookie": f"sid={tok}; Path=/; HttpOnly; SameSite=Strict"})
            if p == "/api/logout":
                for part in self.headers.get("Cookie", "").split(";"):
                    k, _, v = part.strip().partition("=")
                    if k == "sid": SESSIONS.pop(v, None)
                return self.send(200, {"redirect": "/login"}, headers={"Set-Cookie": "sid=; Path=/; Max-Age=0"})

            # ---- user actions (always on the logged-in user's own account) ----
            if p in ("/api/u/rent", "/api/u/reserve", "/api/u/return-request"):
                if not self.need(s, "USER"): return
                d = self.body(); mid = s["member_id"]
                if p == "/api/u/rent":    code, res = issue({"member_id": mid, "resource_id": d["resource_id"]})
                elif p == "/api/u/reserve": code, res = reserve({"member_id": mid, "resource_id": d["resource_id"]})
                else:                      code, res = request_return(d, mid)
                return self.send(code, res)

            # ---- admin actions ----
            if p == "/api/db/query":
                if not self.need(s, "ADMIN"): return
                return self.send(200, run_query(self.body().get("sql", "")))
            if p in ADMIN_POST:
                if not self.need(s, "ADMIN"): return
                code, res = ADMIN_POST[p](self.body())
                return self.send(code, res)
            self.send(404, {"error": "not found"})
        except sqlite3.IntegrityError as e:
            self.send(400, {"error": "Already exists or invalid data (" + str(e).split(":")[-1].strip() + ")"})
        except Exception as e:
            self.send(400, {"error": str(e)})

    def log_message(self, *a): pass

if __name__ == "__main__":
    init_db()
    migrate()
    print(f"Library app running -> http://localhost:{PORT}   (Ctrl+C to stop)")
    print("Admin login: admin / admin123   |   User login: aman / aman123")
    ThreadingHTTPServer(("localhost", PORT), H).serve_forever()
