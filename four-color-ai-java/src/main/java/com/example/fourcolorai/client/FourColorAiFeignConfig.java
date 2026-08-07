package com.example.fourcolorai.client;

import com.example.fourcolorai.exception.FourColorAiException;
import com.example.fourcolorai.exception.FourColorAiUnavailableException;
import com.example.fourcolorai.exception.FourColorParseException;
import feign.RequestInterceptor;
import feign.codec.ErrorDecoder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class FourColorAiFeignConfig {

    @Bean
    public ErrorDecoder fourColorErrorDecoder() {
        return (methodKey, response) -> {
            if (response.status() == 422) {
                return new FourColorParseException("图片解析失败（业务错误，不重试不熔断）");
            }
            if (response.status() >= 500) {
                return new FourColorAiUnavailableException(
                        "四色图识别服务异常，status=" + response.status());
            }
            return new FourColorAiException(
                    "四色图识别服务调用失败，status=" + response.status());
        };
    }

    @Bean
    public RequestInterceptor fourColorApiKeyInterceptor(
            @Value("${ai-service.four-color.api-key}") String apiKey) {
        return template -> template.header("X-API-Key", apiKey);
    }
}
