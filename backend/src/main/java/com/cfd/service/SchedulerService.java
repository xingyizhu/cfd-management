package com.cfd.service;

import com.cfd.client.AtlassianClient;
import com.cfd.config.AppProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.Map;
import java.util.Set;

@Service
@Slf4j
@RequiredArgsConstructor
public class SchedulerService {

    private final AppProperties appProperties;
    private final HolidayService holidayService;
    private final SyncService syncService;
    private final AtlassianClient atlassianClient;
    private final ReportService reportService;
    private final EmailService emailService;

    @Scheduled(cron = "${cfd.scheduler.sync-cron}", zone = "${cfd.scheduler.zone}")
    public void syncWorklogWindow() {
        if (!appProperties.getScheduler().isEnabled()) {
            return;
        }

        LocalDate targetDate = holidayService.latestWorkday(LocalDate.now());
        Set<String> holidays = holidayService.getHolidaysForRange(targetDate, targetDate);
        Map<String, Integer> result = syncService.syncForceRefreshWindow(
                targetDate,
                reportService.toMemberMaps(atlassianClient.getTeamMembers()),
                holidays
        );
        log.info("Scheduled sync finished for {}: {}", targetDate, result);
    }

    @Scheduled(cron = "${cfd.scheduler.reminder-cron}", zone = "${cfd.scheduler.zone}")
    public void sendReminderEmails() {
        if (!appProperties.getScheduler().isEnabled()) {
            return;
        }

        LocalDate targetDate = holidayService.latestWorkday(LocalDate.now());
        var preview = reportService.previewReminder(targetDate, targetDate);
        if (preview.getUnderLogged().isEmpty()) {
            log.info("No reminder emails needed for {}", targetDate);
            return;
        }

        var sendResult = emailService.sendReminders(
                preview.getUnderLogged().stream().map(member -> Map.<String, Object>of(
                        "accountId", member.getAccountId(),
                        "name", member.getName(),
                        "logged_hours", member.getLoggedHours(),
                        "missing_hours", member.getMissingHours()
                )).toList(),
                Map.of(
                        "date_from", preview.getDateFrom(),
                        "date_to", preview.getDateTo(),
                        "workday_count", preview.getWorkdayCount(),
                        "required_hours", preview.getRequiredHours()
                )
        );
        log.info("Scheduled reminder finished: sent={}, skipped={}", sendResult.sent().size(), sendResult.skipped().size());
    }
}
