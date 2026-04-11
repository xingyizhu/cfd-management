package com.cfd.service;

import com.cfd.model.WorklogRangeRowDto;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.*;
import java.util.*;

/**
 * 工时聚合服务。对应 Python aggregator.py 模块。
 */
@Service
@RequiredArgsConstructor
public class AggregatorService {

    private final HolidayService holidayService;

    // ── Aggregate issues to daily/weekly/quarterly stats ─────────────────

    public Map<String, Map<String, Map<String, Object>>> aggregate(
            List<Map<String, Object>> issues,
            Set<String> memberIds,
            Set<String> holidays) {

        Map<String, Map<String, Map<String, Object>>> stats = new HashMap<>();
        for (String dim : List.of("daily", "weekly", "quarterly")) {
            stats.put(dim, new HashMap<>());
        }

        for (Map<String, Object> issue : issues) {
            String key = (String) issue.get("key");
            Map<String, Object> fields = (Map<String, Object>) issue.getOrDefault("fields", Map.of());
            long origEst = toLong(fields.get("timeoriginalestimate"));
            Map<String, Object> worklogObj = (Map<String, Object>) fields.getOrDefault("worklog", Map.of());
            List<Map<String, Object>> worklogs = (List<Map<String, Object>>) worklogObj.getOrDefault("worklogs", List.of());

            for (Map<String, Object> wl : worklogs) {
                Map<String, Object> author = (Map<String, Object>) wl.getOrDefault("author", Map.of());
                String aid = (String) author.getOrDefault("accountId", "");
                if (!memberIds.contains(aid)) continue;

                String started = ((String) wl.getOrDefault("started", "")).substring(0, 10);
                if (!holidayService.isWorkday(started, holidays)) continue;

                long ts = toLong(wl.get("timeSpentSeconds"));
                String name = (String) author.getOrDefault("displayName", aid);
                LocalDate dObj = LocalDate.parse(started);

                Map<String, String> periodMap = Map.of(
                        "daily", started,
                        "weekly", weekStart(dObj),
                        "quarterly", quarterKey(dObj)
                );

                for (Map.Entry<String, String> entry : periodMap.entrySet()) {
                    String dim = entry.getKey();
                    String pk = entry.getValue();

                    stats.get(dim)
                            .computeIfAbsent(aid, a -> new HashMap<>())
                            .computeIfAbsent(pk, p -> newSlot());

                    @SuppressWarnings("unchecked")
                    Map<String, Object> slot = (Map<String, Object>) stats.get(dim).get(aid).get(pk);
                    slot.put("logged", toLong(slot.get("logged")) + ts);
                    slot.put("name", name);
                    ((Set<String>) slot.get("issues")).add(key);

                    if ("daily".equals(dim)) {
                        Set<String> counted = (Set<String>) slot.get("counted");
                        if (!counted.contains(key)) {
                            slot.put("estimated", toLong(slot.get("estimated")) + origEst);
                            counted.add(key);
                        }
                    }
                }
            }
        }
        return stats;
    }

    private Map<String, Object> newSlot() {
        Map<String, Object> slot = new HashMap<>();
        slot.put("logged", 0L);
        slot.put("estimated", 0L);
        slot.put("issues", new HashSet<String>());
        slot.put("name", "");
        slot.put("counted", new HashSet<String>());
        return slot;
    }

    public List<Map<String, Object>> buildDailyRows(Map<String, Map<String, Map<String, Object>>> stats) {
        return buildRows(stats.get("daily"), "work_date");
    }

    public List<Map<String, Object>> buildWeeklyRows(Map<String, Map<String, Map<String, Object>>> stats) {
        return buildRows(stats.get("weekly"), "week_start");
    }

    public List<Map<String, Object>> buildQuarterlyRows(Map<String, Map<String, Map<String, Object>>> stats) {
        return buildRows(stats.get("quarterly"), "quarter_key");
    }

    private List<Map<String, Object>> buildRows(Map<String, Map<String, Object>> dimStats, String periodCol) {
        String nowTs = Instant.now().toString();
        List<Map<String, Object>> rows = new ArrayList<>();

        for (Map.Entry<String, Map<String, Object>> aidEntry : dimStats.entrySet()) {
            String aid = aidEntry.getKey();
            for (Map.Entry<String, Object> pkEntry : aidEntry.getValue().entrySet()) {
                String pk = pkEntry.getKey();
                Map<String, Object> slot = (Map<String, Object>) pkEntry.getValue();

                Map<String, Object> row = new LinkedHashMap<>();
                row.put("account_id", aid);
                row.put("display_name", slot.get("name"));
                row.put(periodCol, pk);
                row.put("logged_sec", slot.get("logged"));
                row.put("estimated_sec", slot.get("estimated"));
                Set<String> issues = (Set<String>) slot.get("issues");
                row.put("issue_count", issues.size());
                row.put("issue_keys", new ArrayList<>(issues));
                row.put("updated_at", nowTs);
                rows.add(row);
            }
        }
        return rows;
    }

