// api/debug/route.js
import { NextResponse } from "next/server";
import { chatmate } from "../../../../library/tlcchatmatedb/route";

export async function GET() {
    try {
        console.log("Testing database connection...");
        
        // Test 1: Try to get a connection
        const connection = await chatmate.getConnection();
        console.log("✓ Connection acquired");
        
        // Test 2: Try a simple query
        const [rows] = await connection.query("SELECT 1 as test");
        console.log("✓ Query executed successfully");
        
        connection.release();
        console.log("✓ Connection released");
        
        return NextResponse.json({
            success: true,
            message: "Database connection is working!",
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.error("❌ Database Error Details:");
        console.error("Error Message:", error.message);
        console.error("Error Code:", error.code);
        console.error("Error Errno:", error.errno);
        console.error("Full Error:", error);
        
        return NextResponse.json({
            success: false,
            message: "Database connection failed",
            error: {
                message: error.message,
                code: error.code,
                errno: error.errno,
                sqlState: error.sqlState
            }
        }, { status: 500 });
    }
}