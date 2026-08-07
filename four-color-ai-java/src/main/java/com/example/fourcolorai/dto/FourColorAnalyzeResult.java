package com.example.fourcolorai.dto;

import java.util.List;

public record FourColorAnalyzeResult(
        String requestId,
        int width,
        int height,
        int canvasWidth,
        int canvasHeight,
        String previewPngBase64,
        List<Zone> zones,
        List<TextItem> texts,
        List<ExcludedItem> excluded,
        List<String> warnings) {

    public record Point(double x, double y) {}

    public record Polygon(String id, String label, List<Point> points) {}

    public record Zone(String clientId, String name, String riskLevel, String color,
                       boolean suspected, String suggestedName, String aiHint,
                       List<Polygon> polygons) {}

    public record TextItem(List<Point> points, String text, double confidence) {}

    public record ExcludedItem(String color, String reason, List<Polygon> polygons) {}
}
