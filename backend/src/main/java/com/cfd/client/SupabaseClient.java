package com.cfd.client;

import com.cfd.config.AppProperties;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.time.LocalDate;
import java.util.*;

@Slf4j
@Component
@RequiredArgsConstructor
public class SupabaseClient {

    private final AppProperties props;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    private HttpHeaders baseHeaders() {
        String key = props.getSupabase().getAnonKey();
        HttpHeaders headers = new HttpHeaders();
        headers.set("apikey", key);
        headers.set("Authorization", "Bearer " + key);
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));
        return headers;
    }

    private HttpHeaders upsertHeaders() {
        HttpHeaders headers = baseHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Prefer", "resolution=merge-duplicates,return=minimal");
        return headers;
    }

    private HttpHeaders deleteHeaders() {
        HttpHeaders headers = baseHeaders();
        headers.set("Prefer", "return=minimal");
        return headers;
    }

    private String baseUrl(String table) {
        return props.getSupabase().getUrl() + "/rest/v1/" + table;
    }

    // ── Fetch ────────────────────────────────────────────────────────────

    public List<Map<String, Object>> fetchDailyRange(String dateFrom, String dateTo) {
        String base = baseUrl("worklog_daily")
                + "?work_date=gte." + dateFrom
                + "&work_date=lte." + dateTo
                + "&order=work_date.asc,display_name.asc";
        return fetchPaginated(base, 15_000, 2000);
    }

    public List<Map<String, Object>> fetchDaily(String workDate) {
        String base = baseUrl("worklog_daily")
                + "?work_date=eq." + workDate
                + "&order=display_name.asc";
        return fetchPaginated(base, 10_000, 2000);
    }

    public List<Map<String, Object>> fetchWeekly(String weekStart) {
        String base = baseUrl("worklog_weekly")
                + "?week_start=eq." + weekStart
                + "&order=display_name.asc";
        return fetchPaginated(base, 10_000, 2000);
    }

    public List<Map<String, Object>> fetchQuarterly(String quarterKey) {
        String base = baseUrl("worklog_quarterly")
                + "?quarter_key=eq." + quarterKey
                + "&order=display_name.asc";
        return fetchPaginated(base, 10_000, 2000);
    }

    public List<Map<String, Object>> fetchEntriesRange(String dateFrom, String dateTo) {
        String base = baseUrl("worklog_entries")
                + "?work_date=gte." + dateFrom
                + "&work_date=lte." + dateTo
                + "&order=work_date.asc,issue_key.asc,account_id.asc";
        return fetchPaginated(base, 20_000, 2000);
    }

    public List<Map<String, Object>> fetchEntriesRangeForMemberAggregate(String dateFrom, String dateTo) {
        String base = baseUrl("worklog_entries")
                + "?select=account_id,work_date,issue_key,estimated_sec"
                + "&work_date=gte." + dateFrom
                + "&work_date=lte." + dateTo;
        return fetchPaginated(base, 15_000, 2000);
    }

    private List<Map<String, Object>> fetchPaginated(String baseUrl, int timeoutMs, int pageSize) {
        List<Map<String, Object>> rows = new ArrayList<>();
        int offset = 0;

        while (true) {
            String url = baseUrl + "&limit=" + pageSize + "&offset=" + offset;
            HttpEntity<Void> entity = new HttpEntity<>(baseHeaders());
            ResponseEntity<List> resp = restTemplate.exchange(url, HttpMethod.GET, entity, List.class);

            List<Map<String, Object>> batch = Optional.ofNullable(resp.getBody()).orElse(List.of());
            rows.addAll(batch);
            if (batch.size() < pageSize) break;
            offset += pageSize;
        }

        return rows;
    }

    // ── Upsert ───────────────────────────────────────────────────────────

    public int upsertRows(String table, List<Map<String, Object>> rows) {
        if (rows.isEmpty()) return 0;

        Map<String, String> conflictKeys = Map.of(
                "worklog_daily", "account_id,work_date",
                "worklog_weekly", "account_id,week_start",
                "worklog_quarterly", "account_id,quarter_key"
        );

        String url = conflictKeys.containsKey(table)
                ? baseUrl(table) + "?on_conflict=" + conflictKeys.get(table)
                : baseUrl(table);

        HttpEntity<List<Map<String, Object>>> entity = new HttpEntity<>(rows, upsertHeaders());
        restTemplate.exchange(url, HttpMethod.POST, entity, Void.class);
        return rows.size();
    }

    public int upsertEntryRows(List<Map<String, Object>> rows) {
        if (rows.isEmpty()) return 0;

        String url = baseUrl("worklog_entries") + "?on_conflict=account_id,work_date,issue_key";
        HttpEntity<List<Map<String, Object>>> entity = new HttpEntity<>(rows, upsertHeaders());

        try {
            restTemplate.exchange(url, HttpMethod.POST, entity, Void.class);
            return rows.size();
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage().toLowerCase() : "";
            boolean isExtendedFieldError = msg.contains("project_key")
                    || msg.contains("project_name")
                    || msg.contains("status_name");

            if (!isExtendedFieldError) throw e;

            // Fallback: strip extended fields
            List<String> legacyCols = List.of("account_id", "display_name", "work_date",
                    "issue_key", "issue_summary", "time_sec", "estimated_sec", "updated_at");
            List<Map<String, Object>> legacyRows = rows.stream().map(row -> {
                Map<String, Object> r = new LinkedHashMap<>();
                for (String col : legacyCols) {
                    if (row.containsKey(col)) r.put(col, row.get(col));
                }
                return r;
            }).toList();

            HttpEntity<List<Map<String, Object>>> fallbackEntity = new HttpEntity<>(legacyRows, upsertHeaders());
            restTemplate.exchange(url, HttpMethod.POST, fallbackEntity, Void.class);
            return legacyRows.size();
        }
    }

    // ── Delete ───────────────────────────────────────────────────────────

    public void deleteByDateRange(String table, String dateFrom, String dateTo, String dateCol) {
        String url = baseUrl(table) + "?" + dateCol + "=gte." + dateFrom + "&" + dateCol + "=lte." + dateTo;
        HttpEntity<Void> entity = new HttpEntity<>(deleteHeaders());
        restTemplate.exchange(url, HttpMethod.DELETE, entity, Void.class);
    }

    public void deleteByWeekStarts(String table, List<String> weekStarts) {
        if (weekStarts.isEmpty()) return;
        String inClause = String.join(",", weekStarts);
        String url = baseUrl(table) + "?week_start=in.(" + inClause + ")";
        HttpEntity<Void> entity = new HttpEntity<>(deleteHeaders());
        restTemplate.exchange(url, HttpMethod.DELETE, entity, Void.class);
    }

    public void deleteByQuarterKey(String table, String quarterKey) {
        String url = baseUrl(table) + "?quarter_key=eq." + quarterKey;
        HttpEntity<Void> entity = new HttpEntity<>(deleteHeaders());
        restTemplate.exchange(url, HttpMethod.DELETE, entity, Void.class);
    }

    // ── Replace window ───────────────────────────────────────────────────

    public Map<String, Integer> replaceSyncWindowRows(
            String dateFrom, String dateTo, String quarterKey,
            List<Map<String, Object>> dailyRows,
            List<Map<String, Object>> weeklyRows,
            List<Map<String, Object>> quarterlyRows,
            List<Map<String, Object>> entryRows) {

        List<String> weekStarts = weekStartsInRange(dateFrom, dateTo);

        deleteByDateRange("worklog_entries", dateFrom, dateTo, "work_date");
        deleteByDateRange("worklog_daily", dateFrom, dateTo, "work_date");
        if (!weekStarts.isEmpty()) deleteByWeekStarts("worklog_weekly", weekStarts);
        deleteByQuarterKey("worklog_quarterly", quarterKey);

        return Map.of(
                "entries", upsertEntryRows(entryRows),
                "daily", upsertRows("worklog_daily", dailyRows),
                "weekly", upsertRows("worklog_weekly", weeklyRows),
                "quarterly", upsertRows("worklog_quarterly", quarterlyRows)
        );
    }

    public Map<String, Integer> replaceRangeWindowRows(
            String dateFrom, String dateTo,
            List<Map<String, Object>> dailyRows,
            List<Map<String, Object>> entryRows) {

        deleteByDateRange("worklog_entries", dateFrom, dateTo, "work_date");
        deleteByDateRange("worklog_daily", dateFrom, dateTo, "work_date");

        return Map.of(
                "entries", upsertEntryRows(entryRows),
                "daily", upsertRows("worklog_daily", dailyRows)
        );
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    private List<String> weekStartsInRange(String dateFrom, String dateTo) {
        LocalDate start = LocalDate.parse(dateFrom);
        LocalDate end = LocalDate.parse(dateTo);
        if (start.isAfter(end)) return List.of();

        List<String> weeks = new ArrayList<>();
        LocalDate current = start.minusDays(start.getDayOfWeek().getValue() - 1);
        while (!current.isAfter(end)) {
            weeks.add(current.toString());
            current = current.plusWeeks(1);
        }
        return weeks;
    }
}
