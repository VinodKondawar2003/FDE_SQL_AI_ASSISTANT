PRAGMA foreign_keys = ON;
CREATE TABLE departments (
 department_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
);
CREATE TABLE employees (
 employee_id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE, hire_date TEXT NOT NULL,
 department_id INTEGER NOT NULL REFERENCES departments(department_id),
 manager_id INTEGER REFERENCES employees(employee_id),
 salary_cents INTEGER NOT NULL CHECK(salary_cents >= 0)
);
CREATE TABLE customers (
 customer_id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE, city TEXT NOT NULL,
 state TEXT NOT NULL CHECK(length(state)=2), created_at TEXT NOT NULL
);
CREATE TABLE products (
 product_id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
 unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
 active INTEGER NOT NULL CHECK(active IN (0,1))
);
CREATE TABLE orders (
 order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
 employee_id INTEGER REFERENCES employees(employee_id), order_date TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','paid','shipped','cancelled'))
);
CREATE TABLE order_items (
 order_item_id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(order_id),
 product_id INTEGER NOT NULL REFERENCES products(product_id),
 quantity INTEGER NOT NULL CHECK(quantity > 0),
 unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
 UNIQUE(order_id, product_id)
);
CREATE INDEX idx_customers_state ON customers(state);
CREATE INDEX idx_employees_hire_date ON employees(hire_date);
CREATE INDEX idx_employees_department ON employees(department_id);
CREATE INDEX idx_employees_manager ON employees(manager_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_employee ON orders(employee_id);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_items_product ON order_items(product_id);
