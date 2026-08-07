package com.example.fourcolorai;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;

@SpringBootApplication
@EnableFeignClients
public class FourColorAiApplication {
    public static void main(String[] args) {
        SpringApplication.run(FourColorAiApplication.class, args);
    }
}
