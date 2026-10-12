package dev.hakem.api.job;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;

import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;
import software.amazon.awssdk.services.sqs.model.SqsException;

class JobServiceTest {

    private final S3Client s3 = mock(S3Client.class);
    private final SqsClient sqs = mock(SqsClient.class);
    private final JobRepository repo = mock(JobRepository.class);
    private final Clock clock = Clock.fixed(Instant.ofEpochSecond(1_760_000_000L), ZoneOffset.UTC);
    private JobService service;

    @BeforeEach
    void setUp() {
        service = new JobService(s3, sqs, repo, new ConcurrentMapCacheManager(JobService.CACHE),
                "bucket", "https://sqs/queue", clock);
    }

    @Test
    void submitStoresObjectThenCreatesJobThenQueues() {
        JobView job = service.submit("Title", "text");

        var order = inOrder(s3, repo, sqs);
        var put = ArgumentCaptor.forClass(PutObjectRequest.class);
        order.verify(s3).putObject(put.capture(), any(RequestBody.class));
        order.verify(repo).create(eq(job.id()), eq("Title"), eq("manuscripts/" + job.id() + ".txt"), eq(1_760_000_000L));
        var msg = ArgumentCaptor.forClass(SendMessageRequest.class);
        order.verify(sqs).sendMessage(msg.capture());

        assertThat(put.getValue().bucket()).isEqualTo("bucket");
        assertThat(msg.getValue().messageBody())
                .isEqualTo("{\"id\":\"%s\",\"bucket\":\"bucket\",\"key\":\"manuscripts/%s.txt\"}".formatted(job.id(), job.id()));
        assertThat(job.status()).isEqualTo(JobStatus.QUEUED);
    }

    @Test
    void queueFailureMarksJobFailed() {
        when(sqs.sendMessage(any(SendMessageRequest.class)))
                .thenThrow(SqsException.builder().message("down").build());

        JobView job = service.submit("Title", "text");

        assertThat(job.status()).isEqualTo(JobStatus.FAILED);
        verify(repo).markFailed(eq(job.id()), anyString(), anyLong());
    }

    @Test
    void onlyFinishedJobsAreCached() {
        var running = new JobView("a", "T", JobStatus.PROCESSING, 1, 2L, null, null);
        var done = new JobView("a", "T", JobStatus.DONE, 1, 3L, null, "{\"checks\":{}}");
        when(repo.find("a")).thenReturn(Optional.of(running), Optional.of(done));

        assertThat(service.find("a")).contains(running);
        assertThat(service.find("a")).contains(done);   // not cached while running
        assertThat(service.find("a")).contains(done);   // served from cache
        verify(repo, times(2)).find("a");
    }
}
