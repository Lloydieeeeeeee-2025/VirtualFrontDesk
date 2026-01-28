"use client"
import Navigation from "../navigation"
import { useState, useEffect, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import Remove from "../remove"
import Update from "./update"
import Create from "./create"

function UsersContent() {
    const [accountsSettingsModal, setAccountsSettingsModal] = useState(false)
    const [addModal, setAddModal] = useState(false)
    const [editAccountModal, setEditAccountModal] = useState(false)
    const [selectedAccountRow, setSelectedAccountRow] = useState(null)
    const [users, setUsers] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchData, setSearchData] = useState("")
    const [sortOption, setSortOption] = useState("")
    const searchParams = useSearchParams()

    useEffect(() => {
        const showModal = searchParams.get("showModal") === "true"
        setAccountsSettingsModal(showModal)
    }, [searchParams])

    useEffect(() => {
        const fetchUsers = async () => {
            setLoading(true)
            try {
                const response = await fetch("/api/admin/users")
                if (!response.ok) throw new Error("Failed to fetch users")
                const data = await response.json()
                if (data.success) {
                    setUsers(data.data)
                    setError(null)
                } else {
                    throw new Error(data.message || "Failed to fetch users")
                }
            } catch (err) {
                console.error(err)
                setError(err.message)
                setUsers([])
            } finally {
                setLoading(false)
            }
        }
        fetchUsers()
    }, [])

    const search = (e) => { setSearchData(e.target.value) }

    const filteredData = users.filter((row) => {
        const userName = row.user_name ? String(row.user_name).toLowerCase() : ""
        const userEmail = row.user_email ? String(row.user_email).toLowerCase() : ""
        const userId = row.user_id ? String(row.user_id) : ""
        const searchLower = searchData.toLowerCase()
        return (userName.includes(searchLower) || userEmail.includes(searchLower) || userId.includes(searchLower))
    })

    const sortedData = [...filteredData].sort((a, b) => {
        let aValue, bValue
        switch (sortOption) {
            case "Name Ascending":
                aValue = a.user_name || ""
                bValue = b.user_name || ""
                return aValue.localeCompare(bValue)
            case "Name Descending":
                aValue = a.user_name || ""
                bValue = b.user_name || ""
                return bValue.localeCompare(aValue)
            case "Email Ascending":
                aValue = a.user_email || ""
                bValue = b.user_email || ""
                return aValue.localeCompare(bValue)
            case "Email Descending":
                aValue = a.user_email || ""
                bValue = b.user_email || ""
                return bValue.localeCompare(aValue)
            case "ID Ascending":
                aValue = a.user_id || 0
                bValue = b.user_id || 0
                return aValue - bValue
            case "ID Descending":
                aValue = a.user_id || 0
                bValue = b.user_id || 0
                return bValue - aValue
            default:
                return 0
        }
    })

    const editAccountRow = (user) => {
        setSelectedAccountRow(user)
        setEditAccountModal(true)
    }

    return (
        <main className="min-h-screen bg-gray-50">
            <Navigation />
            <div className="pt-16 sm:pt-15 sm:pl-64">
                <div className="p-4 sm:p-6 lg:p-8">
                    <div className="max-w-7xl mx-auto">
                        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
                            <h1 className="text-2xl sm:text-3xl font-bold text-gray-800">Users</h1>
                            <button className="w-full sm:w-auto bg-[#205781] text-white font-medium text-sm sm:text-base hover:bg-[#1a4a6b] py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-sm hover:shadow-md" onClick={() => setAddModal(true)}>
                                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" /></svg>
                                <span>Add User</span>
                            </button>
                        </div>
                        <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200 h-[73vh] flex flex-col overflow-hidden">
                            {!addModal && (
                                <div className="p-4 sm:p-6 border-b border-gray-200 sticky top-0 z-10 bg-white/90 backdrop-blur-sm">
                                    <div className="flex flex-col sm:flex-row gap-4">
                                        <div className="flex-1">
                                            <label htmlFor="table-search" className="sr-only">Search</label>
                                            <div className="relative">
                                                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                                                    <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="m19 19-4-4m0-7A7 7 0 1 1 1 8a7 7 0 0 1 14 0Z" /></svg>
                                                </div>
                                                <input type="text" id="table-search" className="w-full h-11 pl-10 pr-4 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#205781]/20 focus:border-[#205781] transition-all duration-200" placeholder="Search by name or email" value={searchData} onChange={search} />
                                            </div>
                                        </div>
                                        <div className="sm:w-48">
                                            <label htmlFor="sort-option" className="sr-only">Sort by</label>
                                            <select id="sort-option" className="w-full h-11 px-4 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#205781]/20 focus:border-[#205781] transition-all duration-200" value={sortOption} onChange={(e) => setSortOption(e.target.value)}>
                                                <option value="">Sort by</option>
                                                <option value="Name Ascending">Name (A-Z)</option>
                                                <option value="Name Descending">Name (Z-A)</option>
                                                <option value="Email Ascending">Email (A-Z)</option>
                                                <option value="Email Descending">Email (Z-A)</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            )}
                            <div className="flex-1 overflow-x-auto overflow-y-auto">
                                {loading ? (
                                    <div className="flex flex-col justify-center items-center py-16">
                                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#205781]"></div>
                                        <p className="mt-4 text-sm text-gray-500">Loading users...</p>
                                    </div>
                                ) : error ? (
                                    <div className="flex flex-col justify-center items-center py-16 px-4">
                                        <svg className="w-12 h-12 text-red-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                        <p className="text-red-600 text-center">Error loading users: {error}</p>
                                    </div>
                                ) : sortedData.length === 0 ? (
                                    <div className="flex flex-col justify-center items-center py-16">
                                        <svg className="w-12 h-12 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414A1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" /></svg>
                                        <p className="text-gray-500 text-center">{searchData ? "No matching users found" : "No users available"}</p>
                                    </div>
                                ) : (
                                    <div className="min-w-full">
                                        <div className="hidden md:block">
                                            <table className="w-full text-sm text-left">
                                                <thead className="text-xs font-semibold text-white uppercase bg-[#205781] sticky top-0 z-10">
                                                    <tr>
                                                        <th scope="col" className="px-6 py-4">Name</th>
                                                        <th scope="col" className="px-6 py-4">Email</th>
                                                        <th scope="col" className="px-6 py-4 text-center"></th>
                                                        <th scope="col" className="px-6 py-4 text-center"></th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-gray-200">
                                                    {sortedData.map((user) => (
                                                        <tr key={user.user_id} className="bg-white hover:bg-gray-50 transition-colors duration-150">
                                                            <td className="px-6 py-4 text-gray-800 font-medium">{user.user_name}</td>
                                                            <td className="px-6 py-4 text-gray-600">{user.user_email}</td>
                                                            <td className="px-6 py-4">
                                                                <div className="flex items-center justify-center gap-3">
                                                                    <button className="p-2 text-[#205781] hover:bg-[#205781]/10 rounded-lg transition-all duration-150" onClick={() => editAccountRow(user)} aria-label="Edit user">
                                                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
                                                                    </button>
                                                                </div>
                                                            </td>
                                                            <td className="px-6 py-4">
                                                                <div className="flex items-center justify-center gap-3">
                                                                    <Remove className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-all duration-150" id={user.user_id} name={user.user_name} link="/admin/users" apiroute="/api/admin/users" />
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                        <div className="md:hidden divide-y divide-gray-200">
                                            {sortedData.map((user) => (
                                                <div key={user.user_id} className="p-4 bg-white hover:bg-gray-50 transition-colors duration-150">
                                                    <div className="flex items-start justify-between mb-3">
                                                        <div className="flex-1 min-w-0">
                                                            <h3 className="text-base font-semibold text-gray-800 truncate">{user.user_name}</h3>
                                                            <p className="text-sm text-gray-600 truncate mt-1">{user.user_email}</p>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <button className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-[#205781] bg-[#205781]/5 hover:bg-[#205781]/10 rounded-lg transition-all duration-150" onClick={() => editAccountRow(user)}>
                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4"><path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
                                                            Edit
                                                        </button>
                                                        <Remove className="flex items-center justify-center px-4 py-2.5 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-all duration-150" id={user.user_id} name={user.user_name} link="/admin/users" apiroute="/api/admin/users" />
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
            <Create open={addModal} close={() => setAddModal(false)} />
            <Update open={editAccountModal} close={() => setEditAccountModal(false)} selectedAccountRow={selectedAccountRow} />
        </main>
    )
}

export default function Users() {
    return (
        <Suspense fallback={<div className="flex items-center justify-center min-h-screen"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#205781]"></div></div>}>
            <UsersContent />
        </Suspense>
    )
}