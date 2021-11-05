import os
import sys
import uuid

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.utils import secure_filename
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from random import randint
from functools import wraps

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Create decorator for user access level
def requires_access_level(access_level):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session["user_id"]
            access_level = db.execute("SELECT access_level FROM users WHERE id = :user_id",
                                user_id=user_id)[0]["access_level"]
            #print(access_level, file=sys.stderr)
            if not access_level == "admin":
                return apology("You do not have access to that page. Sorry!")
            return f(*args, **kwargs)
        return decorated_function
    return decorator




# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///bar.db")

# Display menu editor to admin
@app.route("/menu-admin", methods=["GET", "POST"])
@login_required
@requires_access_level("admin")
def menuAdmin():
        """Display the menu"""
        rows = db.execute("SELECT * FROM menu")

        for row in rows:
            price = row["price"]
            row.update( {'price' : usd(price)} )

        return render_template("menu-admin.html", rows=rows)

# Display menu to user
@app.route("/menu-user", methods=["GET", "POST"])
@login_required
def menuUser():

    rows = db.execute("SELECT * FROM menu WHERE active = 'yes'")
    user_id = session["user_id"]

    if request.method == "POST":

        order_id = uuid.uuid1()
        order_code = randint(1000, 9999)
        # print(order_code, file=sys.stderr)
        total_quantity = 0

        for row in rows:
            item_id = row["item_id"]
            quantity_id = "quantity-" + str(item_id)
            # print(quantity_id, file=sys.stderr)
            quantity = request.form.get(quantity_id)
            # print(quantity, file=sys.stderr)
            if not quantity == "":
                quantity = int(request.form.get(quantity_id))
                if quantity > 0:
                    total_quantity = quantity + total_quantity
                    price = row["price"]
                    amount = quantity * price
                    status = "not submitted"
                    db.execute("INSERT INTO orders (order_id, item_id, quantity, amount, user_id, status, order_code) VALUES (:order_id, :item_id, :quantity, :amount, :user_id, :status, :order_code)",
                            order_id=order_id.int, item_id=item_id, quantity=quantity, amount=amount, user_id=user_id, status=status, order_code=order_code)

        if total_quantity > 0:
            return redirect("/confirmation")
        else:
            return apology("please select an item")

    else:
        """Display the menu"""

        for row in rows:
            price = row["price"]
            row.update( {'price' : usd(price)} )

        return render_template("menu-user.html", rows=rows)

# Display order confirmation page to user
@app.route("/confirmation", methods=["GET", "POST"])
@login_required
def confirmation():

    if request.method == "POST":
        orders = db.execute("SELECT DISTINCT order_id FROM orders WHERE user_id = :user_id ORDER BY timestamp DESC LIMIT 1",
                          user_id=session["user_id"])
        if not len(orders) > 0:
            return apology("no orders")

        for order in orders:
            if request.form['submit_button'] == 'Confirm':
                tablenumber = request.form['tablenumber']
                db.execute("UPDATE orders SET status = 'in progress', tablenumber = :tablenumber WHERE order_id = :order_id",
                        tablenumber=tablenumber, order_id=order["order_id"])


                return redirect("/confirmed")

            else:
                db.execute("UPDATE orders SET status = 'canceled' WHERE order_id = :order_id",
                        order_id=order["order_id"])

                return redirect("/menu-user")

    if request.method == "GET":
        orders = db.execute("SELECT DISTINCT order_id FROM orders WHERE user_id = :user_id ORDER BY timestamp DESC LIMIT 1",
                          user_id=session["user_id"])

        if not len(orders) > 0:
            return apology("no orders")

        for order in orders:
            order_amount = db.execute("SELECT SUM(amount) AS total FROM orders WHERE order_id = :order_id",
                              order_id=order["order_id"])
            # print(order, file=sys.stderr)
            # print(order_amount, file=sys.stderr)
            order.update( {'order_amount' : usd(order_amount[0]["total"])} )
            order_timestamp = db.execute("SELECT timestamp FROM orders WHERE order_id = :order_id LIMIT 1",
                              order_id=order["order_id"])
            order.update( {'order_timestamp' : order_timestamp[0]["timestamp"]} )

            order_items = db.execute("SELECT * FROM orders LEFT JOIN menu ON orders.item_id = menu.item_id WHERE order_id = :order_id",
                        order_id=order["order_id"])

            order.update( {'order_items' : order_items} )

            order_status = db.execute("SELECT status FROM orders WHERE order_id = :order_id LIMIT 1",
                              order_id=order["order_id"])

            order.update( {'order_status' : order_status[0]["status"].title()} )

            order_code = db.execute("SELECT order_code FROM orders WHERE order_id = :order_id LIMIT 1",
                              order_id=order["order_id"])

            order.update( {'order_code' : order_code[0]["order_code"]} )

        return render_template("confirmation.html", orders=orders)

