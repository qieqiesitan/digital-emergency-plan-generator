package com.example.fourcolorai.common;

public record ApiResponse<T>(int code, String message, T data) {
    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }

    public boolean ok() {
        return code == 0;
    }
}
