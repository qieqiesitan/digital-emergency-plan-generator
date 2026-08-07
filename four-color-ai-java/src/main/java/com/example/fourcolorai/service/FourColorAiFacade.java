package com.example.fourcolorai.service;

import com.example.fourcolorai.client.FourColorAiClient;
import com.example.fourcolorai.common.ApiResponse;
import com.example.fourcolorai.dto.FourColorAnalyzeRequest;
import com.example.fourcolorai.dto.FourColorAnalyzeResult;
import com.example.fourcolorai.exception.FourColorAiException;
import com.example.fourcolorai.exception.FourColorAiUnavailableException;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import org.springframework.stereotype.Service;

@Service
public class FourColorAiFacade {

    private final FourColorAiClient client;

    public FourColorAiFacade(FourColorAiClient client) {
        this.client = client;
    }

    @Retry(name = "fourColorAi", fallbackMethod = "analyzeFallback")
    @CircuitBreaker(name = "fourColorAi")
    public FourColorAnalyzeResult analyze(String imageBase64) {
        ApiResponse<FourColorAnalyzeResult> resp = client.analyze(
                new FourColorAnalyzeRequest(imageBase64, FourColorAnalyzeRequest.Options.defaults()));
        if (!resp.ok()) {
            throw new FourColorAiException("AI 服务业务失败: code=" + resp.code() + ", " + resp.message());
        }
        return resp.data();
    }

    private FourColorAnalyzeResult analyzeFallback(String imageBase64, Throwable t) {
        throw new FourColorAiUnavailableException("四色图识别服务暂不可用", t);
    }
}
