package com.example.fourcolorai.config;

import java.nio.file.Path;
import java.nio.file.Paths;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class PreviewWebConfig implements WebMvcConfigurer {

    private final Path root;

    public PreviewWebConfig(
            @Value("${app.preview-storage.dir:${java.io.tmpdir}/four-color-previews}") String dir) {
        this.root = Paths.get(dir).toAbsolutePath().normalize();
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/api/risk-management/previews/**")
                .addResourceLocations(root.toUri().toString());
    }
}
