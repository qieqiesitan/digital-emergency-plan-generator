package com.example.fourcolorai.dto;

import java.util.List;

public record FrontendAnalyzeResponse(
        String previewUrl,
        int canvasWidth,
        int canvasHeight,
        List<FourColorAnalyzeResult.Zone> zones,
        List<String> warnings,
        List<FourColorAnalyzeResult.ExcludedItem> excluded,
        List<FourColorAnalyzeResult.TextItem> texts) {

    public static FrontendAnalyzeResponse from(FourColorAnalyzeResult result, String previewUrl) {
        return new FrontendAnalyzeResponse(
                previewUrl,
                result.canvasWidth(),
                result.canvasHeight(),
                result.zones(),
                result.warnings(),
                result.excluded(),
                result.texts());
    }
}
