package com.example.fourcolorai.client;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.fourcolorai.exception.FourColorAiException;
import com.example.fourcolorai.exception.FourColorAiUnavailableException;
import com.example.fourcolorai.exception.FourColorParseException;
import feign.Request;
import feign.Response;
import java.util.Collections;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class FourColorAiFeignConfigTest {

    private FourColorAiFeignConfig config;

    @BeforeEach
    void setUp() {
        config = new FourColorAiFeignConfig();
    }

    private Response response(int status) {
        return Response.builder()
                .status(status)
                .reason("reason")
                .request(Request.create(Request.HttpMethod.POST,
                        "http://localhost/api/v1/four-color/analyze",
                        Collections.emptyMap(), new byte[0], null))
                .headers(Collections.emptyMap())
                .build();
    }

    @Test
    void maps422ToParseException() {
        Object decoded = config.fourColorErrorDecoder()
                .decode("FourColorAiClient#analyze(FourColorAnalyzeRequest)", response(422));
        assertThat(decoded).isInstanceOf(FourColorParseException.class);
    }

    @Test
    void maps503ToUnavailableException() {
        Object decoded = config.fourColorErrorDecoder()
                .decode("FourColorAiClient#analyze(FourColorAnalyzeRequest)", response(503));
        assertThat(decoded).isInstanceOf(FourColorAiUnavailableException.class);
    }

    @Test
    void mapsOtherStatusToGenericException() {
        Object decoded = config.fourColorErrorDecoder()
                .decode("FourColorAiClient#analyze(FourColorAnalyzeRequest)", response(404));
        assertThat(decoded).isInstanceOf(FourColorAiException.class);
    }
}
