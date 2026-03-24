from pymongo import MongoClient
from datetime import datetime, timedelta

client = MongoClient("mongodb://localhost:27017")
db = client.blood_bank_db  # change if DB name differs

for item in db.inventory.find():
    update_fields = {}

    if "quantity" not in item:
        update_fields["quantity"] = 1

    if "donation_date" not in item:
        update_fields["donation_date"] = datetime.now()

    if "expiry_date" not in item:
        update_fields["expiry_date"] = datetime.now() + timedelta(days=30)

    if update_fields:
        db.inventory.update_one(
            {"_id": item["_id"]},
            {"$set": update_fields}
        )

print("✅ Inventory migration completed successfully")
