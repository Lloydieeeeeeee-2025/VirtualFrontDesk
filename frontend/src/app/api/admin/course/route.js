import { chatmate } from "../../../../../library/tlcchatmatedb/route";
import { NextResponse } from "next/server";

export async function POST(req) {
    try {
        const formData = await req.formData();
        const courseDocument = formData.get("course_document");
        const documentName = formData.get("document_name");

        if (!courseDocument || !documentName) {
            return NextResponse.json({ success: false, message: "Course document and name are required" }, { status: 400 });
        }

        const bytes = await courseDocument.arrayBuffer();
        const buffer = Buffer.from(bytes);
        const base64Document = buffer.toString("base64");

        const query = "INSERT INTO Course (course_document, document_name) VALUES (?, ?)";
        const [result] = await chatmate.query(query, [base64Document, documentName]);

        return NextResponse.json({ success: true, message: "Course uploaded successfully", data: { course_id: result.insertId } }, { status: 201 });
    } catch (err) {
        console.error("Error uploading course:", err);
        return NextResponse.json({ success: false, message: "Failed to upload course" }, { status: 500 });
    }
}

export async function GET(req) {
    try {
        const { searchParams } = new URL(req.url);
        const courseId = searchParams.get("course_id");
        const view = searchParams.get("view"); // 'active' or 'archived'

        if (courseId) {
            const query = "SELECT * FROM Course WHERE course_id = ?";
            const [result] = await chatmate.query(query, [courseId]);
            if (result.length === 0) {
                return NextResponse.json({ success: false, message: "Course not found" }, { status: 404 });
            }
            let course = result[0];
            if (course.course_document) course.course_document = course.course_document.toString("utf8");
            return NextResponse.json({ success: true, data: course }, { status: 200 });
        }

        let query;
        if (view === "archived") {
            query = "SELECT course_id, document_name, deleted_at FROM Course WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC";
        } else {
            query = "SELECT course_id, document_name FROM Course WHERE deleted_at IS NULL";
        }

        const [courses] = await chatmate.query(query);
        return NextResponse.json({ success: true, data: courses }, { status: 200 });
    } catch (err) {
        console.error("Error fetching courses:", err);
        return NextResponse.json({ success: false, message: "Failed to fetch courses" }, { status: 500 });
    }
}

export async function PUT(req) {
    try {
        const formData = await req.formData();
        const courseId = formData.get("course_id");
        const courseDocument = formData.get("course_document");
        const documentName = formData.get("document_name");

        if (!courseId || !documentName) {
            return NextResponse.json({ success: false, message: "Course ID and document name are required" }, { status: 400 });
        }

        let query, params;
        if (courseDocument) {
            const bytes = await courseDocument.arrayBuffer();
            const buffer = Buffer.from(bytes);
            const base64Document = buffer.toString("base64");
            query = "UPDATE Course SET course_document = ?, document_name = ? WHERE course_id = ?";
            params = [base64Document, documentName, courseId];
        } else {
            query = "UPDATE Course SET document_name = ? WHERE course_id = ?";
            params = [documentName, courseId];
        }

        const [updateResult] = await chatmate.query(query, params);
        return NextResponse.json({ success: true, message: "Course updated successfully" }, { status: 200 });
    } catch (err) {
        console.error("Error updating course:", err);
        return NextResponse.json({ success: false, message: "Failed to update course" }, { status: 500 });
    }
}

// Soft-delete (archive/unarchive)
export async function PATCH(req) {
    try {
        const { course_id, action } = await req.json();

        if (!course_id || !["archive", "unarchive"].includes(action)) {
            return NextResponse.json({ success: false, message: "Invalid request" }, { status: 400 });
        }

        let query;
        if (action === "archive") {
            query = "UPDATE Course SET deleted_at = NOW() WHERE course_id = ?";
        } else {
            query = "UPDATE Course SET deleted_at = NULL WHERE course_id = ?";
        }

        const [result] = await chatmate.query(query, [course_id]);
        if (result.affectedRows === 0) {
            return NextResponse.json({ success: false, message: "Course not found" }, { status: 404 });
        }

        return NextResponse.json({ success: true, message: action === "archive" ? "Course archived" : "Course restored" }, { status: 200 });
    } catch (err) {
        console.error("Archive/Unarchive error:", err);
        return NextResponse.json({ success: false, message: "Operation failed" }, { status: 500 });
    }
}

// Hard delete (keep this!)
export async function DELETE(req) {
    try {
        const { searchParams } = new URL(req.url);
        const courseId = searchParams.get("course_id");
        if (!courseId) {
            return NextResponse.json({ success: false, message: "Course ID is required" }, { status: 400 });
        }
        const query = "DELETE FROM Course WHERE course_id = ?";
        await chatmate.query(query, [courseId]);
        return NextResponse.json({ success: true, message: "Course deleted permanently" }, { status: 200 });
    } catch (err) {
        console.error("Error deleting course:", err);
        return NextResponse.json({ success: false, message: "Failed to delete course" }, { status: 500 });
    }
}