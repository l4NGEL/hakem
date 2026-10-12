package dev.hakem.api.job;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.charset.StandardCharsets;
import java.util.Optional;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(ManuscriptController.class)
class ManuscriptControllerTest {

    private static final String ID = "3f0c6a1e-8a3b-4c55-9d0e-2b7f5a1c9e42";
    private static final String TEXT = "Abstract. " + "word ".repeat(60);

    @Autowired
    MockMvc mvc;

    @MockitoBean
    JobService jobs;

    @Test
    void jsonSubmitReturns202WithLocation() throws Exception {
        when(jobs.submit(eq("Paper"), anyString()))
                .thenReturn(new JobView(ID, "Paper", JobStatus.QUEUED, 1, null, null, null));

        mvc.perform(post("/api/manuscripts").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"Paper\",\"text\":\"%s\"}".formatted(TEXT)))
                .andExpect(status().isAccepted())
                .andExpect(header().string("Location", "/api/manuscripts/" + ID))
                .andExpect(jsonPath("$.status").value("QUEUED"))
                .andExpect(jsonPath("$.report").doesNotExist());
    }

    @Test
    void tooShortTextIsRejected() throws Exception {
        mvc.perform(post("/api/manuscripts").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"Paper\",\"text\":\"short\"}"))
                .andExpect(status().isBadRequest());
        verifyNoInteractions(jobs);
    }

    @Test
    void markdownUploadUsesFileNameAsTitle() throws Exception {
        when(jobs.submit(eq("draft"), anyString()))
                .thenReturn(new JobView(ID, "draft", JobStatus.QUEUED, 1, null, null, null));
        var file = new MockMultipartFile("file", "draft.md", "text/markdown", TEXT.getBytes(StandardCharsets.UTF_8));

        mvc.perform(multipart("/api/manuscripts").file(file))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.title").value("draft"));
    }

    @Test
    void otherFileTypesAreRejected() throws Exception {
        var file = new MockMultipartFile("file", "draft.pdf", "application/pdf", new byte[] {1, 2, 3});
        mvc.perform(multipart("/api/manuscripts").file(file))
                .andExpect(status().isUnsupportedMediaType());
        verifyNoInteractions(jobs);
    }

    @Test
    void invalidUtf8IsRejected() throws Exception {
        byte[] bad = new byte[300];
        java.util.Arrays.fill(bad, (byte) 0xC3);
        var file = new MockMultipartFile("file", "draft.txt", "text/plain", bad);
        mvc.perform(multipart("/api/manuscripts").file(file)).andExpect(status().isBadRequest());
    }

    @Test
    void reportIsEmbeddedAsJsonNotAsString() throws Exception {
        when(jobs.find(ID)).thenReturn(Optional.of(new JobView(ID, "Paper", JobStatus.DONE, 1, 2L, null,
                "{\"checks\":{\"issues\":[{\"code\":\"missing_section\"}]}}")));

        mvc.perform(get("/api/manuscripts/" + ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.report.checks.issues[0].code").value("missing_section"));
    }

    @Test
    void unknownJobIs404AndMalformedIdIs400() throws Exception {
        when(jobs.find(ID)).thenReturn(Optional.empty());
        mvc.perform(get("/api/manuscripts/" + ID)).andExpect(status().isNotFound());
        mvc.perform(get("/api/manuscripts/not-an-id")).andExpect(status().isBadRequest());
    }
}
