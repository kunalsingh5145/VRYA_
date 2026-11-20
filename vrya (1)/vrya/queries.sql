-- Q1 Overdue books (not returned, past due date)
SELECT * FROM v_overdue;

-- Q2 Frequently borrowed resources
SELECT * FROM v_popular_resources LIMIT 5;

-- Q3 CTE: monthly usage analytics
WITH monthly AS (
  SELECT substr(issue_date,1,7) AS month, COUNT(*) AS issues
  FROM transaction_log GROUP BY month
)
SELECT month, issues FROM monthly ORDER BY month;

-- Q4 CTE: members with unpaid penalties + total owed
WITH dues AS (
  SELECT t.member_id, SUM(p.amount) AS owed
  FROM penalty p JOIN transaction_log t ON t.txn_id = p.txn_id
  WHERE p.paid = 0 GROUP BY t.member_id
)
SELECT m.name, d.owed FROM dues d JOIN member m USING(member_id);

-- Q5 Borrowing pattern by category
SELECT c.name AS category, COUNT(*) AS borrows
FROM transaction_log t JOIN resource r USING(resource_id)
JOIN category c USING(category_id) GROUP BY c.name ORDER BY borrows DESC;

-- Q6 Late returns (returned after due date)
SELECT m.name, r.title, t.due_date, t.return_date
FROM transaction_log t JOIN member m USING(member_id) JOIN resource r USING(resource_id)
WHERE t.return_date > t.due_date;
