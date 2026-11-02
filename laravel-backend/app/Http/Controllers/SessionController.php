<?php

namespace App\Http\Controllers;

use App\Models\StreamSession;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Validator;

/**
 * SessionController
 *
 * Manages the database records for inference sessions. The dashboard
 * starts and stops the streams on the FastAPI inference service directly.
 */
class SessionController extends Controller
{
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
            'model_used' => 'nullable|string|in:YOLO,RT,RTDETR,BOTH',
            'status'     => 'nullable|string',
        ]);

        if ($validator->fails()) {
            return response()->json(['errors' => $validator->errors()], 422);
        }

        // "RT" is the dashboard's short name for RT-DETR
        $model = $request->input('model_used', 'YOLO');
        if ($model === 'RT') {
            $model = 'RTDETR';
        }

        // Only the database record is created here. The dashboard starts the
        // inference stream itself, so forwarding here would start a duplicate.
        $session = StreamSession::create([
            'source'     => $request->input('source', '0'),
            'model_used' => $model,
            'status'     => $request->input('status', 'active'),
        ]);

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
