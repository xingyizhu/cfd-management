package com.cfd.model;

import lombok.Data;

import java.util.List;

@Data
public class ReminderSendResultDto {
    private List<String> sent;
    private List<String> skipped;
}
