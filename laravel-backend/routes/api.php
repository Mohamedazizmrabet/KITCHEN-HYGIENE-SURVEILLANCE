<?php

use App\Http\Controllers\SessionController;
use App\Http\Controllers\ViolationController;
use App\Http\Controllers\SettingsController;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API Routes — KitchenWatch Laravel Backend
|--------------------------------------------------------------------------
|
| All routes are stateless JSON APIs.
| No authentication middleware is applied here — Sanctum can be added
| later by wrapping routes with auth:sanctum.
|
*/

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
Route::get('/health', function () {
    return response()->json([
        'status'  => 'ok',
        'service' => 'KitchenWatch Laravel API',
        'time'    => now()->toIso8601String(),
    ]);
});

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------
Route::get('/sessions',        [SessionController::class, 'index']);
Route::post('/sessions',       [SessionController::class, 'store']);
Route::get('/sessions/{id}',   [SessionController::class, 'show']);
Route::delete('/sessions/{id}',[SessionController::class, 'destroy']);

// ---------------------------------------------------------------------------
// Violations
// ---------------------------------------------------------------------------
Route::get('/violations',      [ViolationController::class, 'index']);
Route::post('/violations',     [ViolationController::class, 'store']);
Route::get('/violations/{id}', [ViolationController::class, 'show']);

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
Route::get('/settings',        [SettingsController::class, 'index']);
Route::put('/settings',        [SettingsController::class, 'update']);

// ---------------------------------------------------------------------------
// Inference service proxy
// Routes that forward requests to FastAPI so the frontend has a single origin
// ---------------------------------------------------------------------------
Route::prefix('inference')->group(function () {
    $inferenceUrl = env('INFERENCE_SERVICE_URL', 'http://localhost:8001');

    Route::get('/health', function () use ($inferenceUrl) {
        try {
            $res = Http::timeout(3)->get("{$inferenceUrl}/health");
            return response()->json($res->json(), $res->status());
        } catch (\Exception $e) {
            return response()->json(['status' => 'offline', 'error' => $e->getMessage()], 503);
        }
    });

    Route::post('/model/select', function (Request $request) use ($inferenceUrl) {
        try {
            $res = Http::timeout(5)->post("{$inferenceUrl}/model/select", $request->all());
            return response()->json($res->json(), $res->status());
        } catch (\Exception $e) {
            return response()->json(['error' => $e->getMessage()], 503);
        }
    });

    Route::get('/metrics', function () use ($inferenceUrl) {
        try {
            $res = Http::timeout(3)->get("{$inferenceUrl}/metrics");
            return response()->json($res->json(), $res->status());
        } catch (\Exception $e) {
            return response()->json(['error' => $e->getMessage()], 503);
        }
    });
});
