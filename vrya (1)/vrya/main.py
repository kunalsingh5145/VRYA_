"""
Intelligent Library & Digital Resource Management System
DBMS Capstone - Python + SQLite (no installation needed: python main.py)
"""
import sqlite3, os
from datetime import date, timedelta

DB = "library.db"
TODAY = "2026-11-18"          # fixed 'today' so demo output is reproducible

def run_script(conn, path):
    with open(path) as f:
        conn.executescript(f.read())

def setup():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    run_script(conn, "schema.sql")
    run_script(conn, "data.sql")
    conn.commit()
    return conn

def show(conn, title, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print(f"\n=== {title} ===")
    print(" | ".join(cols))
    print("-" * 70)
    for r in rows:
        print(" | ".join(str(x) for x in r))
    if not rows:
        print("(no rows)")

# ---------- Operations ----------
def issue_book(conn, member_id, resource_id):
    cur = conn.cursor()
    avail = cur.execute("SELECT copies_avail FROM resource WHERE resource_id=?", (resource_id,)).fetchone()
    if not avail or avail[0] <= 0:
        print("Not available - you can reserve it.")
        return
    plan = cur.execute("""SELECT p.max_books, p.loan_days FROM member m
                          JOIN membership_plan p USING(plan_id) WHERE m.member_id=?""", (member_id,)).fetchone()
    held = cur.execute("SELECT COUNT(*) FROM transaction_log WHERE member_id=? AND return_date IS NULL",
                       (member_id,)).fetchone()[0]
    if held >= plan[0]:
        print("Borrow limit reached for this membership plan.")
        return
    due = (date.fromisoformat(TODAY) + timedelta(days=plan[1])).isoformat()
    cur.execute("INSERT INTO transaction_log(member_id,resource_id,issue_date,due_date) VALUES (?,?,?,?)",
                (member_id, resource_id, TODAY, due))
    cur.execute("UPDATE resource SET copies_avail=copies_avail-1 WHERE resource_id=?", (resource_id,))
    conn.commit()
    print(f"Issued. Due date: {due}")

def return_book(conn, txn_id):
    cur = conn.cursor()
    t = cur.execute("""SELECT t.due_date, t.resource_id, p.fine_per_day FROM transaction_log t
                       JOIN member m USING(member_id) JOIN membership_plan p USING(plan_id)
                       WHERE t.txn_id=? AND t.return_date IS NULL""", (txn_id,)).fetchone()
    if not t:
        print("Invalid / already returned transaction.")
        return
    due, rid, fine = t
    late = (date.fromisoformat(TODAY) - date.fromisoformat(due)).days
    cur.execute("UPDATE transaction_log SET return_date=? WHERE txn_id=?", (TODAY, txn_id))
    cur.execute("UPDATE resource SET copies_avail=copies_avail+1 WHERE resource_id=?", (rid,))
    if late > 0:
        cur.execute("INSERT INTO penalty(txn_id,days_late,amount) VALUES (?,?,?)", (txn_id, late, late * fine))
        print(f"Returned LATE by {late} days. Penalty = Rs {late * fine}")
    else:
        print("Returned on time. No penalty.")
    conn.commit()

def reserve(conn, member_id, resource_id):
    conn.execute("INSERT INTO reservation(member_id,resource_id,res_date) VALUES (?,?,?)",
                 (member_id, resource_id, TODAY))
    conn.commit()
    print("Reservation placed.")

# ---------- Analytics ----------
def analytics(conn):
    show(conn, "Resources (inventory)", """
        SELECT r.resource_id, r.title, r.type, p.name AS publisher, r.copies_avail||'/'||r.copies_total AS avail
        FROM resource r JOIN publisher p USING(publisher_id)""")
    show(conn, "Q1 OVERDUE BOOKS (view v_overdue)", "SELECT * FROM v_overdue")
    show(conn, "Q2 FREQUENTLY BORROWED (view v_popular_resources)", "SELECT * FROM v_popular_resources LIMIT 5")
    show(conn, "Q3 MONTHLY USAGE (CTE)", """
        WITH monthly AS (SELECT substr(issue_date,1,7) AS month, COUNT(*) AS issues
                         FROM transaction_log GROUP BY month)
        SELECT month, issues FROM monthly ORDER BY month""")
    show(conn, "Q4 UNPAID PENALTIES PER MEMBER (CTE)", """
        WITH dues AS (SELECT t.member_id, SUM(p.amount) AS owed
                      FROM penalty p JOIN transaction_log t USING(txn_id)
                      WHERE p.paid=0 GROUP BY t.member_id)
        SELECT m.name, d.owed FROM dues d JOIN member m USING(member_id)""")
    show(conn, "Q5 BORROWING PATTERN BY CATEGORY", """
        SELECT c.name AS category, COUNT(*) AS borrows
        FROM transaction_log t JOIN resource r USING(resource_id) JOIN category c USING(category_id)
        GROUP BY c.name ORDER BY borrows DESC""")
    show(conn, "Q6 MEMBER SUMMARY (view v_member_summary)", "SELECT * FROM v_member_summary")
    show(conn, "Q7 ACTIVE RESERVATIONS", """
        SELECT m.name, r.title, res.res_date FROM reservation res
        JOIN member m USING(member_id) JOIN resource r USING(resource_id) WHERE status='ACTIVE'""")
    show(conn, "INDEX USED? (EXPLAIN QUERY PLAN)",
         "EXPLAIN QUERY PLAN SELECT * FROM transaction_log WHERE member_id = 1")

def menu(conn):
    while True:
        print("""
===== LIBRARY MANAGEMENT SYSTEM =====
1. Issue resource      2. Return resource    3. Reserve resource
4. Full analytics      5. Overdue list       6. Popular resources
0. Exit""")
        ch = input("Choice: ").strip()
        if ch == "1":
            issue_book(conn, int(input("Member ID: ")), int(input("Resource ID: ")))
        elif ch == "2":
            return_book(conn, int(input("Transaction ID: ")))
        elif ch == "3":
            reserve(conn, int(input("Member ID: ")), int(input("Resource ID: ")))
        elif ch == "4":
            analytics(conn)
        elif ch == "5":
            show(conn, "OVERDUE", "SELECT * FROM v_overdue")
        elif ch == "6":
            show(conn, "POPULAR", "SELECT * FROM v_popular_resources")
        elif ch == "0":
            break

if __name__ == "__main__":
    conn = setup()
    print("Database created with sample data.")
    analytics(conn)
    print("\n--- Demo: issue & return ---")
    issue_book(conn, 2, 5)
    return_book(conn, 2)       # txn 2 is overdue -> penalty
    if input("\nOpen interactive menu? (y/n): ").lower() == "y":
        menu(conn)
    conn.close()
