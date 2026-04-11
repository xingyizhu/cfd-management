package com.cfd.controller;

import com.cfd.client.AtlassianClient;
import com.cfd.model.SyncRequestDto;
import com.cfd.model.SyncResultDto;
import com.cfd.service.ReportService;
import com.cfd.service.HolidayService;
import com.cfd.service.SyncService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/sync")
@RequiredArgsConstructor
public class SyncController {

    private final SyncService syncService;
    private final AtlassianClient atlassianClient;
    private final HolidayService holidayService;
    private final ReportService reportService;

    /**
     * POST /api/sync
     * Body: { "dateFrom": "YYYY-MM-DD", "dateTo": "YYYY-MM-DD", "forceRefresh": false }
     */
    @PostMapping
    public SyncResultDto sync(@RequestBody(required = false) SyncRequestDto body) {
        String dateFrom = body != null && body.getDateFrom() != null ? body.getDateFrom() : LocalDate.now().toString();
        String dateTo = body != null && body.getDateTo() != null ? body.getDateTo() : LocalDate.now().toString();
        boolean forceRefresh = body != null && body.isForceRefresh();

        LocalDate start = LocalDate.parse(dateFrom);
        LocalDate end = LocalDate.parse(dateTo);

        LocalDate normalizedStart = start.isBefore(end) ? start : end;
        LocalDate normalizedEnd = start.isBefore(end) ? end : start;
        Set<String> holidays = holidayService.getHolidaysForRange(normalizedStart, normalizedEnd);
        var members = reportService.toMemberMaps(atlassianClient.getTeamMembers());

        Map<String, Integer> counts;
        if (forceRefresh) {
            counts = syncService.syncForceRefreshWindow(normalizedEnd, members, holidays);
        } else {
            counts = syncService.syncRangeWindow(normalizedStart, normalizedEnd, members, holidays);
        }

        SyncResultDto result = new SyncResultDto();
        result.setEntries(counts.getOrDefault("entries", 0));
        result.setDaily(counts.getOrDefault("daily", 0));
        result.setWeekly(counts.getOrDefault("weekly", 0));
        result.setQuarterly(counts.getOrDefault("quarterly", 0));
        return result;
    }
}
