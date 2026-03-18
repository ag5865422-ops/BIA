import { NextResponse } from "next/server";

const BACKEND_BASE = process.env.BACKEND_BASE ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  const form = await req.formData();
  const upstream = await fetch(`${BACKEND_BASE}/api/datasets/upload`, {
    method: "POST",
    body: form
  });

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" }
  });
}

