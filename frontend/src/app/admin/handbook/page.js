"use client"
import React, { useState, useCallback, useEffect } from 'react';
import HandbookUpdate from './update';
import HandbookCreate from './create';
import Navigation from "../navigation";
import Archive from './archive';

export default function Handbook() {
    const [handbooks, setHandbooks] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [isUpdateOpen, setIsUpdateOpen] = useState(false);
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isArchiveOpen, setIsArchiveOpen] = useState(false);
    const [selectedHandbook, setSelectedHandbook] = useState(null);
    const [searchData, setSearchData] = useState("");
    const [sortOption, setSortOption] = useState("");
    const [openDropdownId, setOpenDropdownId] = useState(null);

    const closeUpdateModal = useCallback(() => { setIsUpdateOpen(false); setSelectedHandbook(null); }, []);
    const openUpdateModal = useCallback((handbook) => { setSelectedHandbook(handbook); setIsUpdateOpen(true); setOpenDropdownId(null); }, []);
    const openCreateModal = useCallback(() => { setIsCreateOpen(true); }, []);
    const closeCreateModal = useCallback(() => { setIsCreateOpen(false); }, []);
    const openArchiveModal = useCallback((handbook) => { setSelectedHandbook(handbook); setIsArchiveOpen(true); setOpenDropdownId(null); }, []);
    const openArchiveListModal = useCallback(() => { setSelectedHandbook(null); setIsArchiveOpen(true); }, []);
    const closeArchiveModal = useCallback(() => { setIsArchiveOpen(false); setSelectedHandbook(null); }, []);

    const search = (e) => { setSearchData(e.target.value); };

    const toggleDropdown = (handbookId) => {
        setOpenDropdownId(openDropdownId === handbookId ? null : handbookId);
    };

    const fetchHandbooks = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch("/api/admin/handbook?view=active");
            const data = await response.json();
            if (data.success) {
                setHandbooks(data.data || []);
            } else {
                setError(data.message || "Failed to load handbooks");
            }
        } catch (err) {
            setError("Error fetching handbooks");
            console.error("Fetch handbooks error:", err);
        } finally {
            setLoading(false);
        }
    };

    const filteredData = handbooks.filter((row) => {
        const handbookName = row.handbook_name ? String(row.handbook_name).toLowerCase() : "";
        const handbookId = row.handbook_id ? String(row.handbook_id) : "";
        const searchLower = searchData.toLowerCase();
        return handbookName.includes(searchLower) || handbookId.includes(searchLower);
    });

    const sortedData = [...filteredData].sort((a, b) => {
        let aValue, bValue;
        switch (sortOption) {
            case "Name Ascending":
                aValue = a.handbook_name || "";
                bValue = b.handbook_name || "";
                return aValue.localeCompare(bValue);
            case "Name Descending":
                aValue = a.handbook_name || "";
                bValue = b.handbook_name || "";
                return bValue.localeCompare(aValue);
            default:
                return 0;
        }
    });

    const handleArchive = async (handbookId) => {
        if (!confirm("Archive this handbook? It will be hidden from the main list.")) return;
        try {
            const res = await fetch("/api/admin/handbook", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ handbook_id: handbookId, action: "archive" })
            });
            const data = await res.json();
            if (data.success) {
                fetchHandbooks();
                setOpenDropdownId(null);
            } else {
                alert(data.message || "Failed to archive");
            }
        } catch (err) {
            alert("Error archiving handbook");
        }
    };

    const handleViewDocument = async (handbookId, handbookName) => {
        try {
            const response = await fetch(`/api/admin/handbook?handbook_id=${handbookId}`);
            const data = await response.json();
            if (data.success && data.data.handbook_document) {
                const byteCharacters = atob(data.data.handbook_document);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: 'application/pdf' });
                const url = URL.createObjectURL(blob);
                window.open(url, '_blank');
            } else {
                alert("Failed to load document");
            }
        } catch (err) {
            alert("Error loading document");
        }
    };

    const handleDownloadDocument = async (handbookId, handbookName) => {
        try {
            const response = await fetch(`/api/admin/handbook?handbook_id=${handbookId}`);
            const data = await response.json();
            if (data.success && data.data.handbook_document) {
                const byteCharacters = atob(data.data.handbook_document);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: 'application/pdf' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = handbookName;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                setOpenDropdownId(null);
            } else {
                alert("Failed to load document for download");
            }
        } catch (err) {
            alert("Error downloading document");
        }
    };

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (openDropdownId && !e.target.closest(`[data-dropdown="${openDropdownId}"]`)) {
                setOpenDropdownId(null);
            }
        };
        document.addEventListener('click', handleClickOutside);
        return () => document.removeEventListener('click', handleClickOutside);
    }, [openDropdownId]);

    useEffect(() => { fetchHandbooks(); }, []);

    const handleDelete = async (handbookId) => {
        if (!confirm("Are you sure you want to permanently delete this handbook? This action cannot be undone.")) return;
        try {
            const res = await fetch(`/api/admin/handbook?handbook_id=${handbookId}`, {
                method: "DELETE"
            });
            const data = await res.json();
            if (data.success) {
                fetchHandbooks(); // Refresh the list
                setOpenDropdownId(null);
            } else {
                alert(data.message || "Failed to delete handbook");
            }
        } catch (err) {
            alert("Error deleting handbook");
            console.error("Delete error:", err);
        }
    };

    return (
        <main className="min-h-screen bg-gray-50">
            <Navigation />
            <div className="pt-16 sm:pt-15 sm:pl-64">
                <div className="p-4 sm:p-6 lg:p-8">
                    <div className="max-w-7xl mx-auto">
                        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
                            <h1 className="text-2xl sm:text-3xl font-bold text-gray-800">Handbook</h1>
                            <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                                <button className="flex items-center justify-center gap-2 w-full sm:w-auto bg-[#205781] text-white text-sm sm:text-base hover:bg-[#1a4a6b] py-2 px-2 rounded-lg transition-all duration-200 shadow-sm hover:shadow-md" onClick={openArchiveListModal}>
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z" />
                                    </svg>
                                    <span>Archived</span>
                                </button>
                                <button className="flex items-center justify-center gap-2 w-full sm:w-auto bg-[#205781] text-white text-sm sm:text-base hover:bg-[#1a4a6b] py-2 px-2 rounded-lg transition-all duration-200 shadow-sm hover:shadow-md" onClick={openCreateModal}>
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                                    </svg>
                                    <span>Upload Document</span>
                                </button>
                            </div>
                        </div>
                        <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200 h-[73vh] flex flex-col overflow-hidden">
                            {!isCreateOpen && (
                                <div className="p-4 sm:p-6 border-b border-gray-200 sticky top-0 z-10 bg-white/90 backdrop-blur-sm">
                                    <div className="flex flex-col sm:flex-row gap-4">
                                        <div className="flex-1">
                                            <label htmlFor="table-search" className="sr-only">Search</label>
                                            <div className="relative">
                                                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                                                    <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="m19 19-4-4m0-7A7 7 0 1 1 1 8a7 7 0 0 1 14 0Z" /></svg>
                                                </div>
                                                <input type="text" id="table-search" className="w-full h-11 pl-10 pr-4 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#205781]/20 focus:border-[#205781] transition-all duration-200" placeholder="Search by handbook name" value={searchData} onChange={search} />
                                            </div>
                                        </div>
                                        <div className="sm:w-48">
                                            <label htmlFor="sort-option" className="sr-only">Sort by</label>
                                            <select id="sort-option" className="w-full h-11 px-4 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#205781]/20 focus:border-[#205781] transition-all duration-200" value={sortOption} onChange={(e) => setSortOption(e.target.value)}>
                                                <option value="">Sort by</option>
                                                <option value="Name Ascending">Name (A-Z)</option>
                                                <option value="Name Descending">Name (Z-A)</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            )}
                            <div className="flex-1 overflow-x-auto overflow-y-auto">
                                {loading ? (
                                    <div className="flex flex-col justify-center items-center py-16">
                                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#205781]"></div>
                                        <p className="mt-4 text-sm text-gray-500">Loading handbooks...</p>
                                    </div>
                                ) : error ? (
                                    <div className="flex flex-col justify-center items-center py-16 px-4">
                                        <svg className="w-12 h-12 text-red-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                        <p className="text-red-600 text-center">Error loading handbooks: {error}</p>
                                    </div>
                                ) : sortedData.length === 0 ? (
                                    <div className="flex flex-col justify-center items-center py-16">
                                        <svg className="w-12 h-12 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" /></svg>
                                        <p className="text-gray-500 text-center">{searchData ? "No matching handbooks found" : "No handbooks uploaded yet"}</p>
                                    </div>
                                ) : (
                                    <div className="min-w-full">
                                        <div className="hidden md:block">
                                            <table className="w-full text-sm text-left">
                                                <thead className="text-xs font-semibold text-white uppercase bg-[#205781] sticky top-0 z-10">
                                                    <tr>
                                                        <th scope="col" className="px-6 py-4">Documents</th>
                                                        <th scope="col" className="px-6 py-4 text-center">Actions</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-gray-200">
                                                    {sortedData.map((handbook, index) => (
                                                        <tr key={handbook.handbook_id ?? `handbook-${index}`} className="bg-white hover:bg-gray-50 transition-colors duration-150">
                                                            <td className="px-6 py-4 text-gray-800 font-medium">
                                                                <button onClick={() => handleViewDocument(handbook.handbook_id, handbook.handbook_name)} className="text-gray-600 hover:[#205781]/10 hover:underline">
                                                                    {handbook.handbook_name}
                                                                </button>
                                                            </td>
                                                            <td className="px-6 py-4 text-center relative" data-dropdown={handbook.handbook_id}>
                                                                <div className="relative flex justify-center">
                                                                    <button onClick={() => toggleDropdown(handbook.handbook_id)} className="p-2 text-[#205781] hover:bg-[#205781]/10 rounded-lg transition-all duration-150">
                                                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                                                            <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                                                                        </svg>
                                                                    </button>
                                                                    {openDropdownId === handbook.handbook_id && (
                                                                        <div className="origin-top-right absolute top-full right-0 mt-1 w-56 bg-white border border-slate-200 rounded-lg shadow-xl z-20">
                                                                            <ul className="py-1">
                                                                                <li>
                                                                                    <button onClick={() => handleDownloadDocument(handbook.handbook_id, handbook.handbook_name)} className="w-full text-left text-slate-800 hover:bg-slate-50 flex items-center p-3">
                                                                                        <div className="flex items-center justify-center bg-white border border-slate-200 rounded shadow-sm h-7 w-7 shrink-0 mr-3">
                                                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4">
                                                                                                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
                                                                                            </svg>
                                                                                        </div>
                                                                                        <span className="whitespace-nowrap text-sm">Download</span>
                                                                                    </button>
                                                                                </li>
                                                                                <li>
                                                                                    <button onClick={() => handleArchive(handbook.handbook_id)} className="w-full text-left text-slate-800 hover:bg-slate-50 flex items-center p-3">
                                                                                        <div className="flex items-center justify-center bg-white border border-slate-200 rounded shadow-sm h-7 w-7 shrink-0 mr-3">
                                                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4">
                                                                                                <path strokeLinecap="round" strokeLinejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z" />
                                                                                            </svg>
                                                                                        </div>
                                                                                        <span className="whitespace-nowrap text-sm">Archive</span>
                                                                                    </button>
                                                                                </li>
                                                                                <li>
                                                                                    <button onClick={() => openUpdateModal(handbook)} className="w-full text-left text-slate-800 hover:bg-slate-50 flex items-center p-3">
                                                                                        <div className="flex items-center justify-center bg-white border border-slate-200 rounded shadow-sm h-7 w-7 shrink-0 mr-3">
                                                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4">
                                                                                                <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
                                                                                            </svg>
                                                                                        </div>
                                                                                        <span className="whitespace-nowrap text-sm">Update</span>
                                                                                    </button>
                                                                                </li>
                                                                            </ul>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>

                                        {/* Mobile View */}
                                        <div className="md:hidden divide-y divide-gray-200">
                                            {sortedData.map((handbook, index) => (
                                                <div key={handbook.handbook_id ?? `handbook-mobile-${index}`} className="p-4 bg-white hover:bg-gray-50 transition-colors duration-150">
                                                    <div className="flex items-start justify-between mb-3">
                                                        <div className="flex-1 min-w-0">
                                                            <h3 className="text-base font-semibold text-gray-800 truncate">{handbook.handbook_name}</h3>
                                                        </div>
                                                        <div className="relative ml-2" data-dropdown={handbook.handbook_id}>
                                                            <button onClick={() => toggleDropdown(handbook.handbook_id)} className="p-2 text-[#205781] hover:bg-[#205781]/10 rounded-lg">
                                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-5">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                                                                </svg>
                                                            </button>
                                                            {openDropdownId === handbook.handbook_id && (
                                                                <div className="origin-top-right absolute right-0 mt-1 w-48 bg-white border border-slate-200 rounded-lg shadow-xl z-20">
                                                                    <ul className="py-1">
                                                                        <li>
                                                                            <button onClick={() => handleViewDocument(handbook.handbook_id, handbook.handbook_name)} className="w-full text-left text-slate-800 hover:bg-slate-50 flex items-center p-3 text-sm">
                                                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4 mr-3">
                                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                                                                                </svg>
                                                                                <span>View</span>
                                                                            </button>
                                                                        </li>
                                                                        <li>
                                                                            <button onClick={() => handleDownloadDocument(handbook.handbook_id, handbook.handbook_name)} className="w-full text-left text-slate-800 hover:bg-slate-50 flex items-center p-3 text-sm">
                                                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4 mr-3">
                                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
                                                                                </svg>
                                                                                <span>Download</span>
                                                                            </button>
                                                                        </li>
                                                                        <li>
                                                                            <button onClick={() => handleArchive(handbook.handbook_id)} className="w-full text-left text-slate-800 hover:bg-slate-50 flex items-center p-3 text-sm">
                                                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4 mr-3">
                                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z" />
                                                                                </svg>
                                                                                <span>Archive</span>
                                                                            </button>
                                                                        </li>
                                                                        <li>
                                                                            <button onClick={() => openUpdateModal(handbook)} className="w-full text-left text-slate-800 hover:bg-slate-50 flex items-center p-3 text-sm">
                                                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4 mr-3">
                                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
                                                                                </svg>
                                                                                <span>Update</span>
                                                                            </button>
                                                                        </li>
                                                                        <li>
                                                                            <button
                                                                                onClick={() => handleDelete(handbook.handbook_id)}
                                                                                className="w-full text-left text-red-600 hover:bg-red-50 flex items-center p-3"
                                                                            >
                                                                                <div className="flex items-center justify-center bg-white border border-slate-200 rounded shadow-sm h-7 w-7 shrink-0 mr-3">
                                                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4">
                                                                                        <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                                                                                    </svg>
                                                                                </div>
                                                                                <span className="whitespace-nowrap text-sm">Delete</span>
                                                                            </button>
                                                                        </li>
                                                                    </ul>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <HandbookUpdate open={isUpdateOpen} close={closeUpdateModal} selectedHandbookRow={selectedHandbook} onUpdate={fetchHandbooks} />
            <HandbookCreate open={isCreateOpen} close={closeCreateModal} onHandbookCreated={fetchHandbooks} />
            <Archive open={isArchiveOpen} close={closeArchiveModal} selectedHandbookRow={selectedHandbook} onArchiveChange={fetchHandbooks} />
        </main>
    );
}