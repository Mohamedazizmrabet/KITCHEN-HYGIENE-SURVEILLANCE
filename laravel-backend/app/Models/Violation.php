<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Violation — a single PPE compliance violation detected during a session.
 *
 * @property int    $id
 * @property int    $session_id
 * @property int    $person_id
 * @property string $violation_type
 * @property float  $confidence
 * @property string $timestamp
 */
class Violation extends Model
{
    protected $fillable = [
        'session_id',
        'person_id',
        'violation_type',
        'confidence',
        'timestamp',
    ];

    protected $casts = [
        'confidence' => 'float',
        'timestamp'  => 'datetime',
    ];

    /**
     * The session this violation belongs to.
     */
    public function session(): BelongsTo
    {
        return $this->belongsTo(StreamSession::class, 'session_id');
    }
}
