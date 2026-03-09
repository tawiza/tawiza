import { NextRequest } from 'next/server';

const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8000';

// Allow long-running PPDSL analysis (10 minutes max)
export const maxDuration = 600;

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { query, cognitive_level = 'analytical', fast = false } = body;

    if (!query) {
      return new Response(JSON.stringify({ error: 'Query is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Create abort controller with 10-minute timeout for PPDSL analysis
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600000); // 10 minutes

    // Forward to FastAPI backend with streaming
    const response = await fetch(`${FASTAPI_URL}/api/v1/tajine/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        cognitive_level,
        stream: true,
        fast,
      }),
      signal: controller.signal,
      // @ts-expect-error - undici-specific option for body timeout
      bodyTimeout: 600000, // 10 minutes
      headersTimeout: 120000, // 2 minutes for headers (model loading can take ~70s)
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const error = await response.text();
      return new Response(error, { status: response.status });
    }

    // Get the response body as a readable stream
    const backendStream = response.body;
    if (!backendStream) {
      return new Response('No response body', { status: 500 });
    }

    // Create a TransformStream to forward chunks immediately
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    const reader = backendStream.getReader();

    // Pipe the backend stream to the client without buffering
    // Add keepalive to prevent timeout during long PPDSL phases
    let lastActivity = Date.now();
    const keepaliveInterval = setInterval(() => {
      const encoder = new TextEncoder();
      // Send comment keepalive if no activity for 15 seconds
      if (Date.now() - lastActivity > 15000) {
        writer.write(encoder.encode(': keepalive\n\n')).catch(() => {});
        lastActivity = Date.now();
      }
    }, 10000);

    (async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            clearInterval(keepaliveInterval);
            await writer.close();
            break;
          }
          // Write immediately without buffering
          lastActivity = Date.now();
          await writer.write(value);
        }
      } catch (error) {
        clearInterval(keepaliveInterval);
        // Only log if not a normal client disconnect
        const msg = String(error);
        if (!msg.includes('ResponseAborted') && !msg.includes('other side closed')) {
          console.error('Stream error:', error);
        }
        try {
          await writer.close();
        } catch {
          // Writer already closed or errored, ignore
        }
      }
    })();

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
        'Transfer-Encoding': 'chunked',
      },
    });
  } catch (error) {
    console.error('TAJINE API error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}

export async function GET() {
  try {
    const response = await fetch(`${FASTAPI_URL}/api/v1/tajine/status`);
    const data = await response.json();
    return Response.json(data);
  } catch {
    return Response.json({ status: 'disconnected', error: 'FastAPI not reachable' });
  }
}
