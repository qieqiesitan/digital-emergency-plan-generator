package com.example.fourcolorai.service;

import com.example.fourcolorai.dto.FourColorAnalyzeResult;
import java.util.concurrent.CompletableFuture;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Service
public class FourColorAiAsyncService {

    private final FourColorAiFacade facade;

    public FourColorAiAsyncService(FourColorAiFacade facade) {
        this.facade = facade;
    }

    @Async("aiCallExecutor")
    public CompletableFuture<FourColorAnalyzeResult> analyzeAsync(String imageBase64) {
        return CompletableFuture.completedFuture(facade.analyze(imageBase64));
    }
}
