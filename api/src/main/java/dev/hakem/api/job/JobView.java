package dev.hakem.api.job;

import java.io.Serializable;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonRawValue;

/**
 * A manuscript job as returned to clients. {@code report} is the analyzer's JSON,
 * passed through unparsed so the API does not need to mirror its schema.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record JobView(
        String id,
        String title,
        JobStatus status,
        long createdAt,
        Long updatedAt,
        String error,
        @JsonRawValue String report) implements Serializable {

    public boolean isFinal() {
        return status == JobStatus.DONE || status == JobStatus.FAILED;
    }
}
