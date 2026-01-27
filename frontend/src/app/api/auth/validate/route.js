import { NextResponse } from "next/server";
import { validateSession } from "../../../../../library/sessions/route";

export async function GET(request) {
    try {
        const cookie = request.cookies.get("session_token")?.value
        const result = await validateSession(cookie)

        if (!result.valid) {
            return NextResponse.json({valid: false, message: "cookie cannot found"}, {status: 401})
        }

        return NextResponse.json({valid: true, role: result.role})
    }
    catch (error) {
        return NextResponse.json({valid: false}, {status: 500})
    }
}