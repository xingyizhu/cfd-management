package com.cfd.controller;

import com.cfd.service.EmailService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequestMapping("/api/email")
@RequiredArgsConstructor
public class EmailController {

    private final EmailService emailService;

    /**
     * POST /api/email/remind
     * Body: {
     *   "underLogged": [...],
     *   "context": { "date_from": "...", "date_to": "...", "workday_count": N, "required_hours": N }
     * }
     */
    @PostMapping("/remind")
    public Map<String, Object> sendReminders(@RequestBody Map<String, Object> body) {
        List<Map<String, Object>> underLogged = (List<Map<String, Object>>) body.getOrDefault("underLogged", List.of());
        Map<String, Object> context = (Map<String, Object>) body.getOrDefault("context", Map.of());

        EmailService.SendResult result = emailService.sendReminders(underLogged, context);

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("sent", result.sent());
        resp.put("skipped", result.skipped());
        resp.put("sent_count", result.sent().size());
        return resp;
    }
}
