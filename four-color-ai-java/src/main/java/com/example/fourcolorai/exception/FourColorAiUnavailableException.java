package com.example.fourcolorai.exception;

public class FourColorAiUnavailableException extends RuntimeException {
    public FourColorAiUnavailableException(String message) {
        super(message);
    }

    public FourColorAiUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
