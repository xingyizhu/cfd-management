package com.cfd.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

@Data
public class WorklogRangeRowDto {
    @JsonProperty("account_id")
    private String accountId;

    @JsonProperty("display_name")
    private String displayName;

    @JsonProperty("logged_sec")
    private long loggedSec;

    @JsonProperty("estimated_sec")
    private long estimatedSec;

    @JsonProperty("issue_count")
    private int issueCount;

    @JsonProperty("issue_keys")
    private List<String> issueKeys;
}