    // ── Build entry rows ──────────────────────────────────────────────────

    public List<Map<String, Object>> buildEntryRowsForRange(
            List<Map<String, Object>> issues,
            Set<String> memberIds,
            String dateFrom,
            String dateTo,
            Set<String> holidays) {

        LocalDate start = LocalDate.parse(dateFrom);
        LocalDate end = LocalDate.parse(dateTo);
        if (start.isAfter(end)) return List.of();

        String nowTs = Instant.now().toString();
        Map<String, Map<String, Object>> rowByKey = new LinkedHashMap<>();

        for (Map<String, Object> issue : issues) {
            String issueKey = (String) issue.getOrDefault("key", "");
            if (issueKey.isEmpty()) continue;

            Map<String, Object> fields = (Map<String, Object>) issue.getOrDefault("fields", Map.of());
            String issueSummary = (String) fields.getOrDefault("summary", "");
            long estimatedSec = toLong(fields.get("timeoriginalestimate"));

            Map<String, Object> project = (Map<String, Object>) fields.getOrDefault("project", Map.of());
            String projectKey = (String) project.getOrDefault("key", "");
            if (projectKey.isEmpty()) projectKey = deriveProjectKey(issueKey);
            String projectName = (String) project.getOrDefault("name", "");
            if (projectName.isEmpty()) projectName = projectKey;

            Map<String, Object> status = (Map<String, Object>) fields.getOrDefault("status", Map.of());
            String statusName = (String) status.getOrDefault("name", "未知");

            Map<String, Object> worklogObj = (Map<String, Object>) fields.getOrDefault("worklog", Map.of());
            List<Map<String, Object>> worklogs = (List<Map<String, Object>>) worklogObj.getOrDefault("worklogs", List.of());

            for (Map<String, Object> wl : worklogs) {
                Map<String, Object> author = (Map<String, Object>) wl.getOrDefault("author", Map.of());
                String accountId = (String) author.getOrDefault("accountId", "");
                if (!memberIds.contains(accountId)) continue;

                String started = ((String) wl.getOrDefault("started", "")).substring(0, 10);
                try {
                    LocalDate startedDate = LocalDate.parse(started);
                    if (startedDate.isBefore(start) || startedDate.isAfter(end)) continue;
                } catch (Exception e) {
                    continue;
                }
                if (!holidayService.isWorkday(started, holidays)) continue;

                String mapKey = accountId + "|" + started + "|" + issueKey;
                if (!rowByKey.containsKey(mapKey)) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("account_id", accountId);
                    row.put("display_name", author.getOrDefault("displayName", accountId));
                    row.put("work_date", started);
                    row.put("issue_key", issueKey);
                    row.put("issue_summary", issueSummary);
                    row.put("time_sec", 0L);
                    row.put("estimated_sec", estimatedSec);
                    row.put("project_key", projectKey);
                    row.put("project_name", projectName);
                    row.put("status_name", statusName);
                    row.put("updated_at", nowTs);
                    rowByKey.put(mapKey, row);
                }

                Map<String, Object> row = rowByKey.get(mapKey);
                row.put("time_sec", toLong(row.get("time_sec")) + toLong(wl.get("timeSpentSeconds")));
            }
        }

