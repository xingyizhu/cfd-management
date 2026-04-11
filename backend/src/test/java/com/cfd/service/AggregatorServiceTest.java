package com.cfd.service;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anySet;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AggregatorServiceTest {

    @Test
    void shouldAggregateRangeRowsAndDeduplicateEstimatedIssues() {
        HolidayService holidayService = mock(HolidayService.class);
        AggregatorService aggregatorService = new AggregatorService(holidayService);

        List<Map<String, Object>> dailyRows = List.of(
                row("account_id", "u1", "display_name", "Alice", "logged_sec", 7200L),
                row("account_id", "u1", "display_name", "Alice", "logged_sec", 3600L),
                row("account_id", "u2", "display_name", "Bob", "logged_sec", 1800L)
        );
        List<Map<String, Object>> entryRows = List.of(
                row("account_id", "u1", "issue_key", "CFD-1", "estimated_sec", 7200L),
                row("account_id", "u1", "issue_key", "CFD-1", "estimated_sec", 7200L),
                row("account_id", "u2", "issue_key", "CFD-2", "estimated_sec", 3600L)
        );
        List<Map<String, Object>> members = List.of(
                row("accountId", "u1", "displayName", "Alice"),
                row("accountId", "u2", "displayName", "Bob")
        );

        List<Map<String, Object>> result = aggregatorService.aggregateMemberRangeRows(
                dailyRows, entryRows, members, "2026-04-07", "2026-04-11");

        assertEquals(2, result.size());
        assertEquals(10800L, result.get(0).get("logged_sec"));
        assertEquals(7200L, result.get(0).get("estimated_sec"));
        assertEquals(1, result.get(0).get("issue_count"));
    }

    @Test
    void shouldEnsureZeroRowsForMissingMembersOnWorkdays() {
        HolidayService holidayService = mock(HolidayService.class);
        when(holidayService.iterWorkdays(eq("2026-04-10"), eq("2026-04-10"), anySet()))
                .thenReturn(List.of("2026-04-10"));

        AggregatorService aggregatorService = new AggregatorService(holidayService);
        List<Map<String, Object>> rows = List.of(
                row("account_id", "u1", "display_name", "Alice", "work_date", "2026-04-10", "logged_sec", 3600L, "estimated_sec", 1800L, "issue_count", 1, "issue_keys", List.of("CFD-1"))
        );
        List<Map<String, Object>> members = List.of(
                row("accountId", "u1", "displayName", "Alice"),
                row("accountId", "u2", "displayName", "Bob")
        );

        List<Map<String, Object>> result = aggregatorService.ensureDailyMemberRowsForRange(
                rows, members, "2026-04-10", "2026-04-10", Set.of());

        assertEquals(2, result.size());
        assertEquals("Bob", result.get(1).get("display_name"));
        assertEquals(0L, result.get(1).get("logged_sec"));
    }

    private static Map<String, Object> row(Object... values) {
        Map<String, Object> row = new LinkedHashMap<>();
        for (int index = 0; index < values.length; index += 2) {
            row.put(String.valueOf(values[index]), values[index + 1]);
        }
        return row;
    }
}
