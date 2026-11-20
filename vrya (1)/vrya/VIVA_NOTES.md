# VIVA QUICK NOTES

## How to run
    python main.py          (needs only Python 3; creates library.db automatically)
Files: schema.sql (tables, indexes, views) | data.sql (sample data) | queries.sql | main.py

## One-line answers
- **What is the project?** A DBMS for a library handling physical + digital resources, members, issue/return, reservations, fines and analytics.
- **Entities:** Author, Publisher, Category, Resource, Member, Membership_Plan, Transaction, Reservation, Penalty (+ Resource_Author junction).
- **Why Resource_Author table?** Book-Author is many-to-many; junction table with composite PK gives 1NF.
- **Primary key:** uniquely identifies a row (member_id). **Candidate key:** any other unique column (isbn, email). **Foreign key:** links tables (transaction.member_id -> member).
- **Why Membership_Plan separate?** loan_days/fine/max_books depend on plan, not member -> removes transitive dependency (3NF).
- **Normalization:** 1NF atomic values, 2NF no partial dependency, 3NF no transitive dependency.
- **Overdue logic:** return_date IS NULL AND due_date < today.
- **Penalty:** days_late x fine_per_day (plan based), stored in penalty table.
- **View:** saved query (virtual table) - v_overdue, v_popular_resources, v_member_summary.
- **Index:** speeds up search/joins - on member_id, resource_id, due_date. Shown with EXPLAIN QUERY PLAN.
- **CTE:** WITH clause, temporary named result set - used for monthly usage and unpaid dues.
- **Borrowing patterns:** most borrowed resource, category-wise borrows, monthly trend.
- **Digital vs physical?** `type` column; digital resources just have many copies.
- **Why SQLite?** Serverless, zero setup, full SQL support.
- **Future scope:** web UI, email reminders, triggers, recommendation engine.

## Web app (localhost)
    python app.py   ->  open http://localhost:8000
Backend = SQLite (SQL). app.py = Python HTTP server + REST API, index.html = frontend.
Creates library_web.db on first run (delete it to reset the data).

## Showing the database to the teacher
1. In the web app open the **Database** tab: tables, columns, PK/FK, views, indexes, row data, and a read-only SQL console.
2. Or open `library_web.db` in **DB Browser for SQLite** (free: sqlitebrowser.org) -> Browse Data / Database Structure.
3. Or in terminal: `sqlite3 library_web.db` then `.tables`, `.schema`, `SELECT * FROM member;`

## Login system (role based)
| Role  | Username / Password | Can do |
|-------|---------------------|--------|
| Admin | admin / admin123 | Dashboard, catalogue, members, issue/return for anyone, overdue + fines, **Database explorer + SQL console** |
| Member | aman / aman123, riya / riya123, mehta / mehta123, kabir / kabir123 | Browse catalogue, **rent**, **request return**, reserve, see own loans and fines |
- Members can also self-register on the login page (username = email, Student plan).
- Table `user_account` (role CHECK ADMIN/USER, member_id FK). Passwords stored as salted PBKDF2 hashes, not plain text.
- Security: every API checks the session role on the server. A member calling a database URL gets "Access denied"; a member can only request return of their own loans.
- Pages: /login, /admin, /user

## Return verification (two-step return)
**Problem:** if a member could mark a book "returned" by themselves, the system could not know the physical book was still with them.
**Solution:** return is librarian-verified.
1. Member clicks **Request return** -> only `transaction_log.return_requested_on` is set (today's date). `return_date`, `copies_avail` and `penalty` are NOT touched. Status shows "Return requested - waiting for librarian".
2. Admin sees it under **Circulation -> Pending return requests** (and a dashboard counter).
3. Admin clicks **Confirm received** -> `return_date` set, `copies_avail + 1`, penalty row written if late.
   Admin clicks **Reject** -> `return_requested_on` back to NULL, loan stays open, fine keeps growing.
- Fine is counted until the librarian confirms, not until the member clicks (the book is not back until the librarian has it).
- Admin can still use **Mark returned** directly for a normal desk return.
- Old databases are upgraded automatically on start (`migrate()` adds the column).
- **One-line answer:** "Return is a request/approval workflow: the member requests, the librarian verifies the physical book and confirms. Stock and fines change only on confirmation."
- **Demo:** log in as riya -> My loans -> Request return on a book -> log in as admin -> Circulation -> Confirm received (or Reject).
- Show it in SQL: `SELECT txn_id, return_date, return_requested_on FROM transaction_log;`
