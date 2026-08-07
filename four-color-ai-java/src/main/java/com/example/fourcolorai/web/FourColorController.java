package com.example.fourcolorai.web;

import com.example.fourcolorai.common.ApiResponse;
import com.example.fourcolorai.dto.FrontendAnalyzeResponse;
import com.example.fourcolorai.service.FourColorAiAsyncService;
import com.example.fourcolorai.service.PreviewStorageService;
import java.io.IOException;
import java.util.Base64;
import java.util.concurrent.CompletableFuture;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/risk-management/enterprises/{enterpriseId}/floors/{floorId}/four-color")
public class FourColorController {

    private final FourColorAiAsyncService aiService;
    private final PreviewStorageService previewStorageService;

    public FourColorController(FourColorAiAsyncService aiService,
                               PreviewStorageService previewStorageService) {
        this.aiService = aiService;
        this.previewStorageService = previewStorageService;
    }

    @PostMapping("/analyze")
    public CompletableFuture<ApiResponse<FrontendAnalyzeResponse>> analyze(
            @PathVariable String enterpriseId,
            @PathVariable String floorId,
            @RequestParam("file") MultipartFile file) throws IOException {

        String imageBase64 = Base64.getEncoder().encodeToString(file.getBytes());

        return aiService.analyzeAsync(imageBase64)
                .thenApply(result -> ApiResponse.ok(FrontendAnalyzeResponse.from(
                        result,
                        previewStorageService.save(enterpriseId, floorId, result.previewPngBase64()))));
    }
}
