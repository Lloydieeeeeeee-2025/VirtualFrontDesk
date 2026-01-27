import { NextResponse } from "next/server";
import { chatmate } from "../../../../../library/tlcchatmatedb/route";
import bcrypt from "bcryptjs";

export async function GET() {
    try {
        const [users] = await chatmate.query(`SELECT user_id, user_name, user_email FROM User`);

        return NextResponse.json({ success: true, data: users }, { status: 200 });
    } catch (error) {
        return NextResponse.json({ success: false, message: error.message }, { status: 500 });
    }
}

export async function DELETE(request) {
    try {
        const { id } = await request.json();
        await chatmate.query(`DELETE FROM User WHERE user_id = ?`, [id]);
        return NextResponse.json({ success: true, message: "User deleted successfully" }, { status: 200 });
    } catch (error) {
        return NextResponse.json({ success: false, message: error.message }, { status: 500 });
    }
}

export async function PUT(request) {
    try {
        const { user_id, user_name, user_email, currentPassword, newPassword } = await request.json();

        if (!user_id || !user_name || !user_email) {
            return NextResponse.json({ success: false, message: "Missing required fields" }, { status: 400 });
        }

        // Verify user exists and fetch current password for validation
        const [user] = await chatmate.query(`SELECT user_password FROM User WHERE user_id = ?`, [user_id]);
        if (!user || user.length === 0) {
            return NextResponse.json({ success: false, message: "User not found" }, { status: 404 });
        }

        // Validate email uniqueness (excluding the current user)
        const [existingEmail] = await chatmate.query(
            `SELECT user_id FROM User WHERE user_email = ? AND user_id != ?`,
            [user_email, user_id]
        );
        if (existingEmail.length > 0) {
            return NextResponse.json({ success: false, message: "Email is already registered" }, { status: 409 });
        }

        let updateQuery = `UPDATE User SET user_name = ?, user_email = ?`;
        const queryParams = [user_name, user_email];

        // Handle password update if provided
        if (currentPassword && newPassword) {
            const isPasswordValid = await bcrypt.compare(currentPassword, user[0].user_password);
            if (!isPasswordValid) {
                return NextResponse.json({ success: false, message: "Current password is incorrect", field: "password" }, { status: 401 });
            }

            if (!newPassword.match(/^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/)) {
                return NextResponse.json(
                    { success: false, message: "New password must contain uppercase, lowercase, number, and special character. Minimum 8 characters.", field: "password" },
                    { status: 400 }
                );
            }

            const hashedPassword = await bcrypt.hash(newPassword, 10);
            updateQuery += `, user_password = ?`;
            queryParams.push(hashedPassword);
        } else if (currentPassword || newPassword) {
            return NextResponse.json({ success: false, message: "Both current and new password are required for password update", field: "password" }, { status: 400 });
        }

        updateQuery += ` WHERE user_id = ?`;
        queryParams.push(user_id);

        const [result] = await chatmate.query(updateQuery, queryParams);

        if (result.affectedRows === 0) {
            return NextResponse.json({ success: false, message: "Failed to update user" }, { status: 500 });
        }

        return NextResponse.json({ success: true, message: "User updated successfully" }, { status: 200 });
    } catch (error) {
        return NextResponse.json({ success: false, message: error.message }, { status: 500 });
    }
}

export async function POST(request) {
    try {
        const { user_name, user_email, user_password } = await request.json();

        const [existingUser] = await chatmate.query(
            "SELECT user_id FROM User WHERE user_email = ?",
            [user_email]
        );
        if (existingUser.length > 0) {
            return NextResponse.json(
                { success: false, message: "Email is already registered." },
                { status: 400 }
            );
        }

        const salt = await bcrypt.genSalt(10);
        const hashedPassword = await bcrypt.hash(user_password, salt);

        await chatmate.query(
            "INSERT INTO User (user_name, user_email, user_password) VALUES (?, ?, ?)",
            [user_name, user_email, hashedPassword]
        );

        return NextResponse.json(
            { success: true, message: `Hello ${user_name}, Welcome to TLC ChatMate!` },
            { status: 201 }
        );

    } catch (error) {
        return NextResponse.json(
            { success: false, message: "Server error during registration." },
            { status: 500 }
        );
    }
}