import crypto from "crypto"
import { chatmate } from "../tlcchatmatedb/route"
import { REMEMBER_TTL_SECONDS } from "../sessionconstant"

console.log("Session: ", REMEMBER_TTL_SECONDS)
const base64url = (buffer) => buffer.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "")
const sha256hex = (sha) => crypto.createHash("sha256").update(sha).digest("hex")

export function makeSessionCookie(remember) {
    return {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: remember === "yes" ? REMEMBER_TTL_SECONDS : undefined,
    }
}

export async function createSession({useraccountid, remember}) {
    const token = base64url(crypto.randomBytes(48))
    const tokenHash = sha256hex(token)

    console.log("base64url: ", token)
    console.log("sha256hex: ", tokenHash)

    if (remember === "yes") {
        const expiresat = new Date(Date.now() + REMEMBER_TTL_SECONDS * 1000)
        console.log("expires_at: ", expiresat)

        await chatmate.query("INSERT INTO sessions (useraccountid, sessiontoken, expires_at, remember) VALUES (?,?,?,?)", [useraccountid, tokenHash, expiresat, 1])
    }

    return {token}
}

export async function validateSession(rawToken) {
    if (!rawToken) return {valid: false}
    const tokenHash = sha256hex(rawToken)
    const [rows] = await chatmate.query("SELECT s.sessionid, s.useraccountid, s.expires_at, u.userrole FROM sessions s JOIN useraccounts u ON u.useraccountid = s.useraccountid WHERE s.sessiontoken = ? LIMIT 1", [tokenHash])

    const row = rows[0]
    console.log("renewSession.row: ", row)
    if (!row) {
        return {valid: false}
    }

    const expired = new Date(row.expires_at) <= new Date
    if (expired) {
        console.log("User role: ", row.userrole)
        await chatmate.query("DELETE FROM sessions WHERE sessionid = ?", [row.sessionid])
        return {valid: false}
    }

    return {valid: true, useraccountid: row.useraccountid, role: row.userrole}
}

export async function destroySession(rawToken) {
    if (!rawToken) return;
    const tokenHash = sha256hex(rawToken)
    await chatmate.query("DELETE FROM sessions WHERE sessiontoken = ? ", [tokenHash])
}