"use client"
import { useState } from "react"

export default function Create({ open, close }) {
    const [userName, setUserName] = useState("")
    const [userNameError, setUserNameError] = useState("")
    const [userEmail, setUserEmail] = useState("")
    const [userEmailError, setUserEmailError] = useState("")
    const [userPassword, setUserPassword] = useState("")
    const [userPasswordError, setUserPasswordError] = useState("")
    const [verifyUserPassword, setVerifyUserPassword] = useState("")
    const [verifyUserPasswordError, setVerifyUserPasswordError] = useState("")

    const submit = async () => {
        setUserNameError("")
        setUserEmailError("")
        setUserPasswordError("")
        setVerifyUserPasswordError("")
        if (!userName.match(/^[A-Za-z\s]{2,50}$/)) {
            setUserNameError("Name must contain letters and spaces only, 2-50 characters.")
            return
        }
        if (!userEmail.match(/^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/)) {
            setUserEmailError("Please provide a valid email.")
            return
        }
        if (!userPassword.match(/^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/)) {
            setUserPasswordError("Password must contain uppercase, lowercase, number, and special character. Minimum 8 characters.")
            return
        }
        if (userPassword !== verifyUserPassword) {
            setVerifyUserPasswordError("Passwords do not match.")
            return
        }
        try {
            const res = await fetch("/api/admin/users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_name: userName,
                    user_email: userEmail,
                    user_password: userPassword,
                }),
            })
            const data = await res.json()
            if (!res.ok) {
                if (res.status === 409) {
                    setUserEmailError("Email is already registered.")
                } else if (res.status === 400) {
                    setUserPasswordError(data.message || "Invalid input.")
                } else {
                    setUserEmailError("An unexpected error occurred.")
                }
                return
            }
            setUserName("")
            setUserEmail("")
            setUserPassword("")
            setVerifyUserPassword("")
        } catch (err) {
            console.error("Error:", err.message)
            setUserEmailError("An error occurred while creating the account.")
        }
    }

    return (
        <main className="z-500">
            <div className={`fixed inset-0 bg-opacity-20 bg-black/30 backdrop-blur-xs transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`} onClick={close}></div>
            <div className={`fixed top-0 right-0 h-full w-full md:w-[30%] bg-white border-l border-gray-200 transform transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}>
                <div className="flex flex-col h-full p-5 space-y-4">
                    <div>
                        <button onClick={close} className="text-gray-600 hover:text-black">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                    <div className="flex flex-col h-full">
                        <div className="mb-4 w-full flex justify-between items-center">
                            <h2 className="text-lg font-semibold mb-2">Add New Administrator</h2>
                            <button onClick={close} className="text-gray-600 hover:text-black">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="w-full flex-1 overflow-y-auto">
                            <div className="space-y-4 md:space-y-6">
                                <div className="space-y-2">
                                    <label htmlFor="name" className="block text-sm font-medium text-gray-700">Name</label>
                                    <input type="text" id="name" name="name" value={userName} onChange={(e) => setUserName(e.target.value)} placeholder="Full name" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent" />
                                    {userNameError && <span className="text-red-600 text-sm mt-1 block">{userNameError}</span>}
                                </div>
                                <div className="space-y-2">
                                    <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
                                    <input type="email" id="email" name="email" value={userEmail} onChange={(e) => setUserEmail(e.target.value)} placeholder="user@example.com" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent" />
                                    {userEmailError && <span className="text-red-600 text-sm mt-1 block">{userEmailError}</span>}
                                </div>
                                <div className="pt-4 border-t border-gray-200">
                                    <h3 className="text-lg font-medium text-gray-800 mb-3">Create Password</h3>
                                    <div className="space-y-2">
                                        <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
                                        <input type="password" id="password" name="password" value={userPassword} onChange={(e) => setUserPassword(e.target.value)} placeholder="••••••••" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent" />
                                        {userPasswordError && <span className="text-red-600 text-sm mt-1 block">{userPasswordError}</span>}
                                    </div>
                                    <div className="space-y-2">
                                        <label htmlFor="verifyPassword" className="block text-sm font-medium text-gray-700">Verify Password</label>
                                        <input type="password" id="verifyPassword" name="verifyPassword" value={verifyUserPassword} onChange={(e) => setVerifyUserPassword(e.target.value)} placeholder="••••••••" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent" />
                                        {verifyUserPasswordError && <span className="text-red-600 text-sm mt-1 block">{verifyUserPasswordError}</span>}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <button className="w-full bg-gray-200 hover:bg-gray-300 transition duration-400 p-2 rounded-lg" onClick={submit}>Save</button>
                </div>
            </div>
        </main>
    )
}