"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useEffect, useState } from "react"

export default function Navigation() {
    const get_current_page = usePathname()
    const router = useRouter()
    const [isMenuActive, setIsMenuActive] = useState(false)
    const [dropdownOpen, setDropdownOpen] = useState(false)
    const [userData, setUserData] = useState(null)

    useEffect(() => {
        const storedUserData = localStorage.getItem("userData")
        if (storedUserData) {
            const parsedData = JSON.parse(storedUserData)
            setUserData(parsedData)
        } else {
            router.push("/userpage/signin")
        }
    }, [router])

    const toggleDropdown = () => {
        setDropdownOpen(!dropdownOpen)
    }

    const handleSignOut = () => {
        localStorage.removeItem("userData")
        router.push("/admin/login")
    }

    const navLinks = [
        {
            href: "/admin/url",
            label: "URL",
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.622 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364l-4.5 4.5a4.5 4.5 0 0 0 1.242 7.244" />
                </svg>
            ),
        },
        {
            href: "/admin/course",
            label: "Course",
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
                </svg>
            ),
        },
        {
            href: "/admin/handbook",
            label: "Handbook",
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0 0 12 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52 2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 0 1-2.031.352 5.988 5.988 0 0 1-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.971Zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0 2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 0 1-2.031.352 5.989 5.989 0 0 1-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.971Z" />
                </svg>
            ),
        },
        {
            href: "/admin/users",
            label: "Users",
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z" />
                </svg>
            ),
        },
    ]

    return (
        <main className="text-gray-600">
            {/* Top Navigation Bar */}
            <nav className="fixed top-0 z-50 w-full bg-white/80 backdrop-blur-md border-b border-gray-100">
                <div className="px-4 py-2 lg:px-6">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            {/* Mobile menu button */}
                            <button 
                                onClick={() => setIsMenuActive(!isMenuActive)} 
                                className="inline-flex items-center justify-center p-2.5 rounded-lg text-gray-600 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#205781]/20 sm:hidden transition-all duration-200"
                                aria-label="Toggle menu"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                                </svg>
                            </button>
                            
                            {/* Logo */}
                            <div className="flex items-center gap-3">
                                <img src="/logo/logo.png" className="h-8 sm:h-10" alt="TLC ChatMate Logo" />
                                <span className="text-lg sm:text-xl font-bold text-[#205781]">TLC ChatMate</span>
                            </div>
                        </div>

                        {/* User dropdown */}
                        <div className="relative">
                            <button 
                                type="button" 
                                onClick={toggleDropdown} 
                                className="flex items-center gap-2 p-1.5 rounded-full hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#205781]/20 transition-all duration-200"
                            >
                                <img 
                                    className="w-9 h-9 rounded-full object-cover ring-2 ring-gray-100" 
                                    src="https://flowbite.com/docs/images/people/profile-picture-5.jpg  " 
                                    alt="User" 
                                />
                            </button>

                            {dropdownOpen && (
                                <div className="absolute top-full right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden">
                                    <div className="p-4 border-b border-gray-100">
                                        <p className="text-sm font-semibold text-gray-900 truncate">
                                            {userData?.user_name || "Guest"}
                                        </p>
                                        <p className="text-xs text-gray-500 truncate mt-0.5">
                                            {userData?.user_email || "No email"}
                                        </p>
                                    </div>

                                    <div className="py-2">
                                        <Link 
                                            href="/student/faqs" 
                                            className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors duration-150"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
                                            </svg>
                                            ChatMate
                                        </Link>

                                        <button 
                                            onClick={handleSignOut} 
                                            className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors duration-150"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
                                            </svg>
                                            Sign out
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </nav>

            {/* Sidebar — now always shown for authenticated users */}
            {userData && (
                <aside 
                    className={`fixed top-0 left-0 z-40 w-64 h-screen pt-20 transition-transform duration-300 ease-in-out bg-[#205781] ${
                        isMenuActive ? "translate-x-0" : "-translate-x-full"
                    } sm:translate-x-0`}
                >
                    <div className="h-full px-4 py-6 overflow-y-auto">
                        {/* User Profile Card */}
                        <div className="mb-6 p-4 rounded-xl bg-white/10 backdrop-blur-sm">
                            <div className="flex items-center gap-3">
                                <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6 text-white">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M17.982 18.725A7.488 7.488 0 0 0 12 15.75a7.488 7.488 0 0 0-5.982 2.975m11.963 0a9 9 0 1 0-11.963 0m11.963 0A8.966 8.966 0 0 1 12 21a8.966 8.966 0 0 1-5.982-2.275M15 9.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                                    </svg>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-white truncate">
                                        {userData?.user_name || "Guest"}
                                    </p>
                                    <p className="text-xs text-white/70 truncate">
                                        Admin
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Navigation Links — all visible */}
                        <nav className="space-y-2">
                            {navLinks.map((link) => (
                                <Link
                                    key={link.href}
                                    href={link.href}
                                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                                        get_current_page === link.href
                                            ? "bg-white/20 text-white font-medium"
                                            : "text-white/80 hover:bg-white/10 hover:text-white"
                                    }`}
                                >
                                    {link.icon}
                                    <span className="text-sm">{link.label}</span>
                                </Link>
                            ))}
                        </nav>
                    </div>
                </aside>
            )}

            {/* Mobile Overlay */}
            {isMenuActive && (
                <div 
                    className="fixed inset-0 bg-black/20 z-30 sm:hidden"
                    onClick={() => setIsMenuActive(false)}
                />
            )}
        </main>
    )
}