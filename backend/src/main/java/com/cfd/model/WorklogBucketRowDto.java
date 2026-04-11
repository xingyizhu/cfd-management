package com.cfd.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

@Data
public class WorklogBucketRowDto {

    @JsonProperty("account_id")
    private String accountId;

    @JsonProperty("display_name")
    private String displayName;

    @JsonProperty("work_date")
    private String workDate;

    @JsonProperty("week_start")
    private String weekStart;

    @JsonProperty("quarter_key")
    private String quarterKey;

    @JsonProperty("logged_sec")
    private long loggedSec;

    @JsonProperty("estimated_sec")
    private long estimatedSec;

    @JsonProperty("issue_count")
    private int issueCount;

    @JsonProperty("issue_keys")
    private List<String> issueKeys;
}
