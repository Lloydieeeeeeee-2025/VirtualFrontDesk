"use client"

import React, { useEffect, useState } from 'react';
import Navigation from '../navigation';
import ReactMarkdown from "react-markdown"
import Permission from '../permission';

export default function FAQS() {
    const [prompt, setPrompt] = useState("")
    const [messages, setMessages] = useState([])
    const [isLoading, setIsLoading] = useState(false)
    const [conversationSession, setConversationSession] = useState(null)
    const [showPermissionModal, setShowPermissionModal] = useState(false)
    const [authIntent, setAuthIntent] = useState(null)

    const preTypeQuestions = {
        schoolFees: "Know about our Tuition, Miscellaneous and Downpayment",
        enrollmentProcess: "What are the enrollment requirements",
        scholarshipGrant: "List of scholarships"
    }

    useEffect(() => {
        const checkLoginStatus = () => {
            const isLoggedIn = localStorage.getItem('isLoggedIn');
            if (isLoggedIn) {
                console.log('User is logged in');
            }
        };
        checkLoginStatus();
    }, []);

    useEffect(() => {
        if (!conversationSession) {
            setConversationSession('session_' + crypto.randomUUID())
        }
    }, [conversationSession])

    const handleInputChange = (e) => {
        const value = e.target.value;
        if (value.length <= 100) {
            setPrompt(value);
        }
    }

    const handlePaste = (e) => {
        e.preventDefault();
    }

    const UserMessage = ({ message }) => {
        return (
            <div className="flex justify-end mb-6">
                <div className="max-w-[85%] sm:max-w-[75%] bg-gradient-to-br from-[#205781] to-[#2a6ba0] text-white rounded-2xl rounded-br-md px-5 py-3.5 shadow-lg">
                    <div className="text-sm leading-relaxed">{message}</div>
                </div>
            </div>
        )
    }

    const AIMessage = ({ message }) => {
        return (
            <div className="flex justify-start mb-6">
                <div className="max-w-[85%] sm:max-w-[75%] bg-white/80 backdrop-blur-sm rounded-2xl rounded-bl-md px-5 py-3.5 shadow-md border border-gray-100">
                    <div className="text-sm text-gray-600 prose prose-sm max-w-none leading-relaxed">
                        <ReactMarkdown components={{p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />,ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />,li: ({ node, ...props }) => <li className="mb-1" {...props} />,strong: ({ node, ...props }) => <strong className="font-semibold text-gray-800" {...props} />,h1: ({ node, ...props }) => <h1 className="text-lg font-bold mb-2" {...props} />,h2: ({ node, ...props }) => <h2 className="text-base font-bold mb-2" {...props} />,h3: ({ node, ...props }) => <h3 className="text-sm font-bold mb-1" {...props} />,}}>
                            {message}
                        </ReactMarkdown>
                    </div>
                </div>
            </div>
        );
    };

    const handlePreTypeQuestion = (question) => {
        if (isLoading) return;
        handleSubmitQuestion(question);
    };

    const handleSubmitQuestion = async (questionText = null) => {
        const userMessage = questionText || prompt.trim();
        if (userMessage === "" || isLoading) return;

        const newUserMessage = { type: 'user', content: userMessage, id: Date.now() };
        setMessages(prev => [...prev, newUserMessage]);
        
        if (!questionText) {
            setPrompt("");
        }
        
        setIsLoading(true);

        const sessionToUse = conversationSession;

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    prompt: userMessage, 
                    conversationSession: sessionToUse, 
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to get response');
            }

            if (data.requires_auth) {
                setAuthIntent(data.intent);
                setShowPermissionModal(true);
                setMessages(prev => prev.filter(msg => msg.id !== newUserMessage.id));
            } else {
                const aiResponse = data.response || "I don't have enough information to answer that question. Please visit The Lewis College for more details.";

                const newAIMessage = { type: 'ai', content: aiResponse, id: Date.now() + 1 };
                setMessages(prev => [...prev, newAIMessage]);
            }

        } catch (error) {
            console.error("Error:", error);
            const errorMessage = {
                type: 'ai',
                content: "Sorry, there was an error processing your request. Please try again.",
                id: Date.now() + 1,
            }
            setMessages(prev => [...prev, errorMessage])
        } finally {
            setIsLoading(false)
        }
    };

    const submit = async (e) => {
        e.preventDefault();
        handleSubmitQuestion();
    };

    const handlePermissionClose = () => {
        setShowPermissionModal(false);
        setAuthIntent(null);
    };

    const handlePermissionContinue = () => {
        setShowPermissionModal(false);
        window.location.href = '/student/login';
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-white to-blue-50/40">
            <Navigation/>

            {showPermissionModal && (
                <Permission onClose={handlePermissionClose} onContinue={handlePermissionContinue} intent={authIntent}/>
            )}

            <main className="transition-all duration-300 ease-in-out pt-[90px] pb-32">
                <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="text-center my-8 sm:my-12 space-y-6 sm:space-y-8">
                        <div className="space-y-3 sm:space-y-4">
                            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-medium text-gray-600 leading-tight px-2">
                                Good day! How may I assist you today?
                            </h2>
                            <p className="text-base sm:text-lg text-gray-600 max-w-2xl mx-auto px-4 leading-relaxed">
                                You can select from the options below or feel free to type your questions.
                            </p>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5 lg:gap-6 mt-8 sm:mt-10">
                            <button onClick={() => handlePreTypeQuestion(preTypeQuestions.schoolFees)} disabled={isLoading} className="group rounded-2xl bg-white/80 backdrop-blur-sm border-2 border-gray-200 text-left p-5 sm:p-6 hover:shadow-xl hover:shadow-[#205781]/10 transition-all duration-300 hover:border-[#205781]/30 hover:bg-white cursor-pointer transform hover:-translate-y-1 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:hover:border-gray-200 disabled:hover:bg-white/80 min-h-[140px] sm:min-h-[160px]">
                                <div className="flex items-start space-x-3 sm:space-x-4">
                                    <div className="flex-shrink-0 w-11 h-11 sm:w-12 sm:h-12 bg-gradient-to-br from-[#205781]/10 to-[#205781]/5 rounded-xl flex items-center justify-center group-hover:from-[#205781]/20 group-hover:to-[#205781]/10 transition-all duration-300">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 sm:w-6 sm:h-6 text-[#205781]">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z" />
                                        </svg>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="font-semibold text-base sm:text-md mb-2 text-gray-700 group-hover:text-[#205781] transition-colors">
                                            School Fees
                                        </p>
                                        <p className="text-sm text-gray-600 leading-relaxed">
                                            Know about our Tuition, Miscellaneous and Downpayment.
                                        </p>
                                    </div>
                                </div>
                            </button>

                            <button onClick={() => handlePreTypeQuestion(preTypeQuestions.enrollmentProcess)} disabled={isLoading} className="group rounded-2xl bg-white/80 backdrop-blur-sm border-2 border-gray-200 text-left p-5 sm:p-6 hover:shadow-xl hover:shadow-[#205781]/10 transition-all duration-300 hover:border-[#205781]/30 hover:bg-white cursor-pointer transform hover:-translate-y-1 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:hover:border-gray-200 disabled:hover:bg-white/80 min-h-[140px] sm:min-h-[160px]">
                                <div className="flex items-start space-x-3 sm:space-x-4">
                                    <div className="flex-shrink-0 w-11 h-11 sm:w-12 sm:h-12 bg-gradient-to-br from-[#205781]/10 to-[#205781]/5 rounded-xl flex items-center justify-center group-hover:from-[#205781]/20 group-hover:to-[#205781]/10 transition-all duration-300">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 sm:w-6 sm:h-6 text-[#205781]">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z" />
                                        </svg>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="font-semibold text-base sm:text-md mb-2 text-gray-700 group-hover:text-[#205781] transition-colors">
                                            Enrollment
                                        </p>
                                        <p className="text-sm text-gray-600 leading-relaxed">
                                            What are the enrollemnt requirements
                                        </p>
                                    </div>
                                </div>
                            </button>

                            <button onClick={() => handlePreTypeQuestion(preTypeQuestions.scholarshipGrant)} disabled={isLoading} className="group rounded-2xl bg-white/80 backdrop-blur-sm border-2 border-gray-200 text-left p-5 sm:p-6 hover:shadow-xl hover:shadow-[#205781]/10 transition-all duration-300 hover:border-[#205781]/30 hover:bg-white cursor-pointer transform hover:-translate-y-1 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:hover:border-gray-200 disabled:hover:bg-white/80 min-h-[140px] sm:min-h-[160px] sm:col-span-2 lg:col-span-1">
                                <div className="flex items-start space-x-3 sm:space-x-4">
                                    <div className="flex-shrink-0 w-11 h-11 sm:w-12 sm:h-12 bg-gradient-to-br from-[#205781]/10 to-[#205781]/5 rounded-xl flex items-center justify-center group-hover:from-[#205781]/20 group-hover:to-[#205781]/10 transition-all duration-300">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 sm:w-6 sm:h-6 text-[#205781]">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
                                        </svg>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="font-semibold text-base sm:text-md mb-2 text-gray-700 group-hover:text-[#205781] transition-colors">
                                            Scholarship Grant
                                        </p>
                                        <p className="text-sm text-gray-600 leading-relaxed">
                                            Explore our available scholarships and how to apply.
                                        </p>
                                    </div>
                                </div>
                            </button>
                        </div>
                    </div>

                    <div className="space-y-4">
                        {messages.map((message) => {
                            if (message.type === 'user') {
                                return <UserMessage key={message.id} message={message.content} />;
                            }
                            if (message.type === 'ai') {
                                return <AIMessage key={message.id} message={message.content} />;
                            }
                            return null;
                        })}
                        {isLoading && (
                            <div className="flex justify-start mb-6">
                                <div className="max-w-[85%] sm:max-w-[75%] bg-white/80 backdrop-blur-sm rounded-2xl rounded-bl-md px-5 py-3.5 shadow-md border border-gray-100">
                                    <div className="flex items-center space-x-2">
                                        <div className="animate-spin rounded-full h-4 w-4 border-2 border-[#205781] border-t-transparent"></div>
                                        <span className="text-sm text-gray-600"></span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>

            <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-md border-t-2 border-gray-200 shadow-xl z-30">
                <div className="transition-all duration-300 ease-in-out">
                    <div className="max-w-5xl mx-auto p-3 sm:p-4 lg:p-5">
                        <form onSubmit={submit} className="relative">
                            <input className="w-full border-2 border-gray-300 rounded-2xl py-3.5 sm:py-4 px-4 sm:px-6 pr-20 sm:pr-24 focus:ring-4 focus:outline-none focus:ring-[#205781]/10 focus:border-[#205781] text-sm sm:text-base placeholder-gray-500 bg-white transition-all duration-200 shadow-sm" value={prompt} onChange={handleInputChange} onPaste={handlePaste} placeholder="Ask here..." disabled={isLoading} maxLength={100}/>
                            <div className="absolute right-14 sm:right-16 top-1/2 -translate-y-1/2 text-xs text-gray-400 font-medium">
                                {prompt.length}/100
                            </div>
                            <button className="absolute right-2 sm:right-3 top-1/2 -translate-y-1/2 p-2.5 sm:p-3 text-white bg-[#205781] hover:bg-[#1a4660] rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg disabled:hover:bg-[#205781]" type="submit" disabled={isLoading || !prompt.trim()}>
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4 sm:w-5 sm:h-5">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
                                </svg>
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    );
}