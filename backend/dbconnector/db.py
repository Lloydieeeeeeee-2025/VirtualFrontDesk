import os
import mysql.connector

def tlcchatmate():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "db"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "password"), 
        database=os.getenv("DB_NAME", "tlcchatmate"),
        port=int(os.getenv("DB_PORT", "3306")),
    )

"""def tlcchatmate():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="tlcchatmate"
    )
"""
"""
def dbconnection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="chatmate"
    )    
"""