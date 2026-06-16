from datetime import date, timedelta
import sqlite3

from flask import Flask, jsonify, request, g, render_template
try:
    from .database import setup_database, db_session
    from .models import (
        create_user,
        authenticate_user,
        list_users,
        get_user_by_id,
        update_user_role,
        delete_user,
        create_book,
        get_book_by_id,
        list_books,
        update_book,
        delete_book,
        create_loan,
        list_loans,
        return_loan,
        get_stats,
    )
    from .auth import generate_token, login_required, role_required
except ImportError:
    from database import setup_database, db_session
    from models import (
        create_user,
        authenticate_user,
        list_users,
        get_user_by_id,
        update_user_role,
        delete_user,
        create_book,
        get_book_by_id,
        list_books,
        update_book,
        delete_book,
        create_loan,
        list_loans,
        return_loan,
        get_stats,
    )
    from auth import generate_token, login_required, role_required


app = Flask(__name__)


# -------------------------
# Helper functions
# -------------------------

def success_response(data=None, message="success", status_code=200):
    response = {
        "status": "success",
        "message": message,
    }

    if data is not None:
        response["data"] = data

    return jsonify(response), status_code


def error_response(message, status_code=400):
    return jsonify({
        "status": "error",
        "message": message
    }), status_code


def get_request_data():
    data = request.get_json(silent=True)

    if data is None:
        return {}

    return data


def parse_bool(value):
    if value is None:
        return False

    return str(value).lower() in ["true", "1", "yes", "y"]


# -------------------------
# Home route
# -------------------------

@app.route("/")
def home():
    return success_response({
        "project": "Library Inventory System",
        "description": "Database-backed CRUD REST API with search, filtering, roles, and SQLite",
        "endpoints": {
            "auth": ["/api/auth/login", "/api/auth/register"],
            "books": ["/api/books", "/api/books/<id>"],
            "loans": ["/api/loans", "/api/loans/mine"],
            "users": ["/api/users"],
            "stats": ["/api/stats"]
        }
    })


@app.route("/ui")
def ui():
    return render_template("index.html")

# -------------------------
# Auth routes
# -------------------------

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = get_request_data()

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return error_response("username and password are required", 400)

    try:
        with db_session() as conn:
            user = create_user(conn, username=username, password=password, role="member")

        return success_response(user, "User registered successfully", 201)

    except sqlite3.IntegrityError:
        return error_response("Username already exists", 409)

    except Exception as error:
        return error_response(str(error), 500)


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = get_request_data()

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return error_response("username and password are required", 400)

    with db_session() as conn:
        user = authenticate_user(conn, username, password)

    if user is None:
        return error_response("Invalid username or password", 401)

    token = generate_token(user)

    return success_response({
        "user": user,
        "token": token
    }, "Login successful")


# -------------------------
# Book routes
# -------------------------

@app.route("/api/books", methods=["GET"])
def get_books():
    search = request.args.get("search")
    genre = request.args.get("genre")
    author = request.args.get("author")
    available_only = parse_bool(request.args.get("available"))
    sort_by = request.args.get("sort", "title")

    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
    except ValueError:
        return error_response("page and limit must be numbers", 400)

    if page < 1:
        page = 1

    if limit < 1:
        limit = 10

    with db_session() as conn:
        books = list_books(
            conn,
            search=search,
            genre=genre,
            author=author,
            available_only=available_only,
            sort_by=sort_by,
            page=page,
            limit=limit,
        )

    return success_response({
        "books": books,
        "page": page,
        "limit": limit,
        "count": len(books)
    })


@app.route("/api/books/<int:book_id>", methods=["GET"])
def get_single_book(book_id):
    with db_session() as conn:
        book = get_book_by_id(conn, book_id)

    if book is None:
        return error_response("Book not found", 404)

    return success_response(book)


@app.route("/api/books", methods=["POST"])
@role_required("admin", "librarian")
def add_book():
    data = get_request_data()

    title = data.get("title")
    author = data.get("author")

    if not title or not author:
        return error_response("title and author are required", 400)

    try:
        total_copies = int(data.get("total_copies", 1))
    except ValueError:
        return error_response("total_copies must be a number", 400)

    try:
        with db_session() as conn:
            book = create_book(
                conn,
                isbn=data.get("isbn"),
                title=title,
                author=author,
                genre=data.get("genre"),
                publication_year=data.get("publication_year"),
                total_copies=total_copies,
                added_by=g.current_user["user_id"],
            )

        return success_response(book, "Book created successfully", 201)

    except sqlite3.IntegrityError:
        return error_response("ISBN already exists or invalid data", 409)

    except ValueError as error:
        return error_response(str(error), 400)

    except Exception as error:
        return error_response(str(error), 500)


