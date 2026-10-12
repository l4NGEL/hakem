package dev.hakem.api.job;

import java.io.IOException;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.ByteBuffer;
import java.util.Locale;
import java.util.Set;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

@RestController
@RequestMapping("/api/manuscripts")
public class ManuscriptController {

    private static final Set<String> EXTENSIONS = Set.of("txt", "md", "markdown");

    public record SubmitText(
            @NotBlank @Size(max = 300) String title,
            @NotBlank @Size(min = 200, message = "must be at least 200 characters") String text) {
    }

    private final JobService jobs;
    private final int maxChars;

    public ManuscriptController(JobService jobs, @Value("${hakem.max-chars:400000}") int maxChars) {
        this.jobs = jobs;
        this.maxChars = maxChars;
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<JobView> submitText(@Valid @RequestBody SubmitText body) {
        return accepted(body.title().strip(), body.text());
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<JobView> submitFile(@RequestParam("file") MultipartFile file,
                                              @RequestParam(value = "title", required = false) String title)
            throws IOException {
        String name = file.getOriginalFilename() == null ? "" : file.getOriginalFilename();
        String ext = name.contains(".") ? name.substring(name.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT) : "";
        if (!EXTENSIONS.contains(ext)) {
            throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE,
                    "Only .txt and .md files are accepted.");
        }
        String text = decodeUtf8(file.getBytes());
        String finalTitle = title == null || title.isBlank() ? name.substring(0, name.lastIndexOf('.')) : title.strip();
        return accepted(finalTitle, text);
    }

    @GetMapping("/{id}")
    public JobView get(@PathVariable @Pattern(regexp = "[0-9a-f-]{36}") String id) {
        return jobs.find(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "No such job."));
    }

    private ResponseEntity<JobView> accepted(String title, String text) {
        if (text.length() > maxChars) {
            throw new ResponseStatusException(HttpStatus.CONTENT_TOO_LARGE,
                    "Manuscript is longer than " + maxChars + " characters.");
        }
        if (text.strip().length() < 200) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Manuscript is too short to review.");
        }
        JobView job = jobs.submit(title, text);
        return ResponseEntity.status(job.status() == JobStatus.FAILED ? HttpStatus.SERVICE_UNAVAILABLE : HttpStatus.ACCEPTED)
                .header("Location", "/api/manuscripts/" + job.id())
                .body(job);
    }

    private static String decodeUtf8(byte[] bytes) {
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "File is not valid UTF-8 text.");
        }
    }
}
