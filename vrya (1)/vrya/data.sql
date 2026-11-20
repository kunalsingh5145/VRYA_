INSERT INTO publisher(name,city) VALUES ('Pearson','London'),('McGraw-Hill','New York'),('O''Reilly','Sebastopol'),('Penguin','London');
INSERT INTO author(name,country) VALUES ('Silberschatz','USA'),('Korth','USA'),('Ramez Elmasri','USA'),('Martin Fowler','UK'),('George Orwell','UK'),('Yuval Harari','Israel');
INSERT INTO category(name) VALUES ('Computer Science'),('Fiction'),('History'),('Journal');
INSERT INTO resource(title,isbn,type,publisher_id,category_id,copies_total,copies_avail,year) VALUES
('Database System Concepts','9780078022159','PHYSICAL',2,1,5,3,2019),
('Fundamentals of Database Systems','9780133970777','PHYSICAL',1,1,4,3,2016),
('Refactoring','9780134757599','DIGITAL',3,1,10,9,2018),
('1984','9780451524935','PHYSICAL',4,2,3,2,1949),
('Sapiens','9780062316097','PHYSICAL',4,3,3,3,2015),
('IEEE Data Engineering Journal','9781000000001','DIGITAL',3,4,99,98,2024);
INSERT INTO resource_author VALUES (1,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,2);
INSERT INTO membership_plan(plan_name,max_books,loan_days,fine_per_day) VALUES ('Student',3,14,2.0),('Faculty',6,30,1.0),('Premium',10,45,0.5);
INSERT INTO member(name,email,phone,plan_id,join_date) VALUES
('Aman Verma','aman@mail.com','9876500001',1,'2025-07-01'),
('Riya Sharma','riya@mail.com','9876500002',1,'2025-08-15'),
('Dr. Mehta','mehta@mail.com','9876500003',2,'2024-01-10'),
('Kabir Singh','kabir@mail.com','9876500004',3,'2026-01-05');
INSERT INTO transaction_log(member_id,resource_id,issue_date,due_date,return_date) VALUES
(1,1,'2026-09-01','2026-09-15','2026-09-20'),
(1,4,'2026-10-01','2026-10-15',NULL),
(2,1,'2026-10-05','2026-10-19','2026-10-18'),
(2,3,'2026-11-01','2026-11-15',NULL),
(3,1,'2026-10-20','2026-11-19',NULL),
(3,2,'2026-10-25','2026-11-24',NULL),
(4,4,'2026-09-10','2026-10-25','2026-10-30'),
(4,6,'2026-11-10','2026-12-25',NULL),
(1,1,'2026-08-01','2026-08-15','2026-08-14'),
(2,5,'2026-11-05','2026-11-19',NULL);
INSERT INTO reservation(member_id,resource_id,res_date,status) VALUES (2,4,'2026-11-10','ACTIVE'),(4,1,'2026-11-12','ACTIVE');
INSERT INTO penalty(txn_id,days_late,amount,paid) VALUES (1,5,10.0,1),(7,5,2.5,0);