# Display order confirmation page
@app.route("/confirmed", methods=["GET", "POST"])
@login_required
def confirmed():

    if request.method == "GET":
        orders = db.execute("SELECT DISTINCT order_id FROM orders WHERE user_id = :user_id ORDER BY timestamp DESC LIMIT 1",
                          user_id=session["user_id"])

        if not len(orders) > 0:
            return apology("no orders")

        for order in orders:
            order_amount = db.execute("SELECT SUM(amount) AS total FROM orders WHERE order_id = :order_id",
                              order_id=order["order_id"])
            order.update( {'order_amount' : usd(order_amount[0]["total"])} )

            order_code = db.execute("SELECT order_code FROM orders WHERE order_id = :order_id LIMIT 1",
                              order_id=order["order_id"])

            order.update( {'order_code' : order_code[0]["order_code"]} )

        return render_template("confirmed.html", orders=orders)

# Hide an item from the menu
@app.route("/delete", methods=["GET", "POST"])
@login_required
def delete():

    if request.method == "POST":

        item_id = request.form.get("delete")
        db.execute("UPDATE menu SET active = 'no' WHERE item_id = :item_id",
                    item_id=item_id)

        return redirect("/menu-admin")

# Changes the order status to "served"
@app.route("/done", methods=["GET", "POST"])
@login_required
def done():

    if request.method == "POST":

        order_id = request.form.get("done")
        db.execute("UPDATE orders SET status = 'Served' WHERE order_id = :order_id",
                    order_id=order_id)

        return redirect("/history-admin")

