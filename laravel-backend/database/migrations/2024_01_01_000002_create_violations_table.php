<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Migration: violations table
 *
 * Stores detected PPE compliance violations during inference sessions.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('violations', function (Blueprint $table) {
            $table->id();
            $table->foreignId('session_id')
                  ->nullable()
                  ->constrained('stream_sessions')
                  ->nullOnDelete();
            $table->unsignedInteger('person_id')->comment('BoT-SORT track ID');
            $table->string('violation_type')->comment('e.g. no_gloves, no_hairnet');
            $table->float('confidence')->default(0.0);
            $table->timestamp('timestamp')->useCurrent();
            $table->timestamps();

            $table->index(['session_id', 'timestamp']);
            $table->index('violation_type');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('violations');
    }
};
