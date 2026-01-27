"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"

export default function Success({ save, link }) {
    const [successModal, setSuccessModal] = useState(false)
    const router = useRouter()
    // const toggleSuccessModal = () => setSuccessModal(prev => !prev)

    return (
        <main>
            <div className="flex justify-center m-5">
                <button onClick={async (e) => { const success = await save(e); if (success) setSuccessModal(true) }} className="block bg-white border border-gray-300 hover:bg-gray-100 focus:ring-4 focus:outline-none focus:ring-gray-200 dark:focus:ring-gray-500 font-medium rounded-md text-sm inline-flex items-center p-2" type="submit">
                    Save
                </button>
            </div>

            {successModal && (
                <div className="fixed z-70 inset-0 flex items-center justify-center w-full h-full bg-opacity-50 bg-black/30 backdrop-blur-xs overflow-y-auto">
                    <div className="relative p-4 w-full max-w-md h-full sm:h-auto">
                        <div className="relative bg-white rounded-lg shadow-sm dark:bg-gray-700">
                            <div className="p-4 md:p-5 text-center">
                                <img className="w-20 sm:w-24 md:w-28 mb-4 object-contain mx-auto" src="/logo/logo.png" />
                                <h3 className="mb-5 text-lg font-normal text-gray-500 dark:text-gray-400">
                                    Save Successfully!
                                </h3>

                                <button onClick={() => router.push(link)} className="mx-auto px-8 py-3 bg-gradient-to-r from-[#205781] to-[#2a6ba0] text-white font-semibold rounded-lg hover:from-[#1a4a6b] hover:to-[#235c8a] active:scale-95 transition-all duration-200 ease-in-out transform focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800">
                                    Okay
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </main>
    )
}