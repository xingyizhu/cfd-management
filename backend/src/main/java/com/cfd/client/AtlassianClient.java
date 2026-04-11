package com.cfd.client;

import com.cfd.config.AppProperties;
import com.cfd.model.TeamMemberDto;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;
import java.util.*;

@Slf4j
@Component
@RequiredArgsConstructor
public class AtlassianClient {

    private final AppProperties props;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    private HttpHeaders authHeaders() {
        String credentials = props.getAtlassian().getUserEmail() + ":" + props.getAtlassian().getApiToken();
        String encoded = Base64.getEncoder().encodeToString(credentials.getBytes());
        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Basic " + encoded);
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));
        return headers;
    }

    public List<TeamMemberDto> getTeamMembers() {
        String url = "https://api.atlassian.com/gateway/api/public/teams/v1/org/"
                + props.getAtlassian().getOrgId()
                + "/teams/"
                + props.getAtlassian().getTeamId()
                + "/members";

        HttpHeaders headers = authHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        Map<String, Object> body = Map.of("maxResults", 100);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        ResponseEntity<JsonNode> resp = restTemplate.exchange(url, HttpMethod.POST, entity, JsonNode.class);
        JsonNode results = resp.getBody().path("results");

        List<String> accountIds = new ArrayList<>();
        for (JsonNode member : results) {
            String id = member.path("accountId").asText();
            if (!id.isEmpty()) accountIds.add(id);
        }

        if (accountIds.isEmpty()) return List.of();

        return fetchUserProfilesBulk(accountIds);
    }

    private List<TeamMemberDto> fetchUserProfilesBulk(List<String> accountIds) {
        String bulkUrl = props.getAtlassian().getCloudUrl() + "/rest/api/3/user/bulk";
        Map<String, TeamMemberDto> profileMap = new LinkedHashMap<>();

        int batchSize = 100;
        for (int i = 0; i < accountIds.size(); i += batchSize) {
            List<String> batch = accountIds.subList(i, Math.min(i + batchSize, accountIds.size()));
            int startAt = 0;

            while (true) {
                UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(bulkUrl)
                        .queryParam("startAt", startAt)
                        .queryParam("maxResults", batchSize);
                for (String id : batch) {
                    builder.queryParam("accountId", id);
                }

                URI bulkUri = builder.encode().build().toUri();
                HttpEntity<Void> entity = new HttpEntity<>(authHeaders());
                ResponseEntity<JsonNode> resp = restTemplate.exchange(
                        bulkUri, HttpMethod.GET, entity, JsonNode.class);

                JsonNode payload = resp.getBody();
                for (JsonNode user : payload.path("values")) {
                    String accountId = user.path("accountId").asText();
                    if (accountId.isEmpty()) continue;
                    TeamMemberDto dto = new TeamMemberDto();
                    dto.setAccountId(accountId);
                    dto.setDisplayName(user.path("displayName").asText(accountId));
                    dto.setEmailAddress(user.path("emailAddress").asText(""));
                    dto.setActive(user.path("active").asBoolean(true));
                    profileMap.put(accountId, dto);
                }

                if (payload.path("isLast").asBoolean(true)) break;
                startAt += payload.path("maxResults").asInt(batchSize);
            }
        }

        // Return in original order, fallback if profile not found
        List<TeamMemberDto> result = new ArrayList<>();
        for (String id : accountIds) {
            if (profileMap.containsKey(id)) {
                result.add(profileMap.get(id));
            } else {
                TeamMemberDto fallback = new TeamMemberDto();
                fallback.setAccountId(id);
                fallback.setDisplayName(id);
                fallback.setEmailAddress("");
                fallback.setActive(true);
                result.add(fallback);
            }
        }
        return result;
    }

    public List<Map<String, Object>> searchIssues(
            List<String> accountIds, String dateFrom, String dateTo) {

        String idsStr = String.join(", ", accountIds);
        String jql = String.format(
                "worklogAuthor in (%s) AND worklogDate >= \"%s\" AND worklogDate <= \"%s\"",
                idsStr, dateFrom, dateTo);

        List<String> fields = List.of(
                "summary", "status", "project", "issuetype",
                "assignee", "timespent", "timeoriginalestimate", "worklog");

        String url = props.getAtlassian().getCloudUrl() + "/rest/api/3/search/jql";
        List<Map<String, Object>> issues = new ArrayList<>();
        String nextPageToken = null;

        while (true) {
            UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(url)
                    .queryParam("jql", jql)
                    .queryParam("fields", String.join(",", fields))
                    .queryParam("maxResults", 100);
            if (nextPageToken != null) {
                builder.queryParam("nextPageToken", nextPageToken);
            }

            URI searchUri = builder.encode().build().toUri();
            HttpEntity<Void> entity = new HttpEntity<>(authHeaders());
            ResponseEntity<JsonNode> resp = restTemplate.exchange(
                    searchUri, HttpMethod.GET, entity, JsonNode.class);

            JsonNode data = resp.getBody();
            JsonNode batch = data.path("issues");

            for (JsonNode issue : batch) {
                Map<String, Object> issueMap = objectMapper.convertValue(issue, Map.class);

                // If worklog total > returned count, fetch all
                JsonNode wl = issue.path("fields").path("worklog");
                int total = wl.path("total").asInt(0);
                int returned = wl.path("worklogs").size();
                if (total > returned) {
                    String issueId = issue.path("id").asText();
                    List<Map<String, Object>> allWorklogs = fetchAllWorklogs(issueId);
                    ((Map<String, Object>) ((Map<String, Object>) issueMap.get("fields")).get("worklog"))
                            .put("worklogs", allWorklogs);
                }

                issues.add(issueMap);
            }

            if (data.path("isLast").asBoolean(false)) break;
            JsonNode nextToken = data.path("nextPageToken");
            if (nextToken.isMissingNode() || nextToken.isNull()) break;
            nextPageToken = nextToken.asText();
        }

        return issues;
    }

    public List<Map<String, Object>> fetchAllWorklogs(String issueId) {
        String url = props.getAtlassian().getCloudUrl() + "/rest/api/3/issue/" + issueId + "/worklog";
        List<Map<String, Object>> worklogs = new ArrayList<>();
        int startAt = 0;

        while (true) {
            URI wlUri = UriComponentsBuilder.fromHttpUrl(url)
                    .queryParam("startAt", startAt)
                    .queryParam("maxResults", 100)
                    .encode().build().toUri();

            HttpEntity<Void> entity = new HttpEntity<>(authHeaders());
            ResponseEntity<JsonNode> resp = restTemplate.exchange(
                    wlUri, HttpMethod.GET, entity, JsonNode.class);

            JsonNode data = resp.getBody();
            JsonNode batch = data.path("worklogs");
            for (JsonNode w : batch) {
                worklogs.add(objectMapper.convertValue(w, Map.class));
            }

            startAt += batch.size();
            if (startAt >= data.path("total").asInt(0)) break;

            try { Thread.sleep(100); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        }

        return worklogs;
    }
}
