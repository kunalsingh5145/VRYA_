-- Intelligent Library & Digital Resource Management System (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE publisher (
    publisher_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    city         TEXT
);
CREATE TABLE author (
    author_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    country   TEXT
);
CREATE TABLE category (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE
);
-- Resource = physical book OR digital resource (e-book, journal, video)
CREATE TABLE resource (
    resource_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    isbn         TEXT UNIQUE,                      -- candidate key
    type         TEXT NOT NULL CHECK (type IN ('PHYSICAL','DIGITAL')),
    publisher_id INTEGER NOT NULL REFERENCES publisher(publisher_id),
    category_id  INTEGER NOT NULL REFERENCES category(category_id),
    copies_total INTEGER NOT NULL DEFAULT 1 CHECK (copies_total >= 0),
    copies_avail INTEGER NOT NULL DEFAULT 1 CHECK (copies_avail >= 0),
    year         INTEGER
);
-- M:N between resource and author
CREATE TABLE resource_author (
    resource_id INTEGER REFERENCES resource(resource_id) ON DELETE CASCADE,
    author_id   INTEGER REFERENCES author(author_id),
    PRIMARY KEY (resource_id, author_id)
);
CREATE TABLE membership_plan (
    plan_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name   TEXT NOT NULL UNIQUE,              -- Student / Faculty / Premium
    max_books   INTEGER NOT NULL,
    loan_days   INTEGER NOT NULL,
    fine_per_day REAL NOT NULL
);
CREATE TABLE member (
    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    email     TEXT NOT NULL UNIQUE,                -- candidate key
    phone     TEXT,
    plan_id   INTEGER NOT NULL REFERENCES membership_plan(plan_id),
    join_date TEXT NOT NULL
);
CREATE TABLE transaction_log (                     -- book circulation
    txn_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER NOT NULL REFERENCES member(member_id),
    resource_id INTEGER NOT NULL REFERENCES resource(resource_id),
    issue_date  TEXT NOT NULL,
    due_date    TEXT NOT NULL,
    return_date TEXT,                              -- NULL = not yet returned (set ONLY when the librarian confirms)
    return_requested_on TEXT                       -- member clicked 'Request return'; NULL = no pending request
);
CREATE TABLE reservation (
    res_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER NOT NULL REFERENCES member(member_id),
    resource_id INTEGER NOT NULL REFERENCES resource(resource_id),
    res_date    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','FULFILLED','CANCELLED'))
);
CREATE TABLE penalty (
    penalty_id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id     INTEGER NOT NULL UNIQUE REFERENCES transaction_log(txn_id),
    days_late  INTEGER NOT NULL,
    amount     REAL NOT NULL,
    paid       INTEGER NOT NULL DEFAULT 0
);

-- INDEXES
CREATE INDEX idx_txn_member   ON transaction_log(member_id);
CREATE INDEX idx_txn_resource ON transaction_log(resource_id);
CREATE INDEX idx_txn_due      ON transaction_log(due_date, return_date);
CREATE INDEX idx_resource_title ON resource(title);

-- VIEWS
CREATE VIEW v_overdue AS
SELECT t.txn_id, m.name AS member, r.title, t.due_date,
       CAST(julianday('2026-11-18') - julianday(t.due_date) AS INTEGER) AS days_overdue,
       CAST(julianday('2026-11-18') - julianday(t.due_date) AS INTEGER) * p.fine_per_day AS fine_so_far
FROM transaction_log t
JOIN member m ON m.member_id = t.member_id
JOIN resource r ON r.resource_id = t.resource_id
JOIN membership_plan p ON p.plan_id = m.plan_id
WHERE t.return_date IS NULL AND t.due_date < '2026-11-18';

CREATE VIEW v_popular_resources AS
SELECT r.resource_id, r.title, r.type, COUNT(t.txn_id) AS times_borrowed
FROM resource r LEFT JOIN transaction_log t ON t.resource_id = r.resource_id
GROUP BY r.resource_id ORDER BY times_borrowed DESC;

CREATE VIEW v_member_summary AS
SELECT m.member_id, m.name, pl.plan_name,
       COUNT(t.txn_id) AS total_borrowed,
       SUM(CASE WHEN t.return_date IS NULL THEN 1 ELSE 0 END) AS currently_holding
FROM member m
JOIN membership_plan pl ON pl.plan_id = m.plan_id
LEFT JOIN transaction_log t ON t.member_id = m.member_id
GROUP BY m.member_id;

-- LOGIN ACCOUNTS (role based: ADMIN / USER). Passwords are stored hashed (PBKDF2), never as plain text.
CREATE TABLE user_account (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('ADMIN','USER')),
    member_id     INTEGER UNIQUE REFERENCES member(member_id)   -- NULL for admin
);
