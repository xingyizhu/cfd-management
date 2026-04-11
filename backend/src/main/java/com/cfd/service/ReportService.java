package com.cfd.service;

import com.cfd.client.AtlassianClient;
import com.cfd.client.SupabaseClient;
import com.cfd.config.AppProperties;
import com.cfd.model.RangeMetaDto;
import com.cfd.model.ReminderPreviewDto;
import com.cfd.model.ReportSummaryDto;
import com.cfd.model.TeamMemberDto;
import com.cfd.model.UnderLoggedMemberDto;
import com.cfd.model.WorklogBucketRowDto;
import com.cfd.model.WorklogRangeRowDto;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.temporal.IsoFields;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class ReportService {

    private final SupabaseClient supabaseClient;
    private final AtlassianClient atlassianClient;
    private final AggregatorService aggregatorService;
    private final HolidayService holidayService;
    private final AppProperties appProperties;

    public ReportSummaryDto buildSummary(LocalDate dateFrom, LocalDate dateTo) {
        LocalDate start = dateFrom.isBefore(dateTo) ? dateFrom : dateTo;
        LocalDate end = dateFrom.isBefore(dateTo) ? dateTo : dateFrom;

        Set<String> holidays = holidayService.getHolidaysForRange(start, end);
        RangeMetaDto meta = buildMeta(start, end, holidays);

        List<Map<String, Object>> members = toMemberMaps(atlassianClient.getTeamMembers());
        List<Map<String, Object>> dailyRows = supabaseClient.fetchDailyRange(start.toString(), end.toString());
        List<Map<String, Object>> memberAggregateRows = supabaseClient.fetchEntriesRangeForMemberAggregate(start.toString(), end.toString());
        List<Map<String, Object>> rangeRows = aggregatorService.aggregateMemberRangeRows(
                dailyRows,
                memberAggregateRows,
                members,
                start.toString(),
                end.toString()
        );

        double requiredHours = meta.getWorkdayCount() * appProperties.getBusiness().getDailyTargetHours();

        ReportSummaryDto dto = new ReportSummaryDto();
        dto.setMeta(meta);
        dto.setDailyRows(toBucketRows(dailyRows));
        dto.setWeeklyRows(toBucketRows(supabaseClient.fetchWeekly(meta.getWeekStart())));
        dto.setQuarterlyRows(toBucketRows(supabaseClient.fetchQuarterly(meta.getQuarterKey())));
        dto.setRangeRows(toRangeRows(rangeRows));
        dto.setUnderLogged(toUnderLoggedRows(aggregatorService.findUnderLoggedRange(rangeRows, requiredHours)));
        dto.setCacheHit(true);
        return dto;
    }

    public ReminderPreviewDto previewReminder(LocalDate dateFrom, LocalDate dateTo) {
        ReportSummaryDto summary = buildSummary(dateFrom, dateTo);

        ReminderPreviewDto preview = new ReminderPreviewDto();
        preview.setDateFrom(summary.getMeta().getDateFrom());
        preview.setDateTo(summary.getMeta().getDateTo());
        preview.setWorkdayCount(summary.getMeta().getWorkdayCount());
        preview.setRequiredHours(summary.getMeta().getWorkdayCount() * appProperties.getBusiness().getDailyTargetHours());
        preview.setUnderLogged(summary.getUnderLogged());
        return preview;
    }

    public RangeMetaDto buildMeta(LocalDate start, LocalDate end, Set<String> holidays) {
        RangeMetaDto meta = new RangeMetaDto();
        meta.setDateFrom(start.toString());
        meta.setDateTo(end.toString());
        meta.setDayCount((int) (end.toEpochDay() - start.toEpochDay()) + 1);
        meta.setWorkdayCount(holidayService.countWorkdays(start.toString(), end.toString(), holidays));
        meta.setWeekStart(end.minusDays(end.getDayOfWeek().getValue() - 1L).toString());
        LocalDate quarterStart = end.with(IsoFields.DAY_OF_QUARTER, 1);
        meta.setQuarterStart(quarterStart.toString());
        meta.setQuarterKey(end.getYear() + "-Q" + ((end.getMonthValue() - 1) / 3 + 1));
        return meta;
    }

    public List<Map<String, Object>> toMemberMaps(List<TeamMemberDto> members) {
        return members.stream().map(member -> {
            Map<String, Object> map = new LinkedHashMap<>();
            map.put("accountId", member.getAccountId());
            map.put("displayName", member.getDisplayName());
            map.put("emailAddress", member.getEmailAddress());
            map.put("active", member.isActive());
            return map;
        }).toList();
    }

    public List<WorklogBucketRowDto> toBucketRows(List<Map<String, Object>> rows) {
        List<WorklogBucketRowDto> mapped = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            WorklogBucketRowDto dto = new WorklogBucketRowDto();
            dto.setAccountId(String.valueOf(row.getOrDefault("account_id", "")));
            dto.setDisplayName(String.valueOf(row.getOrDefault("display_name", "")));
            dto.setWorkDate((String) row.get("work_date"));
            dto.setWeekStart((String) row.get("week_start"));
            dto.setQuarterKey((String) row.get("quarter_key"));
            dto.setLoggedSec(AggregatorService.toLong(row.get("logged_sec")));
            dto.setEstimatedSec(AggregatorService.toLong(row.get("estimated_sec")));
            dto.setIssueCount(((Number) row.getOrDefault("issue_count", 0)).intValue());
            Object issueKeys = row.get("issue_keys");
            if (issueKeys instanceof List<?> list) {
                dto.setIssueKeys(list.stream().map(String::valueOf).toList());
            } else {
                dto.setIssueKeys(List.of());
            }
            mapped.add(dto);
        }
        return mapped;
    }

    public List<WorklogRangeRowDto> toRangeRows(List<Map<String, Object>> rows) {
        return rows.stream().map(row -> {
            WorklogRangeRowDto dto = new WorklogRangeRowDto();
            dto.setAccountId(String.valueOf(row.getOrDefault("account_id", "")));
            dto.setDisplayName(String.valueOf(row.getOrDefault("display_name", "")));
            dto.setLoggedSec(AggregatorService.toLong(row.get("logged_sec")));
            dto.setEstimatedSec(AggregatorService.toLong(row.get("estimated_sec")));
            dto.setIssueCount(((Number) row.getOrDefault("issue_count", 0)).intValue());
            Object issueKeys = row.get("issue_keys");
            if (issueKeys instanceof List<?> list) {
                dto.setIssueKeys(list.stream().map(String::valueOf).toList());
            } else {
                dto.setIssueKeys(List.of());
            }
            return dto;
        }).toList();
    }

    public List<UnderLoggedMemberDto> toUnderLoggedRows(List<Map<String, Object>> rows) {
        return rows.stream().map(row -> {
            UnderLoggedMemberDto dto = new UnderLoggedMemberDto();
            dto.setAccountId(String.valueOf(row.getOrDefault("accountId", "")));
            dto.setName(String.valueOf(row.getOrDefault("name", "")));
            dto.setLoggedHours(((Number) row.getOrDefault("logged_hours", 0.0)).doubleValue());
            dto.setRequiredHours(((Number) row.getOrDefault("required_hours", 0.0)).doubleValue());
            dto.setMissingHours(((Number) row.getOrDefault("missing_hours", 0.0)).doubleValue());
            return dto;
        }).toList();
    }
}
