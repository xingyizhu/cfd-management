package com.cfd.model;

import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
public class RangeSummaryDto {
    private RangeMetaDto meta;
    private List<WorklogRangeRowDto> rangeRows;
    private List<Map<String, Object>> underLogged;
    private boolean cacheHit;
}
