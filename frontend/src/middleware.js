import { NextResponse } from "next/server"

export async function middleware(request) {
  const url = request.nextUrl
  const token = request.cookies.get("session_token")?.value

  // Require token
  if (!token) {
    return NextResponse.redirect(new URL("/", request.url))
  }

  // Validate token
  const validateresponse = await fetch(
    new URL("/api/auth/validate", request.url),
    { method: "GET", headers: { cookie: `session_token=${token}` } }
  )

  if (!validateresponse.ok) {
    const response = NextResponse.redirect(new URL("/unauthorize", request.url))
    response.cookies.set("session_token", "", { path: "/", maxAge: 0 })
    response.cookies.set("userrole", "", { path: "/", maxAge: 0 })
    return response
  }

  const data = await validateresponse.json()
  if (!data.valid) {
    return NextResponse.redirect(new URL("/unauthorize", request.url))
  }

  if (url.pathname.startsWith("/adminpage") && data.role !== "admin") {
    return NextResponse.redirect(new URL("/unauthorize", request.url))
  }

  return NextResponse.next()
}


export const config = {
  // uncomment to enable middleware

    matcher: [/*"/adminpage/accounts/accountstable", 
        "/adminpage/admissiontable", 
        "/adminpage/createadmission", 
        "/adminpage/editadmission", 
        "/adminpage/tuitionfee/schoolfees", 
        "/adminpage/scholarship/createscholarship",
        "/adminpage/scholarship/editscholarship",
        "/adminpage/scholarship/scholarships",*/]

}