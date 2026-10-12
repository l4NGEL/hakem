package dev.hakem.api;

import java.time.Clock;
import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.context.annotation.Bean;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@SpringBootApplication
@ConfigurationPropertiesScan
public class ApiApplication {

    public static void main(String[] args) {
        SpringApplication.run(ApiApplication.class, args);
    }

    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }

    @Bean
    WebMvcConfigurer cors(@Value("${hakem.cors-origins:}") List<String> origins) {
        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                if (!origins.isEmpty()) {
                    registry.addMapping("/api/**").allowedOrigins(origins.toArray(String[]::new))
                            .allowedMethods("GET", "POST");
                }
            }
        };
    }
}
