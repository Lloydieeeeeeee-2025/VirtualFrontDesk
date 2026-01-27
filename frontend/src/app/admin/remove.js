"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"

export default function Remove({ id, name, link, apiroute }) {
    const router = useRouter()

    const [showModal, setShowModal] = useState(false)

    const removeUser = async (confirmation) => {
        if (confirmation !== "Yes") {
            setShowModal(false)
            return
        }

        try {
            const response = await fetch(apiroute, {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id }),
            })

            const data = await response.json()

            if (response.ok && data.success) {
                setShowModal(false)
                setTimeout(() => {
                    router.push(link)
                }, 1500)
            } else {
                setShowModal(false)
            }
        } catch (err) {
            setShowModal(false)
        }
    }

    return (
        <main>
            <div className="flex m-5">
                <button onClick={() => setShowModal(true)} className="font-medium text-red-500 hover:underline" type="button">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                    </svg>
                </button>
            </div>
            {showModal && (
                <div className="fixed z-70 inset-0 flex items-center justify-center w-full h-full bg-opacity-50 bg-black/30 backdrop-blur-xs overflow-y-auto" onClick={() => setShowModal(false)}>
                    <div className="relative p-4 w-full max-w-md h-full sm:h-auto" onClick={(e) => e.stopPropagation()}>
                        <div className="relative bg-white rounded-lg shadow-sm dark:bg-gray-700">
                            <div className="p-4 md:p-5 text-center">
                                <img className="w-20 sm:w-24 md:w-28 mb-4 object-contain mx-auto" src="/logo/logo.png" alt="Logo" />
                                <h3 className="mb-5 text-lg font-normal text-gray-500 dark:text-gray-400">Do you want to remove {name || id}?</h3>
                                <button onClick={() => removeUser("Yes")} className="text-white bg-red-600 hover:bg-red-800 focus:ring-4 focus:outline-none focus:ring-red-300 dark:focus:ring-red-800 font-medium rounded-md text-sm inline-flex items-center px-5 py-2.5 text-center">Yes</button>
                                <button onClick={() => removeUser("No")} className="py-2.5 px-5 ms-3 text-sm font-medium text-gray-900 focus:outline-none bg-white rounded-md border border-gray-200 hover:bg-gray-100 hover:text-blue-700 focus:z-10 focus:ring-4 focus:ring-gray-100 dark:focus:ring-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600 dark:hover:text-white dark:hover:bg-gray-700">Cancel</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </main>
    )
}