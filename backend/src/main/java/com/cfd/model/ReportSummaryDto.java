package com.cfd.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

@Data
public class ReportSummaryDto {

    private RangeMetaDto meta;

    @JsonProperty("daily_rows")
    private List<WorklogBucketRowDto> dailyRows;

    @JsonProperty("weekly_rows")
    private List<WorklogBucketRowDto> weeklyRows;

    @JsonProperty("quarterly_rows")
    private List<WorklogBucketRowDto> quarterlyRows;

    @JsonProperty("range_rows")
    private List<WorklogRangeRowDto> rangeRows;

    @JsonProperty("under_logged")
    private List<UnderLoggedMemberDto> underLogged;

    @JsonProperty("cache_hit")
    private boolean cacheHit;
}
