package dev.hakem.api.job;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Repository;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;
import software.amazon.awssdk.services.dynamodb.model.UpdateItemRequest;

/** Job items in DynamoDB. The analyzer Lambda updates status and report on the same item. */
@Repository
public class JobRepository {

    private final DynamoDbClient ddb;
    private final String table;
    private final long ttlSeconds;

    public JobRepository(DynamoDbClient ddb,
                         @Value("${hakem.jobs-table}") String table,
                         @Value("${hakem.job-ttl-days:30}") long ttlDays) {
        this.ddb = ddb;
        this.table = table;
        this.ttlSeconds = ttlDays * 24 * 3600;
    }

    public void create(String id, String title, String s3Key, long now) {
        Map<String, AttributeValue> item = new HashMap<>();
        item.put("id", s(id));
        item.put("title", s(title));
        item.put("s3Key", s(s3Key));
        item.put("status", s(JobStatus.QUEUED.name()));
        item.put("createdAt", n(now));
        item.put("expiresAt", n(now + ttlSeconds)); // DynamoDB TTL attribute
        ddb.putItem(PutItemRequest.builder().tableName(table).item(item)
                .conditionExpression("attribute_not_exists(id)").build());
    }

    public void markFailed(String id, String error, long now) {
        ddb.updateItem(UpdateItemRequest.builder().tableName(table).key(Map.of("id", s(id)))
                .updateExpression("SET #s = :s, #e = :e, updatedAt = :u")
                .expressionAttributeNames(Map.of("#s", "status", "#e", "error"))
                .expressionAttributeValues(Map.of(":s", s(JobStatus.FAILED.name()), ":e", s(error), ":u", n(now)))
                .build());
    }

    public Optional<JobView> find(String id) {
        var item = ddb.getItem(GetItemRequest.builder().tableName(table).key(Map.of("id", s(id)))
                .consistentRead(true).build()).item();
        if (item == null || item.isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(new JobView(
                item.get("id").s(),
                str(item, "title"),
                JobStatus.valueOf(item.get("status").s()),
                Long.parseLong(item.get("createdAt").n()),
                item.containsKey("updatedAt") ? Long.parseLong(item.get("updatedAt").n()) : null,
                str(item, "error"),
                str(item, "report")));
    }

    private static String str(Map<String, AttributeValue> item, String key) {
        var v = item.get(key);
        return v == null ? null : v.s();
    }

    private static AttributeValue s(String v) {
        return AttributeValue.fromS(v);
    }

    private static AttributeValue n(long v) {
        return AttributeValue.fromN(Long.toString(v));
    }
}
