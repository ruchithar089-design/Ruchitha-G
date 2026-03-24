from flask_pymongo import PyMongo

def init_db(app):
    # Connect to local MongoDB
    app.config["MONGO_URI"] = "mongodb://localhost:27017/blood_bank"
    mongo = PyMongo(app)
    return mongo
