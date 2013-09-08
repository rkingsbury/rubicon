import os
import json
from pymongo.mongo_client import MongoClient

__author__ = 'xiaohuiqu'


def get_g3_bench_collection():
    global db_dir, db_path, f, db_creds, host, port, user, password, database_name, collection_name, conn, db, collection
    db_dir = os.environ['DB_LOC']
    db_path = os.path.join(db_dir, 'molecules_db.json')
    with open(db_path) as f:
        db_creds = json.load(f)
    host = db_creds['host']
    port = db_creds['port']
    user = db_creds['readonly_user']
    password = db_creds['readonly_password']
    database_name = db_creds['database']
    collection_name = db_creds['collection']
    conn = MongoClient(host=host, port=port)
    db = conn[database_name]
    if user:
        db.authenticate(user, password)
    collection = db[collection_name]
    return collection

collection = get_g3_bench_collection()

mission_tag = "G3 Test Set Benchmark (Shyue Scheme)"

result = collection.find({"user_tags.mission": mission_tag},
                         fields=['pretty_formula', 'IE', 'EA', 'charge'])

for m in result:
    print m