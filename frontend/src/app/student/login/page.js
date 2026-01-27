"use client"

import React, { useState } from 'react';

export default function Login() {
    const [studentNumber, setStudentNumber] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');

        try {
            // temporary disabe ang pag pass ng data sa /api/student/login dahil hold muna
            /*
            const response = await fetch('/api/student/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: studentNumber,
                    password: password
                }),
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Login successful - store session and redirect
                localStorage.setItem('isLoggedIn', 'true');
                localStorage.setItem('studentNumber', studentNumber);
                // Redirect back to FAQs with success
                window.location.href = '/userpage/faqs?login=success';
            } else {
                setError(data.error || 'Login failed. Please check your credentials.');
            }
            */
        } catch (error) {
            setError('An error occurred during login. Please try again.');
            console.error('Login error:', error);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col justify-center py-12 sm:px-6 lg:px-8 px-6">
            <div className="sm:mx-auto sm:w-full sm:max-w-md">
                <img className="mx-auto h-10 w-auto rounded-md" src="/logo/logo.png" alt="App Logo"/>
                <h2 className="mt-6 text-center text-3xl leading-9 font-extrabold text-gray-900">Login your MyTLC account</h2>
            </div>

            <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
                <div className="bg-white py-8 px-4 shadow-sm rounded-xl sm:px-10">
                    {error && (
                        <div className="mb-4 bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-md text-sm">
                            {error}
                        </div>
                    )}
                    
                    <form onSubmit={handleSubmit}>
                        <div>
                            <label htmlFor="studentNumber" className="block text-sm font-medium leading-5 text-gray-700">Student Number</label>
                            <div className="mt-1 relative rounded-md shadow-sm">
                                <input id="studentNumber" name="studentNumber" placeholder="c-2015-0015" type="text" required value={studentNumber} onChange={(e) => setStudentNumber(e.target.value)} className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150 ease-in-out sm:text-sm sm:leading-5" disabled={isLoading}/>
                            </div>
                        </div>

                        <div className="mt-6">
                            <label htmlFor="password" className="block text-sm font-medium leading-5 text-gray-700">Password</label>
                            <div className="mt-1 rounded-md shadow-sm">
                                <input id="password" name="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150 ease-in-out sm:text-sm sm:leading-5" disabled={isLoading}/>
                            </div>
                        </div>

                        <div className="mt-6">
                            <span className="block w-full rounded-md shadow-sm">
                                <button type="submit" disabled={isLoading}className="w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-[#205781] hover:bg-[#205781] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed">
                                    {isLoading ? 'Logging in...' : 'Log in'}
                                </button>
                            </span>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}