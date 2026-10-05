<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * StreamSession — represents a single inference session.
 *
 * @property int    $id
 * @property string $source
 * @property string $model_used
 * @property string $status
 */
class StreamSession extends Model
{
    protected $fillable = [
        'source',
        'model_used',
        'status',
    ];

    /**
     * Violations recorded during this session.
     */
    public function violations(): HasMany
    {
        return $this->hasMany(Violation::class, 'session_id');
    }
}
