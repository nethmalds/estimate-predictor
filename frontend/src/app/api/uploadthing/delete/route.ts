import { NextResponse } from "next/server";
import { UTApi } from "uploadthing/server";

const utapi = new UTApi();

export async function POST(request: Request) {
  try {
    const { fileKey } = await request.json();
    if (!fileKey) {
      return NextResponse.json({ error: "No fileKey provided" }, { status: 400 });
    }

    const response = await utapi.deleteFiles(fileKey);
    return NextResponse.json(response);
  } catch (error) {
    console.error("Failed to delete file:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
