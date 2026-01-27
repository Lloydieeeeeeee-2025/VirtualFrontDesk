"use client";

import Navigation from "../navigation";
import { useState, useEffect, useCallback } from "react";
import Update from "./update";
import Create from "./create";
import Remove from "../remove"

export default function URL() {
    const [urls, setUrls] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [isUpdateOpen, setIsUpdateOpen] = useState(false);
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [selectedUrl, setSelectedUrl] = useState(null);
    const [searchData, setSearchData] = useState("");
    const [sortOption, setSortOption] = useState("");

    const closeUpdateModal = useCallback(() => { setIsUpdateOpen(false); setSelectedUrl(null); }, []);
    const openUpdateModal = useCallback((url) => { setSelectedUrl(url); setIsUpdateOpen(true); }, []);
    const openCreateModal = useCallback(() => { setIsCreateOpen(true); }, []);
    const closeCreateModal = useCallback(() => { setIsCreateOpen(false); }, []);

    const search = (e) => { setSearchData(e.target.value); };

    const fetchUrls = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch("/api/admin/url");
            const data = await response.json();
            if (data.success) {
                setUrls(data.data || []);
                setError(null);
            } else {
                setError(data.message || "Failed to load URLs");
            }
        } catch (err) {
            setError("Error fetching URLs");
            console.error("Fetch URLs error:", err);
        } finally {
            setLoading(false);
        }
    };

    const filteredData = urls.filter((row) => {
        const linkUrl = row.link_url ? String(row.link_url).toLowerCase() : "";
        const description = row.description ? String(row.description).toLowerCase() : "";
        const urlId = row.url_id ? String(row.url_id) : "";
        const searchLower = searchData.toLowerCase();
        return linkUrl.includes(searchLower) || description.includes(searchLower) || urlId.includes(searchLower);
    });

    const sortedData = [...filteredData].sort((a, b) => {
        let aValue, bValue;
        switch (sortOption) {
            case "Description Ascending":
                aValue = a.description || "";
                bValue = b.description || "";
                return aValue.localeCompare(bValue);
            case "Description Descending":
                aValue = a.description || "";
                bValue = b.description || "";
                return bValue.localeCompare(aValue);
            default:
                return 0;
        }
    });

    const handleDelete = async (urlId) => {
        if (!confirm("Are you sure you want to delete this URL?")) return;
        try {
            const response = await fetch(`/api/admin/url?url_id=${urlId}`, { method: "DELETE" });
            const data = await response.json();
            if (data.success) {
                fetchUrls();
            } else {
                alert(data.message || "Failed to delete URL");
            }
        } catch (err) {
            alert("Error deleting URL");
            console.error("Delete URL error:", err);
        }
    };

    useEffect(() => { fetchUrls(); }, []);

    return (
        <main className="min-h-screen bg-gray-50">
            <Navigation />
            <div className="pt-16 sm:pt-15 sm:pl-64">
                <div className="p-4 sm:p-6 lg:p-8">
                    <div className="max-w-7xl mx-auto">
                        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
                            <h1 className="text-2xl sm:text-3xl font-bold text-gray-800">URL</h1>
                            <button className="w-full sm:w-auto bg-[#205781] text-white font-medium text-sm sm:text-base hover:bg-[#1a4a6b] py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-sm hover:shadow-md" onClick={openCreateModal}>
                                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" /></svg>
                                <span>Add URL</span>
                            </button>
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
                                                <input type="text" id="table-search" className="w-full h-11 pl-10 pr-4 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#205781]/20 focus:border-[#205781] transition-all duration-200" placeholder="Search by URL, description, or ID" value={searchData} onChange={search} />
                                            </div>
                                        </div>
                                        <div className="sm:w-48">
                                            <label htmlFor="sort-option" className="sr-only">Sort by</label>
                                            <select id="sort-option" className="w-full h-11 px-4 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#205781]/20 focus:border-[#205781] transition-all duration-200" value={sortOption} onChange={(e) => setSortOption(e.target.value)}>
                                                <option value="">Sort by</option>
                                                <option value="Description Ascending">Description (A-Z)</option>
                                                <option value="Description Descending">Description (Z-A)</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div className="flex-1 overflow-x-auto overflow-y-auto">
                                {loading ? (
                                    <div className="flex flex-col justify-center items-center py-16">
                                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#205781]"></div>
                                        <p className="mt-4 text-sm text-gray-500">Loading URLs...</p>
                                    </div>
                                ) : error ? (
                                    <div className="flex flex-col justify-center items-center py-16 px-4">
                                        <svg className="w-12 h-12 text-red-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                        <p className="text-red-600 text-center">Error loading URLs: {error}</p>
                                    </div>
                                ) : sortedData.length === 0 ? (
                                    <div className="flex flex-col justify-center items-center py-16">
                                        <svg className="w-12 h-12 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414A1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" /></svg>
                                        <p className="text-gray-500 text-center">{searchData ? "No matching URLs found" : "No URLs available"}</p>
                                    </div>
                                ) : (
                                    <div className="min-w-full">
                                        <div className="hidden md:block">
                                            <table className="w-full text-sm text-left">
                                                <thead className="text-xs font-semibold text-white uppercase bg-[#205781] sticky top-0 z-10">
                                                    <tr>
                                                        <th scope="col" className="px-6 py-4">Link</th>
                                                        <th scope="col" className="px-6 py-4">Description</th>
                                                        <th scope="col" className="px-6 py-4 text-center"></th>
                                                        <th scope="col" className="px-6 py-4 text-center"></th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-gray-200">
                                                    {sortedData.map((row, index) => (
                                                        <tr key={row.url_id ?? `row-${index}`} className="bg-white hover:bg-gray-50 transition-colors duration-150">
                                                            <td className="px-6 py-4 text-gray-800 font-medium">
                                                                <a href={row.link_url} target="_blank" rel="noopener noreferrer" className=" hover:text-blue-800 hover:underline">
                                                                    {row.link_url ? (row.link_url.length > 50 ? `${row.link_url.substring(0, 50)}...` : row.link_url) : "N/A"}
                                                                </a>
                                                            </td>
                                                            <td className="px-6 py-4 text-gray-600">{row.description}</td>
                                                            <td className="px-6 py-4 text-center">
                                                                <button onClick={() => openUpdateModal(row)} className="p-2 text-[#205781] hover:bg-[#205781]/10 rounded-lg transition-all duration-150" title="Update">
                                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
                                                                </button>
                                                            </td>
                                                            <td className="px-6 py-4 text-center">
                                                                <div className="flex items-center justify-center gap-3">
                                                                    <Remove className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-all duration-150" id={row.url_id} name={row.description} link="/admin/url" apiroute="/api/admin/url" />
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>

                                        <div className="md:hidden divide-y divide-gray-200">
                                            {sortedData.map((row, index) => (
                                                <div key={row.url_id ?? `row-mobile-${index}`} className="p-4 bg-white hover:bg-gray-50 transition-colors duration-150">
                                                    <div className="flex items-start justify-between mb-3">
                                                        <div className="flex-1 min-w-0">
                                                            <h3 className="text-base font-semibold text-gray-800 truncate">{row.link_url ? (row.link_url.length > 40 ? `${row.link_url.substring(0, 40)}...` : row.link_url) : "N/A"}</h3>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <button className="flex items-center justify-center px-4 py-2.5 text-sm font-medium text-[#205781] bg-[#205781]/5 hover:bg-[#205781]/10 rounded-lg transition-all duration-150" onClick={() => openUpdateModal(row)}>
                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4"><path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
                                                            Edit
                                                        </button>
                                                        <button className="flex items-center justify-center px-4 py-2.5 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-all duration-150" onClick={() => handleDelete(row.url_id)}>
                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4"><path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9-.346 9m4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v-.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
                                                            Delete
                                                        </button>
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

            <Update open={isUpdateOpen} close={closeUpdateModal} selectedUrlRow={selectedUrl} onUpdate={fetchUrls} />
            <Create open={isCreateOpen} close={closeCreateModal} onUrlCreated={fetchUrls} />
        </main>
    );
}
