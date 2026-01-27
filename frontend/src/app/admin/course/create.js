"use client"
import { useState } from "react"

export default function Create({ open, close, onCourseCreated }) {
    const [courseFile, setCourseFile] = useState(null);
    const [fileName, setFileName] = useState("");
    const [fileError, setFileError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            // Check if file is PDF
            if (file.type !== 'application/pdf') {
                setFileError("Please upload a PDF file only");
                setCourseFile(null);
                setFileName("");
                return;
            }
            
            // Check file size (e.g., 10MB limit)
            if (file.size > 10 * 1024 * 1024) {
                setFileError("File size must be less than 10MB");
                setCourseFile(null);
                setFileName("");
                return;
            }

            setFileError("");
            setCourseFile(file);
            setFileName(file.name);
        }
    };

    const submit = async () => {
        if (!courseFile) {
            setFileError("Please select a PDF file");
            return;
        }

        try {
            setLoading(true);
            
            const formData = new FormData();
            formData.append("course_document", courseFile);
            formData.append("document_name", fileName);

            const response = await fetch('/api/admin/course', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (result.success) {
                resetForm();
                close();
                if (onCourseCreated) {
                    onCourseCreated();
                }
            } else {
                setFileError(result.message || "Failed to upload course");
            }
        } catch (error) {
            console.error("Upload error:", error);
            setFileError("Network error. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    const resetForm = () => {
        setCourseFile(null);
        setFileName("");
        setFileError("");
        setLoading(false);
        const fileInput = document.getElementById('courseFile');
        if (fileInput) fileInput.value = '';
    };

    const handleClose = () => {
        resetForm();
        close();
    };

    return (
        <main className="z-500">
            <div className={`fixed inset-0 bg-opacity-20 bg-black/30 backdrop-blur-xs transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`} onClick={handleClose}></div>
            <div className={`fixed top-0 right-0 h-full w-full md:w-[30%] bg-white border-l border-gray-200 transform transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}>
                <div className="flex flex-col h-full p-5 space-y-4">
                    <div>
                        <button onClick={handleClose} className="text-gray-600 hover:text-black">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                    <div className="flex flex-col h-full">
                        <div className="mb-4 w-full flex justify-between items-center">
                            <h2 className="text-lg font-semibold mb-2">Upload New Document</h2>
                            <button onClick={close} className="text-gray-600 hover:text-black">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="w-full flex-1 overflow-y-auto">
                            <div className="space-y-4 md:space-y-6">
                                <div className="space-y-2">
                                    <label htmlFor="courseFile" className="block text-sm font-medium text-gray-700">
                                        Course Document (PDF only)
                                    </label>
                                    <div className="flex items-center justify-center w-full">
                                        <label htmlFor="courseFile" className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100">
                                            <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                                <svg className="w-8 h-8 mb-4 text-gray-500" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 20 16">
                                                    <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 13h3a3 3 0 0 0 0-6h-.025A5.56 5.56 0 0 0 16 6.5 5.5 5.5 0 0 0 5.207 5.021C5.137 5.017 5.071 5 5 5a4 4 0 0 0 0 8h2.167M10 15V6m0 0L8 8m2-2 2 2"/>
                                                </svg>
                                                <p className="mb-2 text-sm text-gray-500">
                                                    <span className="font-semibold">Click to upload</span> or drag and drop
                                                </p>
                                                <p className="text-xs text-gray-500">PDF (MAX. 10MB)</p>
                                            </div>
                                            <input 
                                                id="courseFile" 
                                                type="file" 
                                                className="hidden" 
                                                accept=".pdf,application/pdf"
                                                onChange={handleFileChange}
                                            />
                                        </label>
                                    </div>
                                    {fileName && (
                                        <div className="mt-2 p-2 bg-green-50 border border-green-200 rounded">
                                            <p className="text-sm text-green-700 flex items-center gap-2">
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4">
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m6.75 12-3-3m0 0-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                                                </svg>
                                                Selected: {fileName}
                                            </p>
                                        </div>
                                    )}
                                    {fileError && (
                                        <span className="text-red-600 text-sm mt-1 block">{fileError}</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                    <button 
                        className="w-full bg-[#205781] text-white hover:bg-[#1a4a6b] transition duration-400 p-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed" 
                        onClick={submit}
                        disabled={loading || !courseFile}
                    >
                        {loading ? "Uploading..." : "Upload Course"}
                    </button>
                </div>
            </div>
        </main>
    )
}