package com.example.fourcolorai.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.example.fourcolorai.client.FourColorAiClient;
import com.example.fourcolorai.common.ApiResponse;
import com.example.fourcolorai.dto.FourColorAnalyzeResult;
import com.example.fourcolorai.exception.FourColorAiException;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class FourColorAiFacadeTest {

    private FourColorAiClient client;
    private FourColorAiFacade facade;

    @BeforeEach
    void setUp() {
        client = mock(FourColorAiClient.class);
        facade = new FourColorAiFacade(client);
    }

    @Test
    void returnsDataWhenCodeZero() {
        FourColorAnalyzeResult expected = new FourColorAnalyzeResult(
                "rid", 600, 450, 600, 450, "png",
                List.of(), List.of(), List.of(), List.of());
        when(client.analyze(any())).thenReturn(new ApiResponse<>(0, "ok", expected));

        assertThat(facade.analyze("base64")).isEqualTo(expected);
    }

    @Test
    void throwsBusinessExceptionWhenCodeNonZero() {
        when(client.analyze(any())).thenReturn(new ApiResponse<>(1, "boom", null));

        assertThatThrownBy(() -> facade.analyze("base64"))
                .isInstanceOf(FourColorAiException.class);
    }
}
