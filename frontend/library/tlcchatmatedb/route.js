import mysql from "mysql2/promise"

// october 20
export const chatmate = mysql.createPool({
    host: "srv2092.hstgr.io",
    user: "u690915301_administrator",
    password: "tlcchatmate#898989mm$//M",
    database: "u690915301_tlcchatmate",
    port: 3306,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
})

// latest wgen september 21, 2025
{/*
export const chatmate = mysql.createPool({
    host: "localhost",
    user: "root",
    password: "",
    database: "chatmate",
    port: 3306
})    
*/}

// latest when september 15, 2025
{/*
export const chatmate = mysql.createPool({
    host: "localhost",
    user: "root",
    password: "",
    database: "capstone",
    port: 3306
})
*/}
{/*
export const chatmate = mysql.createPool({
    host: "localhost",
    user: "root",
    password: "",
    database: "chatmate",
    port: 3306
})    
*/}
{/*
export const tlcchatmatedb = mysql.createPool({
    host: "localhost",
    user: "root",
    password: "",
    database: "tlcchatmate",
    port: 3306
})    
*/}