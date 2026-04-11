package com.cfd.service;

import com.cfd.config.AppProperties;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Service;

import jakarta.mail.internet.MimeMessage;
import java.util.*;

/**
 * 邮件发送服务。对应 Python emailer.py 模块。
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class EmailService {

    private final JavaMailSender mailSender;
    private final AppProperties props;
    private final ObjectMapper objectMapper;

    public record SendResult(List<String> sent, List<String> skipped) {}

    public SendResult sendReminders(
            List<Map<String, Object>> underLogged,
            Map<String, Object> context) {

        Map<String, String> emailMap = parseMemberEmailMap();
        List<String> sent = new ArrayList<>();
        List<String> skipped = new ArrayList<>();

        String dateFrom = (String) context.getOrDefault("date_from", "");
        String dateTo = (String) context.getOrDefault("date_to", "");
        int workdayCount = (int) context.getOrDefault("workday_count", 0);
        double requiredHours = (double) context.getOrDefault("required_hours", 7.5);

        for (Map<String, Object> member : underLogged) {
            String accountId = (String) member.getOrDefault("accountId", "");
            String name = (String) member.getOrDefault("name", accountId);
            double loggedHours = (double) member.getOrDefault("logged_hours", 0.0);
            double missingHours = (double) member.getOrDefault("missing_hours", 0.0);

            String email = emailMap.get(accountId);
            if (email == null || email.isBlank()) {
                skipped.add(name + "（无邮箱）");
                continue;
            }

            try {
                String subject = String.format("工时提醒：%s 至 %s 区间工时不足", dateFrom, dateTo);
                String body = buildEmailBody(name, dateFrom, dateTo, workdayCount,
                        requiredHours, loggedHours, missingHours);
                sendEmail(email, subject, body);
                sent.add(name);
                log.info("邮件已发送至 {} ({})", name, email);
            } catch (Exception e) {
                log.error("发送邮件失败 {} ({}): {}", name, email, e.getMessage());
                skipped.add(name + "（发送失败）");
            }
        }

        return new SendResult(sent, skipped);
    }

    private void sendEmail(String to, String subject, String htmlBody) throws Exception {
        MimeMessage message = mailSender.createMimeMessage();
        MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");
        helper.setFrom(props.getSmtp().getSender());
        helper.setTo(to);
        helper.setSubject(subject);
        helper.setText(htmlBody, true);
        mailSender.send(message);
    }

    private String buildEmailBody(String name, String dateFrom, String dateTo,
                                   int workdayCount, double requiredHours,
                                   double loggedHours, double missingHours) {
        return String.format("""
                <html><body style="font-family: sans-serif; color: #222;">
                <p>Hi %s，</p>
                <p>统计区间 <strong>%s</strong> 至 <strong>%s</strong>（共 %d 个工作日）内，
                您的工时记录为 <strong>%.2f h</strong>，
                目标工时为 <strong>%.2f h</strong>，
                尚缺 <strong>%.2f h</strong>。</p>
                <p>请及时在 Jira 中补录工时记录。</p>
                <p style="color:#888; font-size:0.9em;">此邮件由 CFD 工时统计系统自动发送。</p>
                </body></html>
                """, name, dateFrom, dateTo, workdayCount,
                loggedHours, requiredHours, missingHours);
    }

    private Map<String, String> parseMemberEmailMap() {
        String raw = props.getBusiness().getMemberEmailMap();
        if (raw == null || raw.isBlank() || raw.equals("{}")) return Map.of();
        try {
            return objectMapper.readValue(raw, new TypeReference<Map<String, String>>() {});
        } catch (Exception e) {
            log.warn("解析 MEMBER_EMAIL_MAP 失败: {}", e.getMessage());
            return Map.of();
        }
    }
}
