<?php

namespace App\Http\Controllers;

use App\Models\StreamSession;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Validator;

/**
 * SessionController
 *
 * Manages inference sessions: creates records in the database and
 * optionally proxies start/stop commands to the FastAPI inference service.
 */
class SessionController extends Controller
{
    private string $inferenceUrl;

    public function __construct()
    {
        $this->inferenceUrl = env('INFERENCE_SERVICE_URL', 'http://localhost:8001');
    }

    /**
     * GET /api/sessions
     * Return all sessions ordered by most recent.
     */
    public function index(): JsonResponse
    {
        $sessions = StreamSession::with('violations')
            ->orderByDesc('created_at')
            ->get();

        return response()->json($sessions);
    }

    /**
     * POST /api/sessions
     * Create a new session record and forward to inference service.
     */
    public function store(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'source'     => 'nullable|string',
            'model_used' => 'nullable|string|in:YOLO,RTDETR,BOTH',
            'status'     => 'nullable|string',
        ]);

        if ($validator->fails()) {
            return response()->json(['errors' => $validator->errors()], 422);
        }

        $session = StreamSession::create([
            'source'     => $request->input('source', '0'),
            'model_used' => $request->input('model_used', 'YOLO'),
            'status'     => $request->input('status', 'active'),
        ]);

        // Forward to inference service (non-blocking — best effort)
        try {
            Http::timeout(5)->post("{$this->inferenceUrl}/session/start", [
                'source' => $session->source,
                'model'  => $session->model_used,
            ]);
        } catch (\Exception $e) {
            // Log but don't fail — inference service may not be running
            \Log::warning("Could not notify inference service: {$e->getMessage()}");
        }

        return response()->json($session, 201);
    }

    /**
     * GET /api/sessions/{id}
     */
    public function show(int $id): JsonResponse
    {
        $session = StreamSession::with('violations')->findOrFail($id);
        return response()->json($session);
    }

    /**
     * DELETE /api/sessions/{id}
     * Stop and delete a session.
     */
    public function destroy(int $id): JsonResponse
    {
        $session = StreamSession::findOrFail($id);
        $session->update(['status' => 'stopped']);

        return response()->json(['message' => 'Session stopped.']);
    }
}
