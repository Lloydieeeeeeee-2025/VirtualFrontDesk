"use client"
import { useState, useEffect } from "react"

export default function Archive({ open, close, selectedCourseRow, onArchiveChange }) {
    const [archiveProgress, setArchiveProgress] = useState(false)
    const [archiveError, setArchiveError] = useState("")
    const [archivedCourses, setArchivedCourses] = useState([])
    const [loadingArchived, setLoadingArchived] = useState(false)
    const [openDropdownId, setOpenDropdownId] = useState(null)

    const isListView = !selectedCourseRow

    useEffect(() => {
        if (open && isListView) {
            loadArchived()
        }
    }, [open, isListView])

    const loadArchived = async () => {
        setLoadingArchived(true)
        try {
            const res = await fetch("/api/admin/course?view=archived")
            const data = await res.json()
            if (data.success) {
                setArchivedCourses(data.data || [])
            } else {
                setArchiveError("Failed to load archived courses")
            }
        } catch (err) {
            setArchiveError("Error loading archived courses")
        } finally {
            setLoadingArchived(false)
        }
    }

    const handleUnarchive = async (course) => {
        try {
            const res = await fetch("/api/admin/course", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ course_id: course.course_id, action: "unarchive" })
            })
            const data = await res.json()
            if (data.success) {
                if (onArchiveChange) onArchiveChange()
                loadArchived()
                setOpenDropdownId(null)
            } else {
                alert(data.message || "Failed to restore")
            }
        } catch (err) {
            alert("Error restoring course")
        }
    }

    const handleDelete = async (courseId, name) => {
        try {
            const res = await fetch(`/api/admin/course?course_id=${courseId}`, { method: "DELETE" })
            const data = await res.json()
            if (data.success) {
                loadArchived()
                setOpenDropdownId(null)
            } else {
                alert(data.message || "Failed to delete")
            }
        } catch (err) {
            alert("Error deleting course")
        }
    }

    const submitArchive = async () => {
        if (!selectedCourseRow) return
        setArchiveProgress(true)
        setArchiveError("")
        try {
            const res = await fetch("/api/admin/course", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ course_id: selectedCourseRow.course_id, action: "archive" })
            })
            const data = await res.json()
            if (data.success) {
                if (onArchiveChange) onArchiveChange()
                setTimeout(() => {
                    close()
                    setArchiveProgress(false)
                }, 1000)
            } else {
                setArchiveError(data.message || "Failed to archive")
                setArchiveProgress(false)
            }
        } catch (err) {
            setArchiveError("An error occurred while archiving")
            setArchiveProgress(false)
        }
    }

    const toggleDropdown = (courseId) => {
        setOpenDropdownId(openDropdownId === courseId ? null : courseId)
    }

    return (
        <main>
            <div className={`fixed inset-0 bg-opacity-20 bg-black/30 backdrop-blur-xs transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`} onClick={close}></div>
            <div className={`fixed top-0 right-0 h-full w-full md:w-[30%] bg-white border-l border-gray-200 transform transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}>
                <div className="flex flex-col h-full p-5 space-y-4">
                    <div className="flex mt-10 items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-gray-800">
                            {isListView ? "Archived Courses" : "Archive Course"}
                        </h2>
                        <button onClick={close} className="text-gray-600 hover:text-black p-1">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    {isListView ? (
                        <div className="flex-1 overflow-y-auto">
                            {loadingArchived ? (
                                <div className="text-center py-6 text-gray-500">Loading...</div>
                            ) : archivedCourses.length === 0 ? (
                                <div className="text-center py-6 text-gray-500">No archived courses</div>
                            ) : (
                                <section className="flex flex-col justify-center antialiased bg-gray-50 text-gray-600 min-h-screen p-0">
                                    <div className="h-full">
                                        <div className="relative max-w-[340px] mx-auto bg-white shadow-lg rounded-lg">
                                            <div className="py-3 px-5">
                                                <h3 className="text-xs font-semibold uppercase text-gray-400 mb-1">Archived</h3>
                                                <div className="divide-y divide-gray-200">
                                                    {archivedCourses.map((course) => (
                                                        <div key={course.course_id} className="py-2 relative">
                                                            <div
                                                                className="flex justify-between items-center cursor-pointer hover:bg-gray-50 px-2 py-1 rounded"
                                                                onClick={() => toggleDropdown(course.course_id)}
                                                            >
                                                                <span className="truncate text-sm">{course.document_name}</span>
                                                            </div>
                                                            {openDropdownId === course.course_id && (
                                                                <div className="mt-1 w-full bg-white border border-gray-200 rounded shadow-lg z-10">
                                                                    <button
                                                                        onClick={() => handleUnarchive(course)}
                                                                        className="block w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-blue-50"
                                                                    >
                                                                        Unarchive
                                                                    </button>
                                                                    <button
                                                                        onClick={() => handleDelete(course.course_id, course.document_name)}
                                                                        className="block w-full text-left px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
                                                                    >
                                                                        Delete
                                                                    </button>
                                                                </div>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </section>
                            )}
                        </div>
                    ) : (
                        <div className="flex-1 overflow-y-auto">
                            <p>Are you sure you want to archive <strong>{selectedCourseRow?.document_name}</strong>?</p>
                        </div>
                    )}

                    {archiveError && (
                        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                            <p className="text-sm text-red-600">{archiveError}</p>
                        </div>
                    )}

                    <div className="flex gap-3 pt-4 border-t border-gray-200">
                        <button
                            className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-800 transition duration-400 py-3 rounded-lg font-medium text-sm"
                            onClick={close}
                            disabled={archiveProgress}
                        >
                            Cancel
                        </button>
                        {!isListView && (
                            <button
                                className="flex-1 bg-[#205781] hover:bg-[#1a4a6b] text-white transition duration-400 py-3 rounded-lg font-medium text-sm"
                                onClick={submitArchive}
                                disabled={archiveProgress}
                            >
                                {archiveProgress ? "Archiving..." : "Archive"}
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </main>
    )
}