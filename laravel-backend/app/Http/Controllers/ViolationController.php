<?php

namespace App\Http\Controllers;

use App\Models\Violation;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Validator;

/**
 * ViolationController
 *
 * Stores and retrieves PPE compliance violations.
 * Violations can be pushed directly from the Python inference service
 * or recorded by the frontend.
 */
class ViolationController extends Controller
{
    /**
     * GET /api/violations
     * Return all violations, optionally filtered by session or type.
     */
    public function index(Request $request): JsonResponse
    {
        $query = Violation::orderByDesc('timestamp');

        if ($request->has('session_id')) {
            $query->where('session_id', $request->integer('session_id'));
        }

        if ($request->has('type')) {
            $query->where('violation_type', $request->input('type'));
        }

        $violations = $query->get();

        return response()->json($violations);
    }

    /**
     * POST /api/violations
     * Record a new violation.
     * Called by the Python inference service when a violation is detected.
     */
    public function store(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'session_id'     => 'nullable|integer|exists:stream_sessions,id',
            'person_id'      => 'required|integer',
            'violation_type' => 'required|string|max:100',
            'confidence'     => 'nullable|numeric|between:0,1',
            'timestamp'      => 'nullable|date',
        ]);

        if ($validator->fails()) {
            return response()->json(['errors' => $validator->errors()], 422);
        }

        $violation = Violation::create([
            'session_id'     => $request->input('session_id'),
            'person_id'      => $request->input('person_id'),
            'violation_type' => $request->input('violation_type'),
            'confidence'     => $request->input('confidence', 0.0),
            'timestamp'      => $request->input('timestamp', now()),
        ]);

        return response()->json($violation, 201);
    }

    /**
     * GET /api/violations/{id}
     */
    public function show(int $id): JsonResponse
    {
        return response()->json(Violation::findOrFail($id));
    }
}
