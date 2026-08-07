package com.example.fourcolorai.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LocalPreviewStorageServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void savesPngAndReturnsUrl() throws IOException {
        LocalPreviewStorageService service = new LocalPreviewStorageService(tempDir.toString());
        byte[] png = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};

        String url = service.save("e1", "f1", Base64.getEncoder().encodeToString(png));

        assertThat(url).startsWith("/api/risk-management/previews/e1/f1/").endsWith(".png");
        Path saved = tempDir.resolve(url.substring("/api/risk-management/previews/".length()));
        assertThat(Files.readAllBytes(saved)).containsExactly(png);
    }

    @Test
    void sanitizesUnsafeIds() {
        LocalPreviewStorageService service = new LocalPreviewStorageService(tempDir.toString());

        String url = service.save("../evil", "f1", Base64.getEncoder().encodeToString(new byte[]{1, 2, 3}));

        assertThat(url).startsWith("/api/risk-management/previews/evil/f1/");
    }

    @Test
    void rejectsInvalidBase64() {
        LocalPreviewStorageService service = new LocalPreviewStorageService(tempDir.toString());

        assertThatThrownBy(() -> service.save("e1", "f1", "!!!not-base64!!!"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
