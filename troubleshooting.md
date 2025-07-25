- OpenPLC db destructing after closing. Corrupting the openplc.db file.
-   Create Database:
-   ```bash
-     ~/OpenPLC_v3/webserver/core
-     sqlite3 openplc.db

- Inside SQlite prompt paste:
```` SQL
CREATE TABLE programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    code TEXT,
    language TEXT
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT
);

INSERT INTO users (username, password) VALUES ('admin', 'admin');
.quit

