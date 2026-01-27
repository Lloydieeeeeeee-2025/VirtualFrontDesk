import { chatmate } from "../../../../../library/tlcchatmatedb/route";
import { NextResponse } from "next/server";

export const runtime = 'nodejs';
export const maxDuration = 60;

async function parseFormData(req) {
  const formData = await req.formData();
  return formData;
}

// POST: Upload new handbook
export async function POST(req) {
  try {
    const formData = await parseFormData(req);
    const handbookDocument = formData.get("handbook_document");
    const handbookName = formData.get("handbook_name");

    if (!handbookDocument || !handbookName) {
      return NextResponse.json({ success: false, message: "Handbook document and name are required" }, { status: 400 });
    }

    if (handbookDocument.size > 20 * 1024 * 1024) {
      return NextResponse.json({ success: false, message: "File size must be less than 20MB" }, { status: 400 });
    }

    const bytes = await handbookDocument.arrayBuffer();
    const buffer = Buffer.from(bytes);
    const query = "INSERT INTO Handbook (handbook_document, handbook_name) VALUES (?, ?)";
    const [result] = await chatmate.execute(query, [buffer, handbookName]);

    return NextResponse.json({ success: true, message: "Handbook uploaded successfully", data: { handbook_id: result.insertId } }, { status: 201 });
  } catch (err) {
    console.error("Error uploading handbook:", err);
    return NextResponse.json({ success: false, message: "Failed to upload handbook: " + err.message }, { status: 500 });
  }
}

// GET: Fetch handbooks (active or archived)
export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const handbookId = searchParams.get("handbook_id");
    const view = searchParams.get("view"); // 'active' or 'archived'

    if (handbookId) {
      const query = "SELECT * FROM Handbook WHERE handbook_id = ?";
      const [result] = await chatmate.execute(query, [handbookId]);
      if (result.length === 0) {
        return NextResponse.json({ success: false, message: "Handbook not found" }, { status: 404 });
      }
      let handbook = result[0];
      if (handbook.handbook_document) {
        handbook.handbook_document = handbook.handbook_document.toString('base64');
      }
      return NextResponse.json({ success: true, data: handbook }, { status: 200 });
    }

    let query;
    if (view === "archived") {
      query = "SELECT handbook_id, handbook_name, deleted_at FROM Handbook WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC";
    } else {
      query = "SELECT handbook_id, handbook_name FROM Handbook WHERE deleted_at IS NULL ORDER BY handbook_id DESC";
    }

    const [handbooks] = await chatmate.execute(query);
    return NextResponse.json({ success: true, data: handbooks }, { status: 200 });
  } catch (err) {
    console.error("Error fetching handbooks:", err);
    return NextResponse.json({ success: false, message: "Failed to fetch handbooks" }, { status: 500 });
  }
}

// PUT: Update handbook
export async function PUT(req) {
  try {
    const formData = await parseFormData(req);
    const handbookId = formData.get("handbook_id");
    const handbookDocument = formData.get("handbook_document");
    const handbookName = formData.get("handbook_name");

    if (!handbookId || !handbookName) {
      return NextResponse.json({ success: false, message: "Handbook ID and name are required" }, { status: 400 });
    }

    let query, params;
    if (handbookDocument) {
      if (handbookDocument.size > 20 * 1024 * 1024) {
        return NextResponse.json({ success: false, message: "File size must be less than 20MB" }, { status: 400 });
      }
      const bytes = await handbookDocument.arrayBuffer();
      const buffer = Buffer.from(bytes);
      query = "UPDATE Handbook SET handbook_document = ?, handbook_name = ? WHERE handbook_id = ?";
      params = [buffer, handbookName, handbookId];
    } else {
      query = "UPDATE Handbook SET handbook_name = ? WHERE handbook_id = ?";
      params = [handbookName, handbookId];
    }

    const [updateResult] = await chatmate.execute(query, params);
    return NextResponse.json({ success: true, message: "Handbook updated successfully" }, { status: 200 });
  } catch (err) {
    console.error("Error updating handbook:", err);
    return NextResponse.json({ success: false, message: "Failed to update handbook" }, { status: 500 });
  }
}

// PATCH: Archive or Unarchive
export async function PATCH(req) {
  try {
    const { handbook_id, action } = await req.json();

    if (!handbook_id || !['archive', 'unarchive'].includes(action)) {
      return NextResponse.json({ success: false, message: "Invalid request" }, { status: 400 });
    }

    let query;
    if (action === "archive") {
      query = "UPDATE Handbook SET deleted_at = NOW() WHERE handbook_id = ?";
    } else {
      query = "UPDATE Handbook SET deleted_at = NULL WHERE handbook_id = ?";
    }

    const [result] = await chatmate.execute(query, [handbook_id]);
    if (result.affectedRows === 0) {
      return NextResponse.json({ success: false, message: "Handbook not found" }, { status: 404 });
    }

    return NextResponse.json({ success: true, message: action === "archive" ? "Handbook archived" : "Handbook restored" }, { status: 200 });
  } catch (err) {
    console.error("Archive/Unarchive error:", err);
    return NextResponse.json({ success: false, message: "Operation failed" }, { status: 500 });
  }
}

// DELETE: Hard delete (keep this!)
export async function DELETE(req) {
  try {
    const { searchParams } = new URL(req.url);
    const handbookId = searchParams.get("handbook_id");
    if (!handbookId) {
      return NextResponse.json({ success: false, message: "Handbook ID is required" }, { status: 400 });
    }
    const query = "DELETE FROM Handbook WHERE handbook_id = ?";
    await chatmate.execute(query, [handbookId]);
    return NextResponse.json({ success: true, message: "Handbook deleted permanently" }, { status: 200 });
  } catch (err) {
    console.error("Error deleting handbook:", err);
    return NextResponse.json({ success: false, message: "Failed to delete handbook" }, { status: 500 });
  }
}