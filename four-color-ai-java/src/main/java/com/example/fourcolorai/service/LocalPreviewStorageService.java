package com.example.fourcolorai.service;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Base64;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class LocalPreviewStorageService implements PreviewStorageService {

    private final Path root;

    public LocalPreviewStorageService(
            @Value("${app.preview-storage.dir:${java.io.tmpdir}/four-color-previews}") String dir) {
        this.root = Paths.get(dir).toAbsolutePath().normalize();
    }

    @Override
    public String save(String enterpriseId, String floorId, String pngBase64) {
        String safeEnterprise = sanitize(enterpriseId);
        String safeFloor = sanitize(floorId);
        String fileName = UUID.randomUUID().toString().replace("-", "") + ".png";
        Path dir = root.resolve(safeEnterprise).resolve(safeFloor).normalize();
        if (!dir.startsWith(root)) {
            throw new IllegalArgumentException("非法存储路径");
        }
        try {
            Files.createDirectories(dir);
            byte[] bytes = Base64.getDecoder().decode(pngBase64);
            Files.write(dir.resolve(fileName), bytes);
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (IOException e) {
            throw new UncheckedIOException("保存预览图失败", e);
        }
        return "/api/risk-management/previews/" + safeEnterprise + "/" + safeFloor + "/" + fileName;
    }

    private String sanitize(String value) {
        String cleaned = value.replaceAll("[^a-zA-Z0-9_-]", "");
        if (cleaned.isEmpty()) {
            throw new IllegalArgumentException("非法标识: " + value);
        }
        return cleaned;
    }
}
