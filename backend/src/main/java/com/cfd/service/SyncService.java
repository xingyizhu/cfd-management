package com.cfd.service;

import com.cfd.client.AtlassianClient;
import com.cfd.client.SupabaseClient;
import com.cfd.model.TeamMemberDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Jira → Supabase 同步服务。对应 Python sync.py 模块。
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class SyncService {

    private final AtlassianClient atlassianClient;
    private final SupabaseClient supabaseClient;
    private final AggregatorService aggregatorService;
    private final HolidayService holidayService;

    public Map<String, Integer> syncRangeWindow(
            LocalDate dateFrom,
            LocalDate dateTo,
            List<Map<String, Object>> members,
            Set<String> holidays) {

        LocalDate start = dateFrom.isBefore(dateTo) ? dateFrom : dateTo;
        LocalDate end = dateFrom.isBefore(dateTo) ? dateTo : dateFrom;

        Set<String> memberIds = members.stream()
                .map(m -> (String) m.getOrDefault("accountId", ""))
                .filter(id -> !id.isEmpty())
                .collect(Collectors.toSet());

        List<Map<String, Object>> issues = atlassianClient.searchIssues(
                new ArrayList<>(memberIds), start.toString(), end.toString());

        var stats = aggregatorService.aggregate(issues, memberIds, holidays);
        List<Map<String, Object>> dailyRows = aggregatorService.buildDailyRows(stats);
        dailyRows = aggregatorService.ensureDailyMemberRowsForRange(
                dailyRows, members, start.toString(), end.toString(), holidays);

        List<Map<String, Object>> entryRows = aggregatorService.buildEntryRowsForRange(
                issues, memberIds, start.toString(), end.toString(), holidays);

        Map<String, Integer> counts = supabaseClient.replaceRangeWindowRows(
                start.toString(), end.toString(), dailyRows, entryRows);

        log.info("syncRangeWindow [{} ~ {}]: daily={}, entries={}",
                start, end, counts.get("daily"), counts.get("entries"));
        return counts;
    }

    public Map<String, Integer> syncForceRefreshWindow(
            LocalDate targetDate,
            List<Map<String, Object>> members,
            Set<String> holidays) {

        LocalDate qStart = quarterStart(targetDate);
        String dateFrom = qStart.toString();
        String dateTo = targetDate.toString();
        int q = (targetDate.getMonthValue() - 1) / 3 + 1;
        String quarterKey = targetDate.getYear() + "-Q" + q;

        Set<String> memberIds = members.stream()
                .map(m -> (String) m.getOrDefault("accountId", ""))
                .filter(id -> !id.isEmpty())
                .collect(Collectors.toSet());

        List<Map<String, Object>> issues = atlassianClient.searchIssues(
                new ArrayList<>(memberIds), dateFrom, dateTo);

        var stats = aggregatorService.aggregate(issues, memberIds, holidays);
        List<Map<String, Object>> dailyRows = aggregatorService.buildDailyRows(stats);
        List<Map<String, Object>> weeklyRows = aggregatorService.buildWeeklyRows(stats);
        List<Map<String, Object>> quarterlyRows = aggregatorService.buildQuarterlyRows(stats);
        List<Map<String, Object>> entryRows = aggregatorService.buildEntryRowsForRange(
                issues, memberIds, dateFrom, dateTo, holidays);

        Map<String, Integer> counts = supabaseClient.replaceSyncWindowRows(
                dateFrom, dateTo, quarterKey, dailyRows, weeklyRows, quarterlyRows, entryRows);

        log.info("syncForceRefresh [{}~{}]: daily={}, weekly={}, quarterly={}, entries={}",
                dateFrom, dateTo,
                counts.get("daily"), counts.get("weekly"), counts.get("quarterly"), counts.get("entries"));
        return counts;
    }

    private LocalDate quarterStart(LocalDate d) {
        int firstMonth = (d.getMonthValue() - 1) / 3 * 3 + 1;
        return LocalDate.of(d.getYear(), firstMonth, 1);
    }
}
