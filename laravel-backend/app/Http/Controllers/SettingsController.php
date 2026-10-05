<?php

namespace App\Http\Controllers;

use App\Models\Setting;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/**
 * SettingsController
 *
 * Key-value application settings used by the frontend (Model Settings page)
 * and read by the Python inference service via SettingsClient.
 *
 * Default settings are returned when none have been saved yet.
 */
class SettingsController extends Controller
{
    /**
     * Default settings returned when the database has no entry.
     */
    private array $defaults = [
        'model'                => 'YOLO',
        'confidence_threshold' => 0.5,
        'stream_fps'           => 30,
        'device'               => 'auto',
        'enabled_classes'      => ['gloves', 'hairnet', 'mask', 'no_gloves', 'no_hairnet'],
    ];

    /**
     * GET /api/settings
     * Return all current settings (with defaults for missing keys).
     */
    public function index(): JsonResponse
    {
        $settings = $this->defaults;

        // Override defaults with any stored values
        $stored = Setting::all()->pluck('value', 'key')->toArray();

        foreach ($stored as $key => $value) {
            // Decode JSON-encoded values (arrays, booleans, numbers)
            $decoded = json_decode($value, true);
            $settings[$key] = ($decoded !== null) ? $decoded : $value;
        }

        return response()->json($settings);
    }

    /**
     * PUT /api/settings
     * Persist settings as key-value pairs.
     * Accepts a flat JSON object from the frontend.
     */
    public function update(Request $request): JsonResponse
    {
        $data = $request->validate([
            'model'                => 'sometimes|string|in:YOLO,RTDETR,BOTH',
            'confidence_threshold' => 'sometimes|numeric|between:0.01,1',
            'stream_fps'           => 'sometimes|integer|min:1|max:120',
            'device'               => 'sometimes|string',
            'enabled_classes'      => 'sometimes|array',
            'enabled_classes.*'    => 'string',
        ]);

        foreach ($data as $key => $value) {
            // Store arrays / complex types as JSON strings
            $stored = is_array($value) ? json_encode($value) : (string) $value;
            Setting::set($key, $stored);
        }

        return response()->json([
            'message' => 'Settings updated.',
            'settings' => $data,
        ]);
    }
}
