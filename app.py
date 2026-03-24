from flask import Flask, render_template, request, redirect, session, send_file, url_for
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from config import init_db
import io
import csv

app = Flask(__name__)
app.secret_key = "supersecretkey"

# CONNECT MONGO
mongo = init_db(app)

# ---------------------------------------------------------
# HELPER: LOGIN REQUIRED
# ---------------------------------------------------------
def login_required():
    if "username" not in session:
        return False
    return True


# ---------------------------------------------------------
# DEFAULT ROUTE
# ---------------------------------------------------------
@app.route("/")
def index():
    return redirect("/login")


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = mongo.db.users.find_one({"username": username})

        if user and user.get("password") == password:
            session["username"] = user["username"]
            session["role"] = user.get("role", "staff")
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid username or password!")

    return render_template("login.html")


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/login")

    inventory = list(mongo.db.inventory.find())
    current_date = datetime.now()

    total_units = 0
    low_stock_count = 0
    expiring_soon_count = 0
    blood_groups = set()
    low_stock_alerts = []
    expiry_alerts = []

    for item in inventory:
        item["_id"] = str(item["_id"])  # Convert ObjectId safely

        qty = item.get("quantity", 0)
        group = item.get("blood_group", "Unknown")
        expiry = item.get("expiry_date")

        total_units += qty
        blood_groups.add(group)

        if qty < 3:
            low_stock_alerts.append(f"{group} low stock ({qty})")
            low_stock_count += 1

        if isinstance(expiry, datetime):
            days_left = (expiry - current_date).days
            if days_left < 0:
                expiry_alerts.append(f"{group} expired on {expiry.strftime('%Y-%m-%d')}")
            elif 0 <= days_left <= 5:
                expiry_alerts.append(f"{group} expires on {expiry.strftime('%Y-%m-%d')}")
                expiring_soon_count += 1

    return render_template(
        "dashboard.html",
        inventory=inventory,
        total_units=total_units or 0,
        low_stock_count=low_stock_count or 0,
        expiring_soon=expiring_soon_count or 0,
        total_groups=len(blood_groups) or 0,
        low_stock_alerts=low_stock_alerts,
        expiry_alerts=expiry_alerts,
        current_date=current_date
    )


# ---------------------------------------------------------
# DONORS
# ---------------------------------------------------------
@app.route("/donors")
def donors():
    if not login_required():
        return redirect("/login")

    donors = list(mongo.db.donors.find())
    for donor in donors:
        donor["_id"] = str(donor["_id"])
    return render_template("donors.html", donors=donors)


# ---------------------------------------------------------
# ADD DONOR
# ---------------------------------------------------------
@app.route("/add_donor", methods=["GET", "POST"])
def add_donor():
    if not login_required():
        return redirect("/login")

    if request.method == "POST":
        donor = {
            "name": request.form["name"],
            "age": int(request.form["age"]),
            "gender": request.form["gender"],
            "blood_group": request.form["blood_group"],
            "contact": request.form["contact"],
            "donation_date": datetime.now()
        }

        insert_ref = mongo.db.donors.insert_one(donor)

        mongo.db.inventory.insert_one({
            "blood_group": donor["blood_group"],
            "quantity": 1,
            "donor_id": str(insert_ref.inserted_id),
            "donation_date": datetime.now(),
            "expiry_date": datetime.now() + timedelta(days=30)
        })

        return redirect("/donors")

    return render_template("add_donor.html")


# ---------------------------------------------------------
# VIEW SINGLE DONOR
# ---------------------------------------------------------
@app.route("/donor/<id>")
def view_donor(id):
    if not login_required():
        return redirect("/login")

    try:
        donor = mongo.db.donors.find_one({"_id": ObjectId(id)})

        if donor:
            donor["_id"] = str(donor["_id"])

        return render_template("view_donor.html", donor=donor)

    except:
        return render_template("view_donor.html", donor=None)


# ---------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------
@app.route("/inventory")
def inventory_page():
    if not login_required():
        return redirect("/login")

    data = list(mongo.db.inventory.find())
    for item in data:
        item["_id"] = str(item["_id"])
    return render_template("inventory.html", inventory=data)


@app.route("/edit/<id>", methods=["GET", "POST"])
def edit_item(id):
    if not login_required():
        return redirect("/login")

    item = mongo.db.inventory.find_one({"_id": ObjectId(id)})

    if request.method == "POST":
        mongo.db.inventory.update_one(
            {"_id": ObjectId(id)},
            {
                "$set": {
                    "blood_group": request.form["blood_group"],
                    "quantity": int(request.form["quantity"]),
                    "expiry_date": datetime.strptime(
                        request.form["expiry_date"], "%Y-%m-%d"
                    )
                }
            }
        )
        return redirect("/inventory")

    item["_id"] = str(item["_id"])
    return render_template("edit_item.html", item=item)


@app.route("/delete/<id>")
def delete_item(id):
    if not login_required():
        return redirect("/login")

    mongo.db.inventory.delete_one({"_id": ObjectId(id)})
    return redirect("/inventory")


# ---------------------------------------------------------
# REQUESTS
# ---------------------------------------------------------
@app.route("/requests")
def requests_page():
    if not login_required():
        return redirect("/login")

    reqs = list(mongo.db.requests.find())
    for r in reqs:
        r["_id"] = str(r["_id"])
    return render_template("blood_requests.html", requests=reqs)
@app.route("/add_request", methods=["GET", "POST"])
def add_request():
    if not login_required():
        return redirect("/login")

    if request.method == "POST":
        blood_request = {
            "patient_name": request.form["patient_name"],
            "blood_group": request.form["blood_group"],
            "units_needed": int(request.form["units_needed"]),
            "hospital": request.form["hospital"],
            "contact": request.form["contact"],
            "request_date": datetime.now()
        }

        mongo.db.requests.insert_one(blood_request)
        return redirect("/requests")

    return render_template("add_request.html")



# ---------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------
@app.route("/analytics")
def analytics():
    if not login_required():
        return redirect("/login")

    inv = list(mongo.db.inventory.find())

    blood_data = {}
    for item in inv:
        group = item.get("blood_group", "Unknown")
        qty = item.get("quantity", 0)
        blood_data[group] = blood_data.get(group, 0) + qty

    labels = list(blood_data.keys())
    values = list(blood_data.values())

    return render_template(
        "analytics.html",
        labels=labels,
        values=values
    )


# ---------------------------------------------------------
# EXPORT CSV
# ---------------------------------------------------------
@app.route("/export_csv")
def export_csv():
    if not login_required():
        return redirect("/login")

    inv = list(mongo.db.inventory.find())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Blood Group", "Quantity", "Expiry Date"])

    for i in inv:
        expiry = i.get("expiry_date")
        expiry_text = expiry.strftime("%Y-%m-%d") if isinstance(expiry, datetime) else "N/A"

        writer.writerow([
            i.get("blood_group", "Unknown"),
            i.get("quantity", 0),
            expiry_text
        ])

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="blood_inventory.csv"
    )


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
