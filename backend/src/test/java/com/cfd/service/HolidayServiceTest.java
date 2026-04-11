package com.cfd.service;

import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDate;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class HolidayServiceTest {

    @Test
    void shouldFallbackToLocalHolidayDataWhenRemoteFails() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        when(restTemplate.getForObject(anyString(), eq(List.class), eq(2025)))
                .thenThrow(new RuntimeException("network down"));
        HolidayService holidayService = new HolidayService(restTemplate);

        Set<String> holidays = holidayService.getCnHolidays(2025);

        assertTrue(holidays.contains("2025-10-01"));
        assertFalse(holidayService.isWorkday("2025-10-01", holidays));
        assertTrue(holidayService.isWorkday("2025-10-11", holidays));
    }

    @Test
    void shouldReturnLatestWorkdayBySkippingHolidayAndWeekend() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        when(restTemplate.getForObject(anyString(), eq(List.class), eq(2025)))
                .thenThrow(new RuntimeException("network down"));
        HolidayService holidayService = new HolidayService(restTemplate);

        LocalDate latest = holidayService.latestWorkday(LocalDate.of(2025, 10, 5));

        assertEquals(LocalDate.of(2025, 9, 30), latest);
    }
}
