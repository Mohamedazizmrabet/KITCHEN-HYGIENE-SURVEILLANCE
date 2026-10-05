<?php

namespace Database\Seeders;

use App\Models\Setting;
use Illuminate\Database\Seeder;

/**
 * DatabaseSeeder
 *
 * Seeds the database with default application settings so the
 * frontend and inference service have sensible initial values.
 */
class DatabaseSeeder extends Seeder
{
    public function run(): void
    {
        $defaults = [
            'model'                => 'YOLO',
            'confidence_threshold' => '0.5',
            'stream_fps'           => '30',
            'device'               => 'auto',
            'enabled_classes'      => json_encode(['gloves', 'hairnet', 'mask', 'no_gloves', 'no_hairnet']),
        ];

        foreach ($defaults as $key => $value) {
            Setting::firstOrCreate(['key' => $key], ['value' => $value]);
        }

        $this->command->info('Default settings seeded.');
    }
}
