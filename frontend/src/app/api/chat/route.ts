import { NextResponse } from "next/server";

const BACKEND_BASE = process.env.BACKEND_BASE ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  const body = await req.text();
  const upstream = await fetch(`${BACKEND_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body
  });

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" }
  });
}

