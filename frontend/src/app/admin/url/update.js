"use client"
import { useState, useEffect } from "react"

export default function Update({ open, close, selectedUrlRow }) {
    const [linkUrl, setLinkUrl] = useState("")
    const [linkUrlError, setLinkUrlError] = useState("")
    const [description, setDescription] = useState("")

    useEffect(() => {
        if (open && selectedUrlRow) {
            console.log("Update - selectedUrlRow:", selectedUrlRow)
            setLinkUrl(selectedUrlRow.link_url || "")
            setDescription(selectedUrlRow.description || "")
            setLinkUrlError("")
        }
    }, [open, selectedUrlRow])

    const submit = async () => {
        setLinkUrlError("")

        if (!linkUrl) {
            setLinkUrlError("Please enter a valid URL.")
            return
        }

        try {
            const payload = {
                url_id: selectedUrlRow?.url_id,
                link_url: linkUrl,
                description: description || null,
            }
            console.log("Update - payload:", payload)
            const res = await fetch("/api/admin/url", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })
            const data = await res.json()
            if (!res.ok) {
                if (res.status === 400) {
                    setLinkUrlError(data.message || "Invalid input.")
                } else {
                    setLinkUrlError(data.message || "An unexpected error occurred.")
                }
                return
            }
            setTimeout(() => {
                close()
                window.location.reload()
            }, 1500)
        } catch (err) {
            console.error("Update - Error:", err.message)
            setLinkUrlError("An error occurred while updating the URL.")
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
                            <h2 className="text-lg font-semibold mb-2">Update URL</h2>
                            <button onClick={close} className="text-gray-600 hover:text-black">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="w-full flex-1 overflow-y-auto">
                            <div className="space-y-4 md:space-y-6">
                                <div className="space-y-2">
                                    <label htmlFor="linkUrl" className="block text-sm font-medium text-gray-700">Link URL</label>
                                    <input type="url" id="linkUrl" name="linkUrl" value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} placeholder="https://example.com" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent" />
                                    {linkUrlError && (
                                        <span className="text-red-600 text-sm mt-1 block">{linkUrlError}</span>
                                    )}
                                </div>
                                <div className="space-y-2">
                                    <label htmlFor="description" className="block text-sm font-medium text-gray-700">Description</label>
                                    <input id="description" name="description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Enter URL description" rows="4" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent"/>
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