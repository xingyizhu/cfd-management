package com.cfd.controller;

import com.cfd.service.HolidayService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.*;

@RestController
@RequestMapping("/api/holidays")
@RequiredArgsConstructor
public class HolidayController {

    private final HolidayService holidayService;

    /**
     * GET /api/holidays?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD
     * 返回指定范围内的节假日列表和工作日数量。
     */
    @GetMapping
    public Map<String, Object> getHolidays(
            @RequestParam String dateFrom,
            @RequestParam String dateTo) {

        LocalDate start = LocalDate.parse(dateFrom);
        LocalDate end = LocalDate.parse(dateTo);
        if (start.isAfter(end)) { LocalDate tmp = start; start = end; end = tmp; }

        Set<String> holidays = holidayService.getHolidaysForRange(start, end);
        List<String> workdays = holidayService.iterWorkdays(start.toString(), end.toString(), holidays);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("holidays", new ArrayList<>(holidays));
        result.put("workdays", workdays);
        result.put("workday_count", workdays.size());
        return result;
    }
}
