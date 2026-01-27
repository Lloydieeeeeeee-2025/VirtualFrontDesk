import { NextResponse } from "next/server";
import { chatmate } from "../../../../../library/tlcchatmatedb/route";



export async function GET() {
    try {

        const [rows] = await chatmate.execute("SELECT * FROM URL ORDER BY url_id DESC");

        return NextResponse.json({ success: true, data: rows });
    } catch (error) {
        console.error("Error fetching URLs:", error);
        return NextResponse.json({ success: false, message: "Failed to fetch URLs" }, { status: 500 });
    }
}

export async function POST(request) {
    try {
        const { link_url, description } = await request.json();

        if (!link_url) {
            return NextResponse.json({ success: false, message: "URL is required" }, { status: 400 });
        }

        const [result] = await chatmate.execute(
            "INSERT INTO URL (link_url, description) VALUES (?, ?)",
            [link_url, description || null]
        );

        return NextResponse.json({ success: true, data: { url_id: result.insertId } });
    } catch (error) {
        console.error("Error creating URL:", error);
        return NextResponse.json({ success: false, message: "Failed to create URL" }, { status: 500 });
    }
}

export async function PUT(request) {
    try {
        const { url_id, link_url, description } = await request.json();

        if (!url_id || !link_url) {
            return NextResponse.json({ success: false, message: "URL ID and link URL are required" }, { status: 400 });
        }

        await chatmate.execute(
            "UPDATE URL SET link_url = ?, description = ? WHERE url_id = ?",
            [link_url, description || null, url_id]
        );

        return NextResponse.json({ success: true, message: "URL updated successfully" });
    } catch (error) {
        console.error("Error updating URL:", error);
        return NextResponse.json({ success: false, message: "Failed to update URL" }, { status: 500 });
    }
}

export async function DELETE(request) {
    try {
        const { id } = await request.json();

        if (!id) {
            return NextResponse.json({ success: false, message: "URL ID is required" }, { status: 400 });
        }

        await chatmate.execute("DELETE FROM URL WHERE url_id = ?", [id]);


        return NextResponse.json({ success: true, message: "URL deleted successfully" });
    } catch (error) {
        console.error("Error deleting URL:", error);
        return NextResponse.json({ success: false, message: "Failed to delete URL" }, { status: 500 });
    }
}