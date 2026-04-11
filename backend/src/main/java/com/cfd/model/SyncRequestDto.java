package com.cfd.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class SyncRequestDto {

    @JsonProperty("date_from")
    private String dateFrom;

    @JsonProperty("date_to")
    private String dateTo;

    @JsonProperty("force_refresh")
    private boolean forceRefresh;
}
