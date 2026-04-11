package com.cfd.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

@Data
public class ReminderPreviewDto {

    @JsonProperty("date_from")
    private String dateFrom;

    @JsonProperty("date_to")
    private String dateTo;

    @JsonProperty("workday_count")
    private int workdayCount;

    @JsonProperty("required_hours")
    private double requiredHours;

    @JsonProperty("under_logged")
    private List<UnderLoggedMemberDto> underLogged;
}
