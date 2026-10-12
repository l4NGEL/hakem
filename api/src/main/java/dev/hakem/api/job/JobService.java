package dev.hakem.api.job;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.util.Optional;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.stereotype.Service;

import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;

/**
 * Intake flow: store the manuscript in S3, create the job item, then queue it.
 * The order matters: the analyzer may pick the message up immediately, so the
 * object and the item must already exist when the message is sent.
 *
 * Reads go through a cache, but only finished jobs are cached: a job still in
 * progress must always be read fresh, while a finished report never changes.
 */
@Service
public class JobService {

    private static final Logger log = LoggerFactory.getLogger(JobService.class);
    static final String CACHE = "reports";

    private final S3Client s3;
    private final SqsClient sqs;
    private final JobRepository jobs;
    private final Cache cache;
    private final String bucket;
    private final String queueUrl;
    private final Clock clock;

    public JobService(S3Client s3, SqsClient sqs, JobRepository jobs, CacheManager caches,
                      @Value("${hakem.bucket}") String bucket,
                      @Value("${hakem.queue-url}") String queueUrl,
                      Clock clock) {
        this.s3 = s3;
        this.sqs = sqs;
        this.jobs = jobs;
        this.cache = caches.getCache(CACHE);
        this.bucket = bucket;
        this.queueUrl = queueUrl;
        this.clock = clock;
    }

    public JobView submit(String title, String text) {
        String id = UUID.randomUUID().toString();
        String key = "manuscripts/" + id + ".txt";
        long now = clock.instant().getEpochSecond();

        s3.putObject(PutObjectRequest.builder().bucket(bucket).key(key)
                        .contentType("text/plain; charset=utf-8").build(),
                RequestBody.fromString(text, StandardCharsets.UTF_8));
        jobs.create(id, title, key, now);
        try {
            sqs.sendMessage(SendMessageRequest.builder().queueUrl(queueUrl)
                    .messageBody("{\"id\":\"%s\",\"bucket\":\"%s\",\"key\":\"%s\"}".formatted(id, bucket, key))
                    .build());
        } catch (SdkException e) {
            log.error("could not queue job {}", id, e);
            jobs.markFailed(id, "Could not queue the manuscript for analysis.", now);
            return new JobView(id, title, JobStatus.FAILED, now, now, "Could not queue the manuscript for analysis.", null);
        }
        return new JobView(id, title, JobStatus.QUEUED, now, null, null, null);
    }

    public Optional<JobView> find(String id) {
        JobView cached = cache.get(id, JobView.class);
        if (cached != null) {
            return Optional.of(cached);
        }
        Optional<JobView> job = jobs.find(id);
        job.filter(JobView::isFinal).ifPresent(j -> cache.put(id, j));
        return job;
    }
}
