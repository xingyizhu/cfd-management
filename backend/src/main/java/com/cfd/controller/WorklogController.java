package com.cfd.controller;

import com.cfd.client.SupabaseClient;
import com.cfd.model.ReportSummaryDto;
import com.cfd.model.WorklogBucketRowDto;
import com.cfd.model.WorklogEntryDto;
import com.cfd.service.ReportService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class WorklogController {

    private final SupabaseClient supabaseClient;
    private final ReportService reportService;

    /**
     * GET /api/reports/summary?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD
     */
    @GetMapping({"/worklog/range", "/reports/summary"})
    public ReportSummaryDto getSummary(
            @RequestParam String dateFrom,
            @RequestParam String dateTo) {
        return reportService.buildSummary(LocalDate.parse(dateFrom), LocalDate.parse(dateTo));
    }

    @GetMapping({"/worklog/entries", "/reports/entries"})
    public List<WorklogEntryDto> getEntries(
            @RequestParam String dateFrom,
            @RequestParam String dateTo) {
        return supabaseClient.fetchEntriesRange(dateFrom, dateTo).stream().map(this::toEntryDto).toList();
    }

    @GetMapping("/reports/daily")
    public List<WorklogBucketRowDto> getDaily(@RequestParam String workDate) {
        return reportService.toBucketRows(supabaseClient.fetchDaily(workDate));
    }

    @GetMapping("/reports/weekly")
    public List<WorklogBucketRowDto> getWeekly(@RequestParam String weekStart) {
        return reportService.toBucketRows(supabaseClient.fetchWeekly(weekStart));
    }

    @GetMapping("/reports/quarterly")
    public List<WorklogBucketRowDto> getQuarterly(@RequestParam String quarterKey) {
        return reportService.toBucketRows(supabaseClient.fetchQuarterly(quarterKey));
    }

    private WorklogEntryDto toEntryDto(Map<String, Object> row) {
        WorklogEntryDto dto = new WorklogEntryDto();
        dto.setAccountId(String.valueOf(row.getOrDefault("account_id", "")));
        dto.setDisplayName(String.valueOf(row.getOrDefault("display_name", "")));
        dto.setWorkDate(String.valueOf(row.getOrDefault("work_date", "")));
        dto.setIssueKey(String.valueOf(row.getOrDefault("issue_key", "")));
        dto.setIssueSummary(String.valueOf(row.getOrDefault("issue_summary", "")));
        dto.setTimeSec(((Number) row.getOrDefault("time_sec", 0)).longValue());
        dto.setEstimatedSec(((Number) row.getOrDefault("estimated_sec", 0)).longValue());
        dto.setProjectKey(String.valueOf(row.getOrDefault("project_key", "")));
        dto.setProjectName(String.valueOf(row.getOrDefault("project_name", "")));
        dto.setStatusName(String.valueOf(row.getOrDefault("status_name", "")));
        return dto;
    }
}
