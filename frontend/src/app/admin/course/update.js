"use client"
import { useState, useEffect } from "react"

export default function Update({ open, close, selectedCourseRow, onUpdate }) {
    const [courseDocument, setCourseDocument] = useState(null)
    const [documentName, setDocumentName] = useState("")
    const [documentNameError, setDocumentNameError] = useState("")
    const [courseDocumentError, setCourseDocumentError] = useState("")
    const [updateProgress, setUpdateProgress] = useState(false)

    useEffect(() => {
        if (open && selectedCourseRow) {
            setDocumentName(selectedCourseRow.document_name || "")
            setCourseDocument(null)
            setDocumentNameError("")
            setCourseDocumentError("")
        }
    }, [open, selectedCourseRow])

    const handleFileChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            if (file.type !== "application/pdf") {
                setCourseDocumentError("Only PDF files are allowed")
                setCourseDocument(null)
                return
            }
            if (file.size > 15 * 1024 * 1024) {
                setCourseDocumentError("File size must be less than 15MB")
                setCourseDocument(null)
                return
            }
            setCourseDocument(file)
            setCourseDocumentError("")
        }
    }

    const submit = async () => {
        setDocumentNameError("")
        setCourseDocumentError("")

        let isValid = true

        if (!documentName.trim()) {
            setDocumentNameError("Document name is required")
            isValid = false
        }

        if (!isValid) return

        setUpdateProgress(true)

        try {
            const formData = new FormData()
            formData.append("course_id", selectedCourseRow?.course_id)
            formData.append("document_name", documentName)
            if (courseDocument) {
                formData.append("course_document", courseDocument)
            }

            const res = await fetch("/api/admin/course", {
                method: "PUT",
                body: formData,
            })

            const data = await res.json()

            if (!res.ok) {
                setCourseDocumentError(data.message || "Failed to update course")
                setUpdateProgress(false)
                return
            }

            if (onUpdate) {
                onUpdate()
            }

            setTimeout(() => {
                close()
                setUpdateProgress(false)
            }, 1500)
        } catch (err) {
            setCourseDocumentError("An error occurred while updating the course")
            setUpdateProgress(false)
        }
    }

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
                            <h2 className="text-lg font-semibold mb-2">Update Document</h2>
                            <button onClick={close} className="text-gray-600 hover:text-black">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="w-full flex-1 overflow-y-auto">
                            <div className="space-y-4 md:space-y-6">
                                <div className="space-y-2">
                                    <label htmlFor="documentName" className="block text-sm font-medium text-gray-700">Document Name</label>
                                    <input type="text" id="documentName" name="documentName" className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent rounded-lg" value={documentName} onChange={(e) => setDocumentName(e.target.value)} placeholder="Enter document name" />
                                    {documentNameError && <span className="text-red-600 text-sm mt-1 block">{documentNameError}</span>}
                                </div>
                                <div className="space-y-2">
                                    <label htmlFor="courseDocument" className="block text-sm font-medium text-gray-700">Replace PDF Document (Optional)</label>
                                    <input type="file" id="courseDocument" name="courseDocument" accept=".pdf" onChange={handleFileChange} className="w-full border border-gray-200 p-2 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent rounded-lg" />
                                    <p className="text-xs text-gray-500">Leave empty to keep the current document</p>
                                    {courseDocument && <p className="text-sm text-gray-600">New file: {courseDocument.name}</p>}
                                    {courseDocumentError && <span className="text-red-600 text-sm mt-1 block">{courseDocumentError}</span>}
                                </div>
                            </div>
                        </div>
                    </div>
                    <button className="w-full bg-gray-200 hover:bg-gray-300 transition duration-400 p-2 rounded-lg" onClick={submit} disabled={updateProgress}>{updateProgress ? "Updating..." : "Save"}</button>
                </div>
            </div>
        </main>
    )
}