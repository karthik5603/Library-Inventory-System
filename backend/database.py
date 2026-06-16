import sqlite3
from pathlib import Path
from contextlib import contextmanager
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "library.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'librarian', 'member')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT UNIQUE,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                genre TEXT,
                publication_year INTEGER,
                total_copies INTEGER NOT NULL CHECK(total_copies >= 0),
                available_copies INTEGER NOT NULL CHECK(available_copies >= 0),
                added_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (added_by) REFERENCES users(id),
                CHECK(available_copies <= total_copies)
            );

            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                loaned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                due_date TEXT NOT NULL,
                returned_at TEXT,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active', 'returned')),
                FOREIGN KEY (book_id) REFERENCES books(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
            CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
            CREATE INDEX IF NOT EXISTS idx_books_genre ON books(genre);
            CREATE INDEX IF NOT EXISTS idx_loans_user ON loans(user_id);
            CREATE INDEX IF NOT EXISTS idx_loans_book ON loans(book_id);
            """
        )


def seed_data():
    with db_session() as conn:
        existing_users = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]

        if existing_users == 0:
            users = [
                ("admin", generate_password_hash("admin123"), "admin"),
                ("librarian1", generate_password_hash("lib123"), "librarian"),
                ("member1", generate_password_hash("member123"), "member"),
            ]

            conn.executemany(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                users,
            )

        existing_books = conn.execute("SELECT COUNT(*) AS count FROM books").fetchone()["count"]

        if existing_books == 0:
            books = [
                ("9780262033848", "Introduction to Algorithms", "Thomas H. Cormen", "Computer Science", 2009, 3, 3, 1),
                ("9780131103627", "The C Programming Language", "Brian Kernighan", "Programming", 1988, 2, 2, 1),
                ("9780132350884", "Clean Code", "Robert C. Martin", "Software Engineering", 2008, 4, 4, 2),
                ("9780596007126", "Head First Design Patterns", "Eric Freeman", "Software Engineering", 2004, 2, 2, 2),
                ("9780134685991", "Effective Java", "Joshua Bloch", "Programming", 2018, 3, 3, 2),
            ]

            conn.executemany(
                """
                INSERT INTO books 
                (isbn, title, author, genre, publication_year, total_copies, available_copies, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                books,
            )


def setup_database():
    init_db()
    seed_data()


if __name__ == "__main__":
    setup_database()
    print("Database initialized successfully.")