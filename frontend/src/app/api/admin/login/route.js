import { NextResponse } from "next/server";
import { chatmate } from "../../../../../library/tlcchatmatedb/route";
import bcrypt from "bcryptjs";

export async function POST(request) {
    try {
        const { user_email, user_password } = await request.json();

        if (!user_email || !user_password) {
            return NextResponse.json(
                { success: false, message: "Email and password are required." },
                { status: 400 }
            );
        }

        const [userRows] = await chatmate.query(
            "SELECT user_id, user_name, user_email, user_password FROM User WHERE user_email = ?",
            [user_email]
        );

        if (userRows.length === 0) {
            return NextResponse.json(
                { success: false, message: "Invalid email or password." },
                { status: 401 }
            );
        }

        const authenticatedUser = userRows[0];
        const isPasswordValid = await bcrypt.compare(user_password, authenticatedUser.user_password);

        if (!isPasswordValid) {
            return NextResponse.json(
                { success: false, message: "Invalid email or password." },
                { status: 401 }
            );
        }

        return NextResponse.json(
            {
                success: true,
                message: `Hello ${authenticatedUser.user_name}, Welcome back to TLC ChatMate!`,
                data: {
                    user_id: authenticatedUser.user_id,
                    user_name: authenticatedUser.user_name,
                    user_email: authenticatedUser.user_email,
                },
            },
            { status: 200 }
        );
    } catch (error) {
        console.error("Login error:", error);
        return NextResponse.json(
            { success: false, message: "Server error during login." },
            { status: 500 }
        );
    }
}