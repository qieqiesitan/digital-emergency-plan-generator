package com.example.fourcolorai.dto;

public record FourColorAnalyzeRequest(String imageBase64, Options options) {
    public record Options(int maxZones, int canvasWidth, int canvasHeight,
                          boolean enableOcr, boolean enableClip) {
        public static Options defaults() {
            return new Options(200, 1600, 1000, true, true);
        }
    }
}
