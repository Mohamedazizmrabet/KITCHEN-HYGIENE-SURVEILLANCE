<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Migration: stream_sessions table
 *
 * Stores each inference session initiated from the frontend.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('stream_sessions', function (Blueprint $table) {
            $table->id();
            $table->string('source')->default('0')->comment('Camera index, RTSP URL, or file path');
            $table->string('model_used')->default('YOLO')->comment('YOLO | RTDETR | BOTH');
            $table->string('status')->default('active')->comment('active | stopped | error');
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('stream_sessions');
    }
};
