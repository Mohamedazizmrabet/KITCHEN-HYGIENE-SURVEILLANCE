<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Setting — key-value application setting.
 *
 * @property string $key
 * @property mixed  $value
 */
class Setting extends Model
{
    protected $fillable = ['key', 'value'];

    /**
     * Retrieve a setting by key, with optional default.
     */
    public static function get(string $key, mixed $default = null): mixed
    {
        $record = static::where('key', $key)->first();
        return $record ? $record->value : $default;
    }

    /**
     * Upsert a setting value by key.
     */
    public static function set(string $key, mixed $value): void
    {
        static::updateOrCreate(['key' => $key], ['value' => $value]);
    }
}
