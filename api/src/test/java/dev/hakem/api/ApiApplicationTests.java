package dev.hakem.api;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(properties = {
        "spring.cache.type=simple",
        "hakem.queue-url=http://localhost:9324/000000000000/hakem-jobs",
        "management.health.redis.enabled=false"})
class ApiApplicationTests {

    @Test
    void contextLoads() {
    }
}
