import { NextResponse } from "next/server";

export async function POST(request) {
    try {
        const { username, password } = await request.json();
        
        console.log("Attempting login for:", username);

        // Send credentials to FastAPI for validation via DataScraping
        const loginResponse = await fetch('http://127.0.0.1:8000/student/login', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                username: username, 
                password: password 
            }),
        });

        const data = await loginResponse.json();
        console.log("FastAPI login response:", data);

        if (data.success) {
            return NextResponse.json({ 
                success: true, 
                message: 'Login successful' 
            });
        } else {
            return NextResponse.json({ 
                success: false, 
                error: data.error || 'Invalid credentials' 
            }, { status: 401 });
        }
        
    } catch (error) {
        console.error('Login API error:', error);
        return NextResponse.json({ 
            error: 'Internal server error during login' 
        }, { status: 500 });
    }
}