# Display past orders of the customer
@app.route("/history-user")
@login_required
def historyUser():
    """Show history of orders"""

    orders = db.execute("SELECT DISTINCT order_id FROM orders WHERE user_id = :user_id ORDER BY timestamp DESC",
                          user_id=session["user_id"])

    if not len(orders) > 0:
        return apology("no orders")

    for order in orders:
        order_amount = db.execute("SELECT SUM(amount) AS total FROM orders WHERE order_id = :order_id",
                          order_id=order["order_id"])
        # print(order, file=sys.stderr)
        # print(order_amount, file=sys.stderr)
        order.update( {'order_amount' : usd(order_amount[0]["total"])} )
        order_timestamp = db.execute("SELECT timestamp FROM orders WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])
        order.update( {'order_timestamp' : order_timestamp[0]["timestamp"]} )

        order_items = db.execute("SELECT * FROM orders LEFT JOIN menu ON orders.item_id = menu.item_id WHERE order_id = :order_id",
                    order_id=order["order_id"])

        order.update( {'order_items' : order_items} )

        order_status = db.execute("SELECT status FROM orders WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])

        order.update( {'order_status' : order_status[0]["status"].title()} )

        order_code = db.execute("SELECT order_code FROM orders WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])

        order.update( {'order_code' : order_code[0]["order_code"]} )

    return render_template("history-user.html", orders=orders)

# Default route
@app.route("/")
@login_required
def homepage():
    user_id = session["user_id"]
    access_level = db.execute("SELECT access_level FROM users WHERE id = :user_id",
                                user_id=user_id)[0]["access_level"]
    if access_level == "admin":
        return redirect("/history-admin")
    else:
        return redirect("/menu-user")

# Display all the orders
@app.route("/history-admin")
@login_required
@requires_access_level("admin")
def historyAdmin():
    """Show history of orders"""

    orders = db.execute("SELECT DISTINCT order_id FROM orders ORDER BY timestamp DESC")

    if not len(orders) > 0:
        return apology("no orders")

    for order in orders:
        user_id = db.execute("SELECT user_id FROM orders WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])
        order.update( {'user_id' : user_id[0]["user_id"]} )
        order_amount = db.execute("SELECT SUM(amount) AS total FROM orders WHERE order_id = :order_id",
                          order_id=order["order_id"])
        # print(order, file=sys.stderr)
        # print(order_amount, file=sys.stderr)
        order.update( {'order_amount' : usd(order_amount[0]["total"])} )
        order_timestamp = db.execute("SELECT timestamp FROM orders WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])
        order.update( {'order_timestamp' : order_timestamp[0]["timestamp"]} )

        order_items = db.execute("SELECT * FROM orders LEFT JOIN menu ON orders.item_id = menu.item_id WHERE order_id = :order_id",
                    order_id=order["order_id"])

        order.update( {'order_items' : order_items} )

        order_status = db.execute("SELECT status FROM orders WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])

        order.update( {'order_status' : order_status[0]["status"].title()} )

        order_code = db.execute("SELECT order_code FROM orders WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])

        order.update( {'order_code' : order_code[0]["order_code"]} )

        order_first_name = db.execute("SELECT first_name FROM orders LEFT JOIN users ON orders.user_id = users.id WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])

        order.update( {'order_first_name' : order_first_name[0]["first_name"]} )

        order_tablenumber = db.execute("SELECT tablenumber FROM orders WHERE order_id = :order_id LIMIT 1",
                          order_id=order["order_id"])

        order.update( {'order_tablenumber' : order_tablenumber[0]["tablenumber"]} )

    return render_template("history-admin.html", orders=orders)

# Create a new item in the menu
@app.route("/new-item", methods=['GET', 'POST'])
@login_required
def newItem():
    if request.method == "POST":

        name = request.form.get("name").title()
        price = request.form.get("price")

        if not name:
            return apology("must provide a name")

        check_name = db.execute("SELECT * FROM menu WHERE name = :name AND active = 'yes'",
                                name=name)

        if len(check_name) != 0:
            return apology("already exists")

        try:
            price = float(price)
        except ValueError:
            return apology("price should be a number")

        if not price > 0:
            return apology("price should be positive")

        # add item to menu
        db.execute("INSERT INTO menu (name, price) VALUES (:name, :price)",
                        name=name, price=price)

        return redirect("/menu-admin")

    else:
        return render_template("new-item.html")


# Sign-in page
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")



# Sign-up page
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        first_name = request.form.get("first_name")

        # Render an apology if the user’s input is blank
        if not username:
            return apology("must provide username", 403)
        if not first_name:
            return apology("must provide name", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)

        # Render an apology if username already exists
        if len(rows) != 0:
            return apology("username already taken", 403)

        # Render an apology if the user’s input is blank
        elif not password:
            return apology("must provide password", 403)

        # Render an apology if the passwords don't match
        elif password != request.form.get("confirmation"):
            return apology("passwords don't match", 403)

        # Submit the user’s input via POST to /register.

        hash = generate_password_hash(password)

        # INSERT the new user into users, storing a hash of the user’s password
        db.execute("INSERT INTO users (username, first_name, hash) VALUES (:username, :first_name, :hash)",
                    username=username, first_name=first_name, hash=hash)

        return redirect("/login ")

    else:
        return render_template("register.html")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Add the user access level to the user property
@app.context_processor
def inject_access_level_for_all_templates():
    user_id = session.get('user_id')
    if not user_id == None:
        access_level = db.execute("SELECT access_level FROM users WHERE id = :user_id",
                                    user_id=user_id)[0]["access_level"]
        # print(access_level, file=sys.stderr)
        return dict(access_level=access_level)
    else:
        return dict()

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
