import { NextResponse } from "next/server";
import { destroySession } from "../../../../../library/sessions/route";

export async function POST(request) {
    await destroySession(request.cookies.get("session_token")?.value)
    const response = NextResponse.json({success: true})

    response.cookies.get("session_token", "", {path: "/", maxAge: 0})
    response.cookies.get("userrole", "", {path: "/", maxAge: 0})

    return response
}