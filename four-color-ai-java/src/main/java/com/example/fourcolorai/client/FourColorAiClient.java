package com.example.fourcolorai.client;

import com.example.fourcolorai.common.ApiResponse;
import com.example.fourcolorai.dto.FourColorAnalyzeRequest;
import com.example.fourcolorai.dto.FourColorAnalyzeResult;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

@FeignClient(
        name = "four-color-ai",
        url = "${ai-service.four-color.base-url}",
        configuration = FourColorAiFeignConfig.class)
public interface FourColorAiClient {

    @PostMapping(value = "/api/v1/four-color/analyze",
                 consumes = MediaType.APPLICATION_JSON_VALUE)
    ApiResponse<FourColorAnalyzeResult> analyze(@RequestBody FourColorAnalyzeRequest request);
}
