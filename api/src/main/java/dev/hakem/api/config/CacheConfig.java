package dev.hakem.api.config;

import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Configuration;

/** Kept out of the application class so web-layer test slices do not need a cache. */
@Configuration
@EnableCaching
public class CacheConfig {
}
