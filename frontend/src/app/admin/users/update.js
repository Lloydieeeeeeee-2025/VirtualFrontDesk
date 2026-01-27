"use client"
import { useState, useEffect } from "react"

export default function Update({ open, close, selectedAccountRow }) {
    const [userName, setUserName] = useState("")
    const [userNameError, setUserNameError] = useState("")
    const [userEmail, setUserEmail] = useState("")
    const [userEmailError, setUserEmailError] = useState("")
    const [currentPassword, setCurrentPassword] = useState("")
    const [currentPasswordError, setCurrentPasswordError] = useState("")
    const [newPassword, setNewPassword] = useState("")
    const [newPasswordError, setNewPasswordError] = useState("")
    const [verifyPassword, setVerifyPassword] = useState("")
    const [verifyPasswordError, setVerifyPasswordError] = useState("")

    useEffect(() => {
        if (open && selectedAccountRow) {
            setUserName(selectedAccountRow.user_name || "")
            setUserEmail(selectedAccountRow.user_email || "")
            setCurrentPassword("")
            setNewPassword("")
            setVerifyPassword("")
            setUserNameError("")
            setUserEmailError("")
            setCurrentPasswordError("")
            setNewPasswordError("")
            setVerifyPasswordError("")
        }
    }, [open, selectedAccountRow])

    const submit = async () => {
        setUserNameError("")
        setUserEmailError("")
        setCurrentPasswordError("")
        setNewPasswordError("")
        setVerifyPasswordError("")
        let isValid = true
        if (!userName.match(/^[A-Za-z\s]{2,50}$/)) {
            setUserNameError("Name must contain letters and spaces only, 2-50 characters.")
            isValid = false
        }
        if (!userEmail.match(/^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/)) {
            setUserEmailError("Please provide a valid email.")
            isValid = false
        }
        if (currentPassword || newPassword || verifyPassword) {
            if (!currentPassword) {
                setCurrentPasswordError("Enter your current password.")
                isValid = false
            }
            if (!newPassword.match(/^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/)) {
                setNewPasswordError("Password must contain uppercase, lowercase, number, and special character. Minimum 8 characters.")
                isValid = false
            }
            if (newPassword !== verifyPassword) {
                setVerifyPasswordError("Passwords do not match.")
                isValid = false
            }
        }
        if (!isValid) return
        try {
            const payload = {
                user_id: selectedAccountRow?.user_id,
                user_name: userName,
                user_email: userEmail,
            };
            if (currentPassword && newPassword) {
                payload.currentPassword = currentPassword;
                payload.newPassword = newPassword;
            }
            const res = await fetch("/api/admin/users", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) {
                if (res.status === 409) {
                    setUserEmailError("Email is already registered.");
                } else if (res.status === 401) {
                    setCurrentPasswordError("Current password is incorrect.");
                } else if (res.status === 400 && data.field === "password") {
                    setNewPasswordError(data.message);
                } else if (res.status === 400) {
                    setUserEmailError(data.message || "Invalid input.");
                } else {
                    setUserEmailError(data.message || "An unexpected error occurred.");
                }
                return;
            }
            setTimeout(() => { close(); }, 1500);
        } catch (err) {
            setUserEmailError("An error occurred while updating the user.");
        }
    };

    return (
        <main>
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
                            <h2 className="text-lg font-semibold mb-2">Update Administrator</h2>
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
                                    <input type="text" id="name" name="name" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent rounded-lg" value={userName} onChange={(e) => setUserName(e.target.value)} placeholder="Full name" />
                                    {userNameError && <span className="text-red-600 text-sm mt-1 block">{userNameError}</span>}
                                </div>
                                <div className="space-y-2">
                                    <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
                                    <input type="email" id="email" name="email" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent rounded-lg" value={userEmail} onChange={(e) => setUserEmail(e.target.value)} placeholder="user@example.com" />
                                    {userEmailError && <span className="text-red-600 text-sm mt-1 block">{userEmailError}</span>}
                                </div>
                                <div className="pt-4 border-t border-gray-200">
                                    <h3 className="text-lg font-medium text-gray-800 mb-3">Change Password (Optional)</h3>
                                    <div className="space-y-2">
                                        <label htmlFor="currentPassword" className="block text-sm font-medium text-gray-700">Current Password</label>
                                        <input type="password" id="currentPassword" name="currentPassword" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent rounded-lg" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} placeholder="••••••••" />
                                        {currentPasswordError && <span className="text-red-600 text-sm mt-1 block">{currentPasswordError}</span>}
                                    </div>
                                    <div className="space-y-2">
                                        <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700">New Password</label>
                                        <input type="password" id="newPassword" name="newPassword" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent rounded-lg" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="••••••••" />
                                        {newPasswordError && <span className="text-red-600 text-sm mt-1 block">{newPasswordError}</span>}
                                    </div>
                                    <div className="space-y-2">
                                        <label htmlFor="verifyPassword" className="block text-sm font-medium text-gray-700">Verify New Password</label>
                                        <input type="password" id="verifyPassword" name="verifyPassword" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent rounded-lg" value={verifyPassword} onChange={(e) => setVerifyPassword(e.target.value)} placeholder="••••••••" />
                                        {verifyPasswordError && <span className="text-red-600 text-sm mt-1 block">{verifyPasswordError}</span>}
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