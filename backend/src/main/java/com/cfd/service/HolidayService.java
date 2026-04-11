package com.cfd.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.*;

/**
 * 中国法定节假日判断服务。
 * 优先走 Nager.Date，失败时回退本地静态数据。
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class HolidayService {

    private final RestTemplate restTemplate;

    // 法定节假日（周末之外的额外休息日）
    private static final Map<Integer, Set<String>> HOLIDAYS = new HashMap<>();

    // 调休补班日（本应为周末但需要上班）
    private static final Map<Integer, Set<String>> WORKDAY_OVERRIDES = new HashMap<>();

    static {
        // 2024 法定节假日
        Set<String> h2024 = new HashSet<>(Arrays.asList(
                "2024-01-01",
                "2024-02-10", "2024-02-11", "2024-02-12", "2024-02-13",
                "2024-02-14", "2024-02-15", "2024-02-16", "2024-02-17",
                "2024-04-04", "2024-04-05", "2024-04-06",
                "2024-05-01", "2024-05-02", "2024-05-03", "2024-05-04", "2024-05-05",
                "2024-06-10",
                "2024-09-15", "2024-09-16", "2024-09-17",
                "2024-10-01", "2024-10-02", "2024-10-03", "2024-10-04",
                "2024-10-05", "2024-10-06", "2024-10-07"
        ));
        HOLIDAYS.put(2024, h2024);

        Set<String> w2024 = new HashSet<>(Arrays.asList(
                "2024-02-04", "2024-02-18",
                "2024-04-07",
                "2024-04-28",
                "2024-05-11",
                "2024-09-14",
                "2024-09-29",
                "2024-10-12"
        ));
        WORKDAY_OVERRIDES.put(2024, w2024);

        // 2025 法定节假日
        Set<String> h2025 = new HashSet<>(Arrays.asList(
                "2025-01-01",
                "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31",
                "2025-02-01", "2025-02-02", "2025-02-03", "2025-02-04",
                "2025-04-04", "2025-04-05", "2025-04-06",
                "2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05",
                "2025-05-31", "2025-06-01", "2025-06-02",
                "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-04",
                "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-08"
        ));
        HOLIDAYS.put(2025, h2025);

        Set<String> w2025 = new HashSet<>(Arrays.asList(
                "2025-01-26",
                "2025-02-08",
                "2025-04-27",
                "2025-09-28",
                "2025-10-11"
        ));
        WORKDAY_OVERRIDES.put(2025, w2025);

        // 2026 法定节假日（暂定，待国务院公告）
        Set<String> h2026 = new HashSet<>(Arrays.asList(
                "2026-01-01",
                "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
                "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24",
                "2026-04-05", "2026-04-06",
                "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
                "2026-06-19",
                "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04",
                "2026-10-05", "2026-10-06", "2026-10-07"
        ));
        HOLIDAYS.put(2026, h2026);
    }

    public Set<String> getHolidaysForRange(LocalDate from, LocalDate to) {
        Set<String> holidays = new HashSet<>();
        for (int year = from.getYear(); year <= to.getYear(); year++) {
            holidays.addAll(getCnHolidays(year));
        }
        return holidays;
    }

    public Set<String> getCnHolidays(int year) {
        try {
            List<?> response = restTemplate.getForObject(
                    "https://date.nager.at/api/v3/PublicHolidays/{year}/CN",
                    List.class,
                    year
            );
            if (response != null && !response.isEmpty()) {
                Set<String> remoteDates = new HashSet<>();
                for (Object item : response) {
                    if (item instanceof Map<?, ?> map) {
                        Object rawDate = map.get("date");
                        if (rawDate != null) {
                            remoteDates.add(String.valueOf(rawDate));
                        }
                    }
                }
                if (!remoteDates.isEmpty()) {
                    return remoteDates;
                }
            }
        } catch (Exception exception) {
            log.debug("Failed to fetch remote holidays for {}: {}", year, exception.getMessage());
        }

        return new HashSet<>(HOLIDAYS.getOrDefault(year, Set.of()));
    }

    public boolean isWorkday(String dateStr, Set<String> holidays) {
        LocalDate d = LocalDate.parse(dateStr);
        DayOfWeek dow = d.getDayOfWeek();

        // 法定节假日（包括调休休息）
        if (holidays.contains(dateStr)) return false;

        // 调休补班
        Set<String> overrides = WORKDAY_OVERRIDES.get(d.getYear());
        if (overrides != null && overrides.contains(dateStr)) return true;

        // 正常周末
        return dow != DayOfWeek.SATURDAY && dow != DayOfWeek.SUNDAY;
    }

    public List<String> iterWorkdays(String dateFrom, String dateTo, Set<String> holidays) {
        LocalDate start = LocalDate.parse(dateFrom);
        LocalDate end = LocalDate.parse(dateTo);
        if (start.isAfter(end)) { LocalDate tmp = start; start = end; end = tmp; }

        List<String> workdays = new ArrayList<>();
        LocalDate current = start;
        while (!current.isAfter(end)) {
            if (isWorkday(current.toString(), holidays)) workdays.add(current.toString());
            current = current.plusDays(1);
        }
        return workdays;
    }

    public int countWorkdays(String dateFrom, String dateTo, Set<String> holidays) {
        return iterWorkdays(dateFrom, dateTo, holidays).size();
    }

    public LocalDate latestWorkday(LocalDate referenceDate) {
        LocalDate current = referenceDate;

        while (true) {
            Set<String> holidays = getCnHolidays(current.getYear());
            if (isWorkday(current.toString(), holidays)) {
                return current;
            }
            current = current.minusDays(1);
        }
    }
}
