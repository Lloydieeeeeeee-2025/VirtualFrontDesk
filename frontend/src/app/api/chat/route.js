import { NextResponse } from "next/server";

export async function POST(request) {
    try {
        // Parse the request body to get the prompt
        const {prompt, conversationSession, username} = await request.json();
        console.log("Received request body:", prompt);

        console.log("Sending to FastAPI:", { prompt: prompt });

        // Send request to FastAPI server
        const chat_response = await fetch('http://127.0.0.1:8000/VirtualFrontDesk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt, conversationSession, username: username  }),
        });

        console.log("FastAPI response status:", chat_response.status);

        // Check if the response is OK
        if (!chat_response.ok) {
            const errorText = await chat_response.text();
            console.log("FastAPI error response:", errorText);
            throw new Error(`HTTP error! status: ${chat_response.status}`);
        }

        const responseData = await chat_response.json();
        console.log("FastAPI success response:", responseData);

        return NextResponse.json({ 
            success: true, 
            response: responseData.response,
            requires_auth: responseData.requires_auth || false,
            intent: responseData.intent || null
        });
        
    } catch (error) {
        console.error('Full error:', error.stack);
        return NextResponse.json({ 
            error: error.message || 'Internal server error' 
        }, { status: 500 });
    }
}