@app.route("/api/books/<int:book_id>", methods=["PUT"])
@role_required("admin", "librarian")
def edit_book(book_id):
    data = get_request_data()

    try:
        with db_session() as conn:
            book = update_book(conn, book_id, data)

        if book is None:
            return error_response("Book not found", 404)

        return success_response(book, "Book updated successfully")

    except sqlite3.IntegrityError:
        return error_response("Invalid update. Check ISBN or copy values.", 409)

    except ValueError as error:
        return error_response(str(error), 400)

    except Exception as error:
        return error_response(str(error), 500)


@app.route("/api/books/<int:book_id>", methods=["DELETE"])
@role_required("admin")
def remove_book(book_id):
    try:
        with db_session() as conn:
            deleted = delete_book(conn, book_id)

        if not deleted:
            return error_response("Book not found", 404)

        return success_response(message="Book deleted successfully")

    except ValueError as error:
        return error_response(str(error), 400)

    except Exception as error:
        return error_response(str(error), 500)


# -------------------------
# Loan routes
# -------------------------

@app.route("/api/loans", methods=["POST"])
@login_required
def borrow_book():
    data = get_request_data()

    book_id = data.get("book_id")

    if not book_id:
        return error_response("book_id is required", 400)

    due_date = data.get("due_date")

    if not due_date:
        due_date = str(date.today() + timedelta(days=14))

    try:
        with db_session() as conn:
            loan = create_loan(
                conn,
                book_id=int(book_id),
                user_id=g.current_user["user_id"],
                due_date=due_date,
            )

        return success_response(loan, "Book borrowed successfully", 201)

    except ValueError as error:
        return error_response(str(error), 400)

    except Exception as error:
        return error_response(str(error), 500)


@app.route("/api/loans", methods=["GET"])
@role_required("admin", "librarian")
def get_all_loans():
    active_only = parse_bool(request.args.get("active"))

    with db_session() as conn:
        loans = list_loans(conn, active_only=active_only)

    return success_response({
        "loans": loans,
        "count": len(loans)
    })


@app.route("/api/loans/mine", methods=["GET"])
@login_required
def get_my_loans():
    active_only = parse_bool(request.args.get("active"))

    with db_session() as conn:
        loans = list_loans(
            conn,
            user_id=g.current_user["user_id"],
            active_only=active_only,
        )

    return success_response({
        "loans": loans,
        "count": len(loans)
    })


@app.route("/api/loans/<int:loan_id>/return", methods=["PATCH"])
@role_required("admin", "librarian")
def mark_loan_returned(loan_id):
    try:
        with db_session() as conn:
            loan = return_loan(conn, loan_id)

        if loan is None:
            return error_response("Loan not found", 404)

        return success_response(loan, "Book returned successfully")

    except ValueError as error:
        return error_response(str(error), 400)

    except Exception as error:
        return error_response(str(error), 500)


# -------------------------
# User routes
# -------------------------

@app.route("/api/users", methods=["GET"])
@role_required("admin")
def get_users():
    with db_session() as conn:
        users = list_users(conn)

    return success_response({
        "users": users,
        "count": len(users)
    })


@app.route("/api/users/<int:user_id>", methods=["GET"])
@role_required("admin")
def get_single_user(user_id):
    with db_session() as conn:
        user = get_user_by_id(conn, user_id)

    if user is None:
        return error_response("User not found", 404)

    return success_response(user)


@app.route("/api/users/<int:user_id>/role", methods=["PATCH"])
@role_required("admin")
def change_user_role(user_id):
    data = get_request_data()
    new_role = data.get("role")

    if not new_role:
        return error_response("role is required", 400)

    try:
        with db_session() as conn:
            user = update_user_role(conn, user_id, new_role)

        if user is None:
            return error_response("User not found", 404)

        return success_response(user, "User role updated successfully")

    except ValueError as error:
        return error_response(str(error), 400)

    except Exception as error:
        return error_response(str(error), 500)


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@role_required("admin")
def remove_user(user_id):
    try:
        with db_session() as conn:
            deleted = delete_user(conn, user_id)

        if not deleted:
            return error_response("User not found", 404)

        return success_response(message="User deleted successfully")

    except sqlite3.IntegrityError:
        return error_response("Cannot delete user because they have related records", 400)

    except Exception as error:
        return error_response(str(error), 500)


# -------------------------
# Stats route
# -------------------------

@app.route("/api/stats", methods=["GET"])
@role_required("admin", "librarian")
def stats():
    with db_session() as conn:
        system_stats = get_stats(conn)

    return success_response(system_stats)


# -------------------------
# Error handlers
# -------------------------

@app.errorhandler(404)
def not_found(error):
    return error_response("Endpoint not found", 404)


@app.errorhandler(405)
def method_not_allowed(error):
    return error_response("Method not allowed", 405)


# -------------------------
# Run app
# -------------------------

if __name__ == "__main__":
    setup_database()
    app.run(debug=True)