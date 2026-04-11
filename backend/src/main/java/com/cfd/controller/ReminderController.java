package com.cfd.controller;

import com.cfd.model.ReminderPreviewDto;
import com.cfd.model.ReminderSendResultDto;
import com.cfd.service.EmailService;
import com.cfd.service.ReportService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/reminders")
@RequiredArgsConstructor
public class ReminderController {

    private final ReportService reportService;
    private final EmailService emailService;

    @GetMapping("/preview")
    public ReminderPreviewDto preview(
            @RequestParam String dateFrom,
            @RequestParam String dateTo) {
        return reportService.previewReminder(LocalDate.parse(dateFrom), LocalDate.parse(dateTo));
    }

    @PostMapping("/send")
    public ReminderSendResultDto send(
            @RequestParam String dateFrom,
            @RequestParam String dateTo) {
        ReminderPreviewDto preview = reportService.previewReminder(LocalDate.parse(dateFrom), LocalDate.parse(dateTo));

        var sendResult = emailService.sendReminders(
                preview.getUnderLogged().stream().map(member -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("accountId", member.getAccountId());
                    row.put("name", member.getName());
                    row.put("logged_hours", member.getLoggedHours());
                    row.put("missing_hours", member.getMissingHours());
                    return row;
                }).toList(),
                Map.of(
                        "date_from", preview.getDateFrom(),
                        "date_to", preview.getDateTo(),
                        "workday_count", preview.getWorkdayCount(),
                        "required_hours", preview.getRequiredHours()
                )
        );

        ReminderSendResultDto dto = new ReminderSendResultDto();
        dto.setSent(sendResult.sent());
        dto.setSkipped(sendResult.skipped());
        return dto;
    }
}