        return new ArrayList<>(rowByKey.values());
    }

    // ── Ensure member rows ────────────────────────────────────────────────

    public List<Map<String, Object>> ensureDailyMemberRowsForRange(
            List<Map<String, Object>> rows,
            List<Map<String, Object>> members,
            String dateFrom,
            String dateTo,
            Set<String> holidays) {

        Map<String, List<Map<String, Object>>> rowsByDate = new HashMap<>();
        for (Map<String, Object> row : rows) {
            String workDate = (String) row.get("work_date");
            if (workDate != null) rowsByDate.computeIfAbsent(workDate, d -> new ArrayList<>()).add(row);
        }

        List<Map<String, Object>> normalized = new ArrayList<>();
        for (String workDate : holidayService.iterWorkdays(dateFrom, dateTo, holidays)) {
            normalized.addAll(
                    ensureMemberRows(rowsByDate.getOrDefault(workDate, List.of()), members, "work_date", workDate)
            );
        }

        normalized.sort(Comparator
                .comparing((Map<String, Object> r) -> (String) r.getOrDefault("work_date", ""))
                .thenComparing(r -> (String) r.getOrDefault("display_name", "")));
        return normalized;
    }

    private List<Map<String, Object>> ensureMemberRows(
            List<Map<String, Object>> rows,
            List<Map<String, Object>> members,
            String periodCol,
            String periodValue) {

        String nowTs = Instant.now().toString();
        Map<String, Map<String, Object>> rowByAccount = new LinkedHashMap<>();

        for (Map<String, Object> row : rows) {
            String aid = (String) row.get("account_id");
            if (aid != null) rowByAccount.put(aid, new LinkedHashMap<>(row));
        }

        for (Map<String, Object> member : members) {
            String aid = (String) member.getOrDefault("accountId", "");
            if (aid.isEmpty()) continue;
            String displayName = (String) member.getOrDefault("displayName", aid);

            if (!rowByAccount.containsKey(aid)) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("account_id", aid);
                row.put("display_name", displayName);
                row.put(periodCol, periodValue);
                row.put("logged_sec", 0L);
                row.put("estimated_sec", 0L);
                row.put("issue_count", 0);
                row.put("issue_keys", List.of());
                row.put("updated_at", nowTs);
                rowByAccount.put(aid, row);
            }
        }

        List<Map<String, Object>> result = new ArrayList<>(rowByAccount.values());
        result.sort(Comparator
                .comparingLong((Map<String, Object> r) -> -toLong(r.get("logged_sec")))
                .thenComparing(r -> (String) r.getOrDefault("display_name", "")));
        return result;
    }

    // ── Range aggregate ───────────────────────────────────────────────────

    public List<Map<String, Object>> aggregateMemberRangeRows(
            List<Map<String, Object>> dailyRows,
            List<Map<String, Object>> entryRows,
            List<Map<String, Object>> members,
            String dateFrom,
            String dateTo) {

        String nowTs = Instant.now().toString();
        Map<String, Map<String, Object>> rowByAccount = new LinkedHashMap<>();

        for (Map<String, Object> member : members) {
            String aid = (String) member.getOrDefault("accountId", "");
            if (aid.isEmpty()) continue;
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("account_id", aid);
            row.put("display_name", member.getOrDefault("displayName", aid));
            row.put("date_from", dateFrom);
            row.put("date_to", dateTo);
            row.put("logged_sec", 0L);
            row.put("estimated_sec", 0L);
            row.put("issue_count", 0);
            row.put("issue_keys", new ArrayList<String>());
            row.put("updated_at", nowTs);
            rowByAccount.put(aid, row);
        }

        for (Map<String, Object> row : dailyRows) {
            String aid = (String) row.get("account_id");
            if (rowByAccount.containsKey(aid)) {
                Map<String, Object> target = rowByAccount.get(aid);
                target.put("logged_sec", toLong(target.get("logged_sec")) + toLong(row.get("logged_sec")));
            }
        }

        Map<String, Set<String>> seenIssues = new HashMap<>();
        for (Map<String, Object> row : entryRows) {
            String aid = (String) row.get("account_id");
            String issueKey = (String) row.getOrDefault("issue_key", "");
            if (!rowByAccount.containsKey(aid) || issueKey.isEmpty()) continue;

            seenIssues.computeIfAbsent(aid, a -> new HashSet<>());
            if (seenIssues.get(aid).contains(issueKey)) continue;

            seenIssues.get(aid).add(issueKey);
            Map<String, Object> target = rowByAccount.get(aid);
            target.put("estimated_sec", toLong(target.get("estimated_sec")) + toLong(row.get("estimated_sec")));
            ((List<String>) target.get("issue_keys")).add(issueKey);
        }

        for (Map<String, Object> row : rowByAccount.values()) {
            row.put("issue_count", ((List<?>) row.get("issue_keys")).size());
        }

        List<Map<String, Object>> result = new ArrayList<>(rowByAccount.values());
        result.sort(Comparator
                .comparingLong((Map<String, Object> r) -> -toLong(r.get("logged_sec")))
                .thenComparing(r -> (String) r.getOrDefault("display_name", "")));
        return result;
    }

    // ── Under-logged ──────────────────────────────────────────────────────

    public List<Map<String, Object>> findUnderLoggedRange(
            List<Map<String, Object>> rangeRows, double requiredHours) {

        long requiredSec = (long) (requiredHours * 3600);
        List<Map<String, Object>> result = new ArrayList<>();

        for (Map<String, Object> row : rangeRows) {
            long loggedSec = toLong(row.get("logged_sec"));
            if (loggedSec >= requiredSec) continue;

            double loggedHours = Math.round(loggedSec / 3600.0 * 100) / 100.0;
            double missingHours = Math.round((requiredHours - loggedHours) * 100) / 100.0;

            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("accountId", row.get("account_id"));
            entry.put("name", row.get("display_name"));
            entry.put("logged_hours", loggedHours);
            entry.put("required_hours", Math.round(requiredHours * 100) / 100.0);
            entry.put("missing_hours", missingHours);
            result.add(entry);
        }

        result.sort(Comparator
                .comparingDouble((Map<String, Object> r) -> -(double) r.get("missing_hours"))
                .thenComparing(r -> (String) r.getOrDefault("name", "")));
        return result;
    }

    // ── Estimate board aggregation ────────────────────────────────────────

    public List<Map<String, Object>> aggregateHighEstimateRangeEntries(
            List<Map<String, Object>> entryRows, long thresholdSec) {

        Map<String, Map<String, Object>> rowByKey = new LinkedHashMap<>();
        for (Map<String, Object> row : entryRows) {
            String aid = (String) row.getOrDefault("account_id", "");
            String issueKey = (String) row.getOrDefault("issue_key", "");
            if (aid.isEmpty() || issueKey.isEmpty()) continue;

            String mapKey = aid + "|" + issueKey;
            rowByKey.computeIfAbsent(mapKey, k -> {
                Map<String, Object> r = new LinkedHashMap<>();
                r.put("account_id", aid);
                r.put("display_name", row.getOrDefault("display_name", aid));
                r.put("issue_key", issueKey);
                r.put("issue_summary", row.getOrDefault("issue_summary", ""));
                r.put("estimated_sec", toLong(row.get("estimated_sec")));
                r.put("time_sec", 0L);
                return r;
            });

            Map<String, Object> r = rowByKey.get(mapKey);
            r.put("time_sec", toLong(r.get("time_sec")) + toLong(row.get("time_sec")));
            r.put("estimated_sec", Math.max(toLong(r.get("estimated_sec")), toLong(row.get("estimated_sec"))));
        }

        List<Map<String, Object>> result = rowByKey.values().stream()
                .filter(r -> toLong(r.get("estimated_sec")) > thresholdSec)
                .collect(java.util.stream.Collectors.toList());

        result.sort(Comparator
                .comparingLong((Map<String, Object> r) -> -toLong(r.get("estimated_sec")))
                .thenComparingLong(r -> -toLong(r.get("time_sec")))
                .thenComparing(r -> (String) r.getOrDefault("issue_key", "")));
        return result;
    }

    public List<Map<String, Object>> aggregateNoEstimateRangeEntries(List<Map<String, Object>> entryRows) {
        Map<String, Map<String, Object>> rowByKey = new LinkedHashMap<>();
        for (Map<String, Object> row : entryRows) {
            String aid = (String) row.getOrDefault("account_id", "");
            String issueKey = (String) row.getOrDefault("issue_key", "");
            if (aid.isEmpty() || issueKey.isEmpty()) continue;

            String mapKey = aid + "|" + issueKey;
            rowByKey.computeIfAbsent(mapKey, k -> {
                Map<String, Object> r = new LinkedHashMap<>();
                r.put("account_id", aid);
                r.put("display_name", row.getOrDefault("display_name", aid));
                r.put("issue_key", issueKey);
                r.put("issue_summary", row.getOrDefault("issue_summary", ""));
                r.put("estimated_sec", toLong(row.get("estimated_sec")));
                r.put("time_sec", 0L);
                return r;
            });

            Map<String, Object> r = rowByKey.get(mapKey);
            r.put("time_sec", toLong(r.get("time_sec")) + toLong(row.get("time_sec")));
            r.put("estimated_sec", Math.max(toLong(r.get("estimated_sec")), toLong(row.get("estimated_sec"))));
        }

        List<Map<String, Object>> result = rowByKey.values().stream()
                .filter(r -> toLong(r.get("estimated_sec")) == 0)
                .collect(java.util.stream.Collectors.toList());

        result.sort(Comparator
                .comparingLong((Map<String, Object> r) -> -toLong(r.get("time_sec")))
                .thenComparing(r -> (String) r.getOrDefault("issue_key", "")));
        return result;
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    private String weekStart(LocalDate d) {
        return d.minusDays(d.getDayOfWeek().getValue() - 1).toString();
    }

    private String quarterKey(LocalDate d) {
        int q = (d.getMonthValue() - 1) / 3 + 1;
        return d.getYear() + "-Q" + q;
    }

    private String deriveProjectKey(String issueKey) {
        int idx = issueKey.indexOf('-');
        return idx > 0 ? issueKey.substring(0, idx).trim() : issueKey.trim();
    }

    public static long toLong(Object val) {
        if (val == null) return 0L;
        if (val instanceof Long l) return l;
        if (val instanceof Integer i) return i.longValue();
        if (val instanceof Number n) return n.longValue();
        try { return Long.parseLong(val.toString()); } catch (Exception e) { return 0L; }
    }
}
