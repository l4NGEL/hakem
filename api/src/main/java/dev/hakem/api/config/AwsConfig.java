package dev.hakem.api.config;

import java.net.URI;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import software.amazon.awssdk.core.client.builder.SdkClientBuilder;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.sqs.SqsClient;

/**
 * AWS clients. Credentials come from the default provider chain (environment,
 * instance/task role). Per-service endpoint overrides exist only for running
 * against local emulators; leave them empty on AWS.
 */
@Configuration
public class AwsConfig {

    @ConfigurationProperties(prefix = "hakem.aws")
    public record AwsProperties(String region, String s3Endpoint, String dynamodbEndpoint, String sqsEndpoint) {
    }

    @Bean
    S3Client s3Client(AwsProperties props) {
        var builder = S3Client.builder()
                .region(Region.of(props.region()))
                .httpClientBuilder(UrlConnectionHttpClient.builder())
                // path-style URLs are required by S3-compatible local stores
                .forcePathStyle(hasText(props.s3Endpoint()));
        return endpoint(builder, props.s3Endpoint()).build();
    }

    @Bean
    DynamoDbClient dynamoDbClient(AwsProperties props) {
        var builder = DynamoDbClient.builder()
                .region(Region.of(props.region()))
                .httpClientBuilder(UrlConnectionHttpClient.builder());
        return endpoint(builder, props.dynamodbEndpoint()).build();
    }

    @Bean
    SqsClient sqsClient(AwsProperties props) {
        var builder = SqsClient.builder()
                .region(Region.of(props.region()))
                .httpClientBuilder(UrlConnectionHttpClient.builder());
        return endpoint(builder, props.sqsEndpoint()).build();
    }

    private static <B extends SdkClientBuilder<B, ?>> B endpoint(B builder, String endpoint) {
        return hasText(endpoint) ? builder.endpointOverride(URI.create(endpoint)) : builder;
    }

    private static boolean hasText(String s) {
        return s != null && !s.isBlank();
    }
}
