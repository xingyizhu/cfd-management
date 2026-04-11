package com.cfd.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class RangeMetaDto {
    @JsonProperty("date_from")
    private String dateFrom;

    @JsonProperty("date_to")
    private String dateTo;

    @JsonProperty("day_count")
    private int dayCount;

    @JsonProperty("workday_count")
    private int workdayCount;

    @JsonProperty("week_start")
    private String weekStart;

    @JsonProperty("quarter_start")
    private String quarterStart;

    @JsonProperty("quarter_key")
    private String quarterKey;
}
