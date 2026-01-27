"use client"
import Link from "next/link"
import UsersNavigation from "../student/users/usersnavigation"
import { useState, useEffect } from "react"

export default function UnAuthorize() {
    const [isAsideOpen, setIsAsideOpen] = useState(false)

    return(
        <main>
            <UsersNavigation isAsideOpen={isAsideOpen} setIsAsideOpen={setIsAsideOpen}/>
            <div className="min-h-screen flex items-center justify-center">
                <div>
                    <h1 className="text-2xl font-bold text-center mb-4">Only authorize user can access this page</h1>
                    <Link className="flex justify-center" href="/userpage/users/faqs">Go to home</Link>
                </div>
            </div>
        </main>
    )
}