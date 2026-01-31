import mysql.connector

def tlcchatmate():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="tlcchatmate"
    )

"""
def dbconnection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="chatmate"
    )    
"""