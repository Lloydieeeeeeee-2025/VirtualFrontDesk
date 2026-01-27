"use client"

export default function Navigation() {
    return (
        <main className="fixed top-0 text-gray-600 w-full z-50">
            <header className="w-full flex items-center justify-center gap-2 sm:gap-3 py-3 sm:py-4 bg-white shadow-sm">
                <img className="object-contain h-8 sm:h-10 lg:h-12 w-auto" src="/logo/logo.png" alt="TLC Logo" />
                <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold">
                    <span className="text-[#205781]">TLC ChatMate</span>
                </h1>
            </header>
        </main>
    )